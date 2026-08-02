from pathlib import Path
from io import BytesIO
import base64
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener


# Permet à Pillow d'ouvrir les fichiers HEIC et HEIF.
register_heif_opener()


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

MODEL = "gpt-5.6-terra"

IMAGE_PATH = (
    BASE_DIR
    / "patients_test"
    / "P-0001"
    / "notes_originales"
    / "2026-08-01_PA.heic"
)

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".heic",
    ".heif",
}

MAX_IMAGE_SIZE = (2400, 2400)
JPEG_QUALITY = 92


# ---------------------------------------------------------
# CHARGEMENT DU CLIENT OPENAI
# ---------------------------------------------------------

def charger_client() -> OpenAI:
    """
    Charge la clé API OpenAI depuis le fichier .env.
    """

    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f"Fichier .env introuvable : {ENV_PATH}"
        )

    load_dotenv(ENV_PATH)

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "La variable OPENAI_API_KEY est absente ou vide "
            "dans le fichier .env."
        )

    return OpenAI(api_key=api_key)


# ---------------------------------------------------------
# VÉRIFICATION DE L'IMAGE
# ---------------------------------------------------------

def verifier_image(image_path: Path) -> None:
    """
    Vérifie que le fichier existe et que son extension
    est prise en charge.
    """

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image introuvable : {image_path}"
        )

    if not image_path.is_file():
        raise ValueError(
            f"Le chemin n'est pas un fichier : {image_path}"
        )

    extension = image_path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        extensions = ", ".join(
            sorted(SUPPORTED_EXTENSIONS)
        )

        raise ValueError(
            f"Format non pris en charge : {extension}\n"
            f"Formats acceptés : {extensions}"
        )


# ---------------------------------------------------------
# CONVERSION HEIC VERS JPEG
# ---------------------------------------------------------

def convertir_image_en_data_url(
    image_path: Path,
) -> str:
    """
    Ouvre l'image originale, y compris au format HEIC,
    corrige son orientation, réduit sa taille si nécessaire,
    puis la convertit en JPEG en mémoire.

    Le fichier original n'est pas modifié.
    """

    verifier_image(image_path)

    try:
        with Image.open(image_path) as image:
            print(
                f"Format réel détecté : {image.format}"
            )
            print(
                f"Dimensions originales : {image.size}"
            )
            print(
                f"Mode colorimétrique : {image.mode}"
            )

            # Corrige l'orientation enregistrée par l'iPhone.
            image = ImageOps.exif_transpose(image)

            # Réduit la résolution sans déformer l'image.
            image.thumbnail(
                MAX_IMAGE_SIZE,
                Image.Resampling.LANCZOS,
            )

            print(
                f"Dimensions après préparation : {image.size}"
            )

            # Le JPEG doit être enregistré en mode RGB.
            if image.mode != "RGB":
                image = image.convert("RGB")

            tampon = BytesIO()

            image.save(
                tampon,
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
            )

            donnees_jpeg = tampon.getvalue()

    except Exception as erreur:
        raise ValueError(
            "Impossible de lire ou de convertir l'image.\n"
            f"Fichier concerné : {image_path}\n"
            f"Détail technique : {erreur}"
        ) from erreur

    if not donnees_jpeg:
        raise ValueError(
            "La conversion a produit une image vide."
        )

    taille_ko = len(donnees_jpeg) / 1024

    print(
        f"Taille du JPEG envoyé : {taille_ko:.1f} Ko"
    )

    image_base64 = base64.b64encode(
        donnees_jpeg
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        f"{image_base64}"
    )


# ---------------------------------------------------------
# TRANSCRIPTION PAR GPT-5.6 TERRA
# ---------------------------------------------------------

