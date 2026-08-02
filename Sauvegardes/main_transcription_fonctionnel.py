from __future__ import annotations

from pathlib import Path
from io import BytesIO
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener


# ---------------------------------------------------------
# PRISE EN CHARGE DES PHOTOS IPHONE HEIC / HEIF
# ---------------------------------------------------------

register_heif_opener()


# ---------------------------------------------------------
# CONFIGURATION GÉNÉRALE
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

ENTREE_DIR = BASE_DIR / "entree"
PATIENTS_DIR = BASE_DIR / "patients_test"
ENV_PATH = BASE_DIR / ".env"

MODEL = "gpt-5.6-terra"

# Extensions que le programme examine dans le dossier entree.
# Une image HEIC simplement renommée en .jpg reste acceptée :
# son vrai format sera détecté avec Pillow.
EXTENSIONS_ENTREE = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".heic",
    ".heif",
}

# Extension utilisée dans le dossier patient selon le vrai
# format interne détecté.
EXTENSIONS_PAR_FORMAT = {
    "JPEG": ".jpg",
    "JPG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "HEIF": ".heic",
    "HEIC": ".heic",
}

# L’image est réduite avant son envoi à l’API afin de limiter
# le coût tout en maintenant une bonne lisibilité.
MAX_IMAGE_SIZE = (2400, 2400)

JPEG_QUALITY = 92

MAX_OUTPUT_TOKENS = 2000


# ---------------------------------------------------------
# CLIENT OPENAI
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
# NORMALISATION DES NOMS
# ---------------------------------------------------------

def normaliser_texte(texte: str) -> str:
    """
    Met le texte en minuscules, supprime les accents et
    transforme les séparateurs en espaces.

    Exemple :
    '2026-08-01_PA' devient '2026 08 01 pa'
    """

    texte = unicodedata.normalize("NFD", texte)

    texte = "".join(
        caractere
        for caractere in texte
        if unicodedata.category(caractere) != "Mn"
    )

    texte = texte.lower()

    texte = re.sub(
        r"[^a-z0-9]+",
        " ",
        texte,
    )

    return texte.strip()


# ---------------------------------------------------------
# CHARGEMENT DES PROFILS PATIENTS
# ---------------------------------------------------------

def charger_patients() -> list[dict]:
    """
    Charge tous les fichiers profil.json présents dans
    patients_test.
    """

    if not PATIENTS_DIR.exists():
        raise FileNotFoundError(
            f"Dossier patients introuvable : {PATIENTS_DIR}"
        )

    patients = []

    for profil_path in sorted(
        PATIENTS_DIR.glob("*/profil.json")
    ):
        try:
            with profil_path.open(
                "r",
                encoding="utf-8",
            ) as fichier:
                profil = json.load(fichier)

        except json.JSONDecodeError as erreur:
            raise ValueError(
                f"JSON invalide dans : {profil_path}\n"
                f"Détail : {erreur}"
            ) from erreur

        identifiant = profil.get("identifiant")

        if not identifiant:
            raise ValueError(
                f"Identifiant absent dans : {profil_path}"
            )

        profil["dossier"] = profil_path.parent
        patients.append(profil)

    if not patients:
        raise RuntimeError(
            "Aucun profil patient n'a été trouvé dans "
            f"{PATIENTS_DIR}."
        )

    return patients


# ---------------------------------------------------------
# IDENTIFICATION DU PATIENT
# ---------------------------------------------------------

def identifier_patient_depuis_nom(
    fichier: Path,
    patients: list[dict],
) -> tuple[dict | None, list[dict]]:
    """
    Recherche les alias du profil patient dans le nom
    du fichier.

    Retourne :
    - le patient si une seule correspondance est trouvée ;
    - None si aucune ou plusieurs correspondances existent ;
    - la liste complète des correspondances.
    """

    nom_normalise = normaliser_texte(fichier.stem)

    nom_encadre = f" {nom_normalise} "

    correspondances = []

    for patient in patients:
        alias_patient = patient.get(
            "alias_fichiers",
            [],
        )

        patient_correspond = False

        for alias in alias_patient:
            alias_normalise = normaliser_texte(
                str(alias)
            )

            if not alias_normalise:
                continue

            alias_encadre = f" {alias_normalise} "

            if alias_encadre in nom_encadre:
                patient_correspond = True
                break

        if patient_correspond:
            correspondances.append(patient)

    if len(correspondances) == 1:
        return correspondances[0], correspondances

    return None, correspondances


# ---------------------------------------------------------
# DÉTECTION DU VRAI FORMAT DE L’IMAGE
# ---------------------------------------------------------

def detecter_format_reel(
    image_path: Path,
) -> tuple[str, str]:
    """
    Détecte le vrai format interne de l’image, indépendamment
    de son extension.

    Par exemple, un fichier HEIC renommé artificiellement
    en .jpg sera détecté comme HEIF et enregistré avec
    l’extension .heic dans le dossier patient.
    """

    try:
        with Image.open(image_path) as image:
            format_reel = (
                image.format or ""
            ).upper()

    except Exception as erreur:
        raise ValueError(
            "Le fichier ne peut pas être lu comme une image "
            f"valide : {image_path.name}\n"
            f"Détail technique : {erreur}"
        ) from erreur

    if not format_reel:
        raise ValueError(
            f"Format réel impossible à déterminer : "
            f"{image_path.name}"
        )

    extension_normalisee = EXTENSIONS_PAR_FORMAT.get(
        format_reel
    )

    if extension_normalisee is None:
        raise ValueError(
            f"Format réel non pris en charge : "
            f"{format_reel}"
        )

    return format_reel, extension_normalisee


# ---------------------------------------------------------
# COMPARAISON DES FICHIERS
# ---------------------------------------------------------

def calculer_sha256(fichier: Path) -> str:
    """
    Calcule l’empreinte SHA-256 d’un fichier afin de savoir
    si deux fichiers sont strictement identiques.
    """

    calcul = hashlib.sha256()

    with fichier.open("rb") as contenu:
        for bloc in iter(
            lambda: contenu.read(1024 * 1024),
            b"",
        ):
            calcul.update(bloc)

    return calcul.hexdigest()


def fichiers_identiques(
    fichier_a: Path,
    fichier_b: Path,
) -> bool:
    """
    Compare deux fichiers sans se fier uniquement à leur nom.
    """

    if not fichier_a.exists():
        return False

    if not fichier_b.exists():
        return False

    if fichier_a.stat().st_size != fichier_b.stat().st_size:
        return False

    return (
        calculer_sha256(fichier_a)
        == calculer_sha256(fichier_b)
    )


# ---------------------------------------------------------
# GESTION DES NOMS DE FICHIERS
# ---------------------------------------------------------

def obtenir_destination_unique(
    destination: Path,
) -> Path:
    """
    Évite d’écraser un fichier différent portant déjà
    le même nom.

    Exemple :
    2026-08-01_PA.heic
    devient
    2026-08-01_PA_2.heic
    """

    if not destination.exists():
        return destination

    compteur = 2

    while True:
        nouvelle_destination = destination.with_name(
            f"{destination.stem}_{compteur}"
            f"{destination.suffix}"
        )

        if not nouvelle_destination.exists():
            return nouvelle_destination

        compteur += 1


# ---------------------------------------------------------
# COPIE DANS LE DOSSIER PATIENT
# ---------------------------------------------------------