def transcrire_image(
    client: OpenAI,
    image_path: Path,
):
    """
    Envoie l'image convertie à GPT-5.6 Terra et demande
    une transcription fidèle, sans analyse clinique.
    """

    image_data_url = convertir_image_en_data_url(
        image_path
    )

    print("\nEnvoi de l'image à GPT-5.6 Terra...")

    reponse = client.responses.create(
        model=MODEL,

        # Aucun raisonnement approfondi n'est nécessaire
        # pour cette simple transcription.
        reasoning={
            "effort": "none"
        },

        # La réponse ne doit pas être conservée pour
        # être récupérée ultérieurement via l'API.
        store=False,

        # Limite largement suffisante pour une page de notes.
        max_output_tokens=2000,

        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Transcris exactement cette note manuscrite "
                            "de test.\n\n"
                            "Règles impératives :\n"
                            "- Ne résume pas.\n"
                            "- N'analyse pas le contenu.\n"
                            "- N'interprète pas les informations.\n"
                            "- Ne complète aucune information absente.\n"
                            "- N'invente aucun mot.\n"
                            "- Ne corrige pas les formulations.\n"
                            "- Conserve autant que possible les titres, "
                            "les paragraphes, les listes et la "
                            "ponctuation.\n"
                            "- Écris [illisible] lorsqu'un passage ne "
                            "peut pas être lu avec suffisamment de "
                            "certitude.\n"
                            "- Écris [mot incertain : proposition] "
                            "lorsqu'un mot semble probable mais reste "
                            "incertain.\n"
                            "- Retourne uniquement la transcription, "
                            "sans introduction ni commentaire."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url,
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    transcription = reponse.output_text.strip()

    if not transcription:
        raise RuntimeError(
            "GPT-5.6 Terra n'a retourné aucune "
            "transcription."
        )

    return transcription, reponse


# ---------------------------------------------------------
# ENREGISTREMENT DE LA TRANSCRIPTION
# ---------------------------------------------------------

def enregistrer_transcription(
    image_path: Path,
    transcription: str,
) -> Path:
    """
    Crée un fichier texte dans le dossier transcriptions
    du patient.
    """

    dossier_patient = image_path.parent.parent

    dossier_transcriptions = (
        dossier_patient
        / "transcriptions"
    )

    dossier_transcriptions.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        dossier_transcriptions
        / f"{image_path.stem}.txt"
    )

    destination.write_text(
        transcription,
        encoding="utf-8",
    )

    return destination


# ---------------------------------------------------------
# AFFICHAGE DES TOKENS
# ---------------------------------------------------------

def afficher_utilisation(reponse) -> None:
    """
    Affiche le nombre de tokens indiqué par l'API.
    """

    print("\n--- UTILISATION API ---")

    usage = getattr(reponse, "usage", None)

    if usage is None:
        print(
            "Les informations d'utilisation "
            "ne sont pas disponibles."
        )
        return

    input_tokens = getattr(
        usage,
        "input_tokens",
        None,
    )

    output_tokens = getattr(
        usage,
        "output_tokens",
        None,
    )

    total_tokens = getattr(
        usage,
        "total_tokens",
        None,
    )

    print(
        f"Tokens d'entrée : {input_tokens}"
    )
    print(
        f"Tokens de sortie : {output_tokens}"
    )
    print(
        f"Tokens totaux : {total_tokens}"
    )


# ---------------------------------------------------------
# PROGRAMME PRINCIPAL
# ---------------------------------------------------------

def main() -> None:
    print("--- TEST DE TRANSCRIPTION ---")
    print(f"Modèle : {MODEL}")
    print(f"Image originale : {IMAGE_PATH}")

    try:
        client = charger_client()

        transcription, reponse = transcrire_image(
            client,
            IMAGE_PATH,
        )

        destination = enregistrer_transcription(
            IMAGE_PATH,
            transcription,
        )

        print("\n--- TRANSCRIPTION OBTENUE ---\n")
        print(transcription)

        afficher_utilisation(reponse)

        print("\n--- ENREGISTREMENT ---")
        print(
            f"Fichier créé : {destination}"
        )

    except FileNotFoundError as erreur:
        print(
            f"\nErreur de fichier : {erreur}"
        )
        sys.exit(1)

    except RuntimeError as erreur:
        print(
            f"\nErreur de configuration : {erreur}"
        )
        sys.exit(1)

    except Exception as erreur:
        print(
            "\nErreur lors du traitement : "
            f"{type(erreur).__name__}: {erreur}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()