def copier_dans_dossier_patient(
    fichier_source: Path,
    patient: dict,
) -> tuple[Path, bool, str]:
    """
    Copie l’image dans notes_originales.

    Le vrai format de l’image détermine l’extension utilisée.

    Retourne :
    - le chemin de destination ;
    - True si une nouvelle copie a été créée ;
    - le vrai format détecté.
    """

    format_reel, extension_reelle = detecter_format_reel(
        fichier_source
    )

    dossier_notes = (
        patient["dossier"]
        / "notes_originales"
    )

    dossier_notes.mkdir(
        parents=True,
        exist_ok=True,
    )

    nom_normalise = (
        f"{fichier_source.stem}"
        f"{extension_reelle}"
    )

    destination_initiale = (
        dossier_notes
        / nom_normalise
    )

    # Si le même fichier est déjà présent, on le réutilise.
    if destination_initiale.exists():
        if fichiers_identiques(
            fichier_source,
            destination_initiale,
        ):
            return (
                destination_initiale,
                False,
                format_reel,
            )

        # Même nom, mais contenu différent :
        # création d’un nom avec _2, _3, etc.
        destination = obtenir_destination_unique(
            destination_initiale
        )

    else:
        destination = destination_initiale

    shutil.copy2(
        fichier_source,
        destination,
    )

    return destination, True, format_reel


# ---------------------------------------------------------
# CONVERSION TEMPORAIRE VERS JPEG
# ---------------------------------------------------------

def convertir_image_en_data_url(
    image_path: Path,
) -> str:
    """
    Ouvre l’image originale, corrige son orientation,
    réduit sa taille et la convertit temporairement en JPEG.

    Le fichier original stocké dans notes_originales
    n’est jamais modifié.
    """

    try:
        with Image.open(image_path) as image:
            print(
                f"    Format réel : {image.format}"
            )
            print(
                f"    Dimensions originales : "
                f"{image.size}"
            )

            image = ImageOps.exif_transpose(
                image
            )

            image.thumbnail(
                MAX_IMAGE_SIZE,
                Image.Resampling.LANCZOS,
            )

            print(
                f"    Dimensions envoyées : "
                f"{image.size}"
            )

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
            "Impossible de préparer l’image pour l’API : "
            f"{image_path}\n"
            f"Détail : {erreur}"
        ) from erreur

    if not donnees_jpeg:
        raise ValueError(
            "La conversion de l’image a produit "
            "un fichier vide."
        )

    taille_ko = len(donnees_jpeg) / 1024

    print(
        f"    Taille envoyée : "
        f"{taille_ko:.1f} Ko"
    )

    contenu_base64 = base64.b64encode(
        donnees_jpeg
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        f"{contenu_base64}"
    )


# ---------------------------------------------------------
# CHEMIN DE LA TRANSCRIPTION
# ---------------------------------------------------------

def obtenir_chemin_transcription(
    image_path: Path,
) -> Path:
    """
    Calcule le chemin du fichier texte correspondant
    à l’image.
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

    return (
        dossier_transcriptions
        / f"{image_path.stem}.txt"
    )


# ---------------------------------------------------------
# APPEL À GPT-5.6 TERRA
# ---------------------------------------------------------

def transcrire_image(
    client: OpenAI,
    image_path: Path,
):
    """
    Envoie l’image à GPT-5.6 Terra et demande uniquement
    une transcription fidèle.
    """

    image_data_url = convertir_image_en_data_url(
        image_path
    )

    reponse = client.responses.create(
        model=MODEL,

        reasoning={
            "effort": "none",
        },

        store=False,

        max_output_tokens=MAX_OUTPUT_TOKENS,

        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Transcris exactement cette note "
                            "manuscrite de test.\n\n"
                            "Règles impératives :\n"
                            "- Retourne du texte brut uniquement.\n"
                            "- N'utilise aucun titre Markdown.\n"
                            "- N'utilise aucun symbole Markdown.\n"
                            "- Ne résume pas.\n"
                            "- N'analyse pas le contenu.\n"
                            "- N'interprète pas les informations.\n"
                            "- Ne complète aucune information "
                            "absente.\n"
                            "- N'invente aucun mot.\n"
                            "- Ne corrige pas les formulations.\n"
                            "- Conserve les accents présents.\n"
                            "- Conserve autant que possible les "
                            "titres, paragraphes, listes et la "
                            "ponctuation.\n"
                            "- Écris [illisible] lorsqu'un passage "
                            "ne peut pas être lu avec suffisamment "
                            "de certitude.\n"
                            "- Écris [mot incertain : proposition] "
                            "lorsqu'un mot semble probable mais "
                            "reste incertain.\n"
                            "- Ne fournis aucune introduction, "
                            "conclusion ou commentaire."
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
    destination: Path,
    transcription: str,
) -> None:
    """
    Enregistre la transcription en UTF-8.
    """

    destination.write_text(
        transcription,
        encoding="utf-8",
    )


# ---------------------------------------------------------
# UTILISATION DE L’API
# ---------------------------------------------------------

def obtenir_utilisation(
    reponse,
) -> tuple[int, int, int]:
    """
    Récupère les tokens utilisés.
    """

    usage = getattr(
        reponse,
        "usage",
        None,
    )

    if usage is None:
        return 0, 0, 0

    input_tokens = (
        getattr(
            usage,
            "input_tokens",
            0,
        )
        or 0
    )

    output_tokens = (
        getattr(
            usage,
            "output_tokens",
            0,
        )
        or 0
    )

    total_tokens = (
        getattr(
            usage,
            "total_tokens",
            0,
        )
        or 0
    )

    return (
        input_tokens,
        output_tokens,
        total_tokens,
    )


# ---------------------------------------------------------
# LISTE DES IMAGES À TRAITER
# ---------------------------------------------------------

def obtenir_images_entree() -> list[Path]:
    """
    Retourne les images présentes dans entree.
    """

    ENTREE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fichiers = [
        fichier
        for fichier in ENTREE_DIR.iterdir()
        if fichier.is_file()
        and fichier.suffix.lower()
        in EXTENSIONS_ENTREE
    ]

    return sorted(
        fichiers,
        key=lambda fichier: fichier.name.lower(),
    )


# ---------------------------------------------------------
# TRAITEMENT D’UNE IMAGE
# ---------------------------------------------------------

def traiter_image(
    client: OpenAI,
    fichier_source: Path,
    patients: list[dict],
) -> tuple[str, int, int, int]:
    """
    Traite une seule image.

    Retourne :
    - son statut ;
    - les tokens d’entrée ;
    - les tokens de sortie ;
    - les tokens totaux.
    """

    print("\n" + "=" * 70)
    print(f"FICHIER : {fichier_source.name}")

    patient, correspondances = (
        identifier_patient_depuis_nom(
            fichier_source,
            patients,
        )
    )

    if patient is None:
        if not correspondances:
            print(
                "Résultat : patient non identifié."
            )
            print(
                "Le fichier reste dans entree et "
                "n'est pas copié."
            )

            return "non_identifie", 0, 0, 0

        identifiants = ", ".join(
            correspondance["identifiant"]
            for correspondance in correspondances
        )

        print(
            "Résultat : identification ambiguë."
        )
        print(
            f"Patients possibles : {identifiants}"
        )
        print(
            "Le fichier reste dans entree et "
            "n'est pas copié."
        )

        return "ambigu", 0, 0, 0

    print(
        f"Patient identifié : "
        f"{patient['identifiant']} "
        f"({patient.get('nom_affichage', '')})"
    )

    image_patient, copie_creee, format_reel = (
        copier_dans_dossier_patient(
            fichier_source,
            patient,
        )
    )

    print(
        f"Format détecté : {format_reel}"
    )

    if copie_creee:
        print(
            f"Photo copiée vers : {image_patient}"
        )
    else:
        print(
            "Photo identique déjà présente dans "
            "notes_originales."
        )
        print(
            f"Photo réutilisée : {image_patient}"
        )

    chemin_transcription = (
        obtenir_chemin_transcription(
            image_patient
        )
    )

    # Protection contre les dépenses répétées.
    if chemin_transcription.exists():
        print(
            "Transcription déjà existante."
        )
        print(
            "Aucun nouvel appel API n'a été effectué."
        )
        print(
            f"Fichier existant : "
            f"{chemin_transcription}"
        )

        return "deja_traite", 0, 0, 0

    print(
        "Préparation et envoi à "
        "GPT-5.6 Terra..."
    )

    transcription, reponse = transcrire_image(
        client,
        image_patient,
    )

    enregistrer_transcription(
        chemin_transcription,
        transcription,
    )

    input_tokens, output_tokens, total_tokens = (
        obtenir_utilisation(
            reponse
        )
    )

    print("\n--- TRANSCRIPTION ---\n")
    print(transcription)

    print("\n--- UTILISATION API ---")
    print(
        f"Tokens d'entrée : {input_tokens}"
    )
    print(
        f"Tokens de sortie : {output_tokens}"
    )
    print(
        f"Tokens totaux : {total_tokens}"
    )

    print("\n--- ENREGISTREMENT ---")
    print(
        f"Transcription créée : "
        f"{chemin_transcription}"
    )

    return (
        "traite",
        input_tokens,
        output_tokens,
        total_tokens,
    )


# ---------------------------------------------------------
# PROGRAMME PRINCIPAL
# ---------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("PSYCHO IA — CLASSEMENT ET TRANSCRIPTION")
    print("=" * 70)

    print(f"Modèle : {MODEL}")
    print(f"Dossier d'entrée : {ENTREE_DIR}")
    print(f"Dossiers patients : {PATIENTS_DIR}")

    try:
        patients = charger_patients()
        images = obtenir_images_entree()

        if not images:
            print(
                "\nAucune image trouvée dans le "
                "dossier entree."
            )
            return

        print(
            f"\nNombre d'images trouvées : "
            f"{len(images)}"
        )

        client = charger_client()

        compteurs = {
            "traite": 0,
            "deja_traite": 0,
            "non_identifie": 0,
            "ambigu": 0,
            "erreur": 0,
        }

        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        for image in images:
            try:
                (
                    statut,
                    input_tokens,
                    output_tokens,
                    tokens,
                ) = traiter_image(
                    client,
                    image,
                    patients,
                )

                compteurs[statut] += 1

                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_tokens += tokens

            except Exception as erreur:
                compteurs["erreur"] += 1

                print(
                    "\nERREUR POUR CE FICHIER :"
                )
                print(
                    f"{type(erreur).__name__}: "
                    f"{erreur}"
                )

                print(
                    "Le programme continue avec "
                    "les autres fichiers."
                )

        print("\n" + "=" * 70)
        print("RÉSUMÉ DU TRAITEMENT")
        print("=" * 70)

        print(
            f"Nouvelles transcriptions : "
            f"{compteurs['traite']}"
        )
        print(
            f"Déjà traitées : "
            f"{compteurs['deja_traite']}"
        )
        print(
            f"Patients non identifiés : "
            f"{compteurs['non_identifie']}"
        )
        print(
            f"Identifications ambiguës : "
            f"{compteurs['ambigu']}"
        )
        print(
            f"Erreurs : "
            f"{compteurs['erreur']}"
        )

        print("\n--- TOTAL API ---")
        print(
            f"Tokens d'entrée : "
            f"{total_input_tokens}"
        )
        print(
            f"Tokens de sortie : "
            f"{total_output_tokens}"
        )
        print(
            f"Tokens totaux : "
            f"{total_tokens}"
        )

        print(
            "\nLes fichiers originaux sont "
            "conservés dans entree."
        )

    except Exception as erreur:
        print(
            "\nERREUR GÉNÉRALE : "
            f"{type(erreur).__name__}: "
            f"{erreur}"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()