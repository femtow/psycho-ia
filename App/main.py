from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
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
from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# PRISE EN CHARGE DES PHOTOS IPHONE HEIC / HEIF
# =========================================================

register_heif_opener()


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ENTREE_DIR = BASE_DIR / "entree"
PATIENTS_DIR = BASE_DIR / "patients_test"
ENV_PATH = BASE_DIR / ".env"

MODEL = "gpt-5.6-terra"

EXTENSIONS_ENTREE = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".heic",
    ".heif",
}

EXTENSIONS_PAR_FORMAT = {
    "JPEG": ".jpg",
    "JPG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "HEIF": ".heic",
    "HEIC": ".heic",
}

MAX_IMAGE_SIZE = (2400, 2400)
JPEG_QUALITY = 92

MAX_OUTPUT_TOKENS_OCR = 2000
MAX_OUTPUT_TOKENS_EXTRACTION = 2000


# =========================================================
# SCHÉMA DES DONNÉES CLINIQUES
# =========================================================

class DonneesCliniques(BaseModel):
    """
    Structure obligatoire du fichier JSON produit à partir
    d'une transcription.

    extra="forbid" interdit au modèle d'ajouter des champs
    non prévus.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    date_seance: date | None = Field(
        description=(
            "Date explicite de la séance au format AAAA-MM-JJ. "
            "Valeur null si elle est absente ou incertaine."
        )
    )

    faits_rapportes: list[str] = Field(
        description=(
            "Faits, événements, symptômes, circonstances ou "
            "expériences explicitement rapportés et ne relevant "
            "pas plus précisément d'une autre catégorie."
        )
    )

    emotions: list[str] = Field(
        description=(
            "Émotions explicitement indiquées, sans les déduire."
        )
    )

    cognitions: list[str] = Field(
        description=(
            "Pensées, anticipations, interprétations, croyances "
            "ou images mentales explicitement présentes."
        )
    )

    comportements: list[str] = Field(
        description=(
            "Actions ou comportements observables explicitement "
            "présents, hors évitements, interventions et tâches."
        )
    )

    evitements: list[str] = Field(
        description=(
            "Situations, sensations, pensées ou activités "
            "explicitement évitées."
        )
    )

    interventions: list[str] = Field(
        description=(
            "Interventions, exercices ou stratégies proposés "
            "ou réalisés dans le cadre thérapeutique."
        )
    )

    taches_interseances: list[str] = Field(
        description=(
            "Exercices, actions ou observations explicitement "
            "demandés entre les séances."
        )
    )

    elements_incertains: list[str] = Field(
        description=(
            "Informations illisibles, ambiguës, contradictoires "
            "ou dont la catégorisation reste incertaine."
        )
    )


# =========================================================
# CLIENT OPENAI
# =========================================================

def charger_client() -> OpenAI:
    """
    Charge la clé API depuis le fichier .env.
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


def obtenir_client(
    cache_client: dict[str, OpenAI],
) -> OpenAI:
    """
    Ne charge le client OpenAI que lorsqu'un appel API
    est réellement nécessaire.

    Ainsi, si tous les fichiers existent déjà, aucune clé
    n'est chargée et aucun appel n'est effectué.
    """

    if "client" not in cache_client:
        cache_client["client"] = charger_client()

    return cache_client["client"]


# =========================================================
# NORMALISATION DES NOMS
# =========================================================

def normaliser_texte(texte: str) -> str:
    """
    Supprime les accents, met en minuscules et remplace
    les séparateurs par des espaces.

    Exemple :
    2026-08-01_PA → 2026 08 01 pa
    """

    texte = unicodedata.normalize(
        "NFD",
        texte,
    )

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


# =========================================================
# CHARGEMENT DES PROFILS PATIENTS
# =========================================================

def charger_patients() -> list[dict]:
    """
    Charge tous les fichiers profil.json présents dans
    patients_test.
    """

    if not PATIENTS_DIR.exists():
        raise FileNotFoundError(
            f"Dossier patients introuvable : {PATIENTS_DIR}"
        )

    patients: list[dict] = []

    profils = sorted(
        PATIENTS_DIR.glob("*/profil.json")
    )

    for profil_path in profils:
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
            "Aucun profil patient trouvé dans "
            f"{PATIENTS_DIR}."
        )

    return patients


# =========================================================
# IDENTIFICATION DU PATIENT
# =========================================================

def identifier_patient_depuis_nom(
    fichier: Path,
    patients: list[dict],
) -> tuple[dict | None, list[dict]]:
    """
    Cherche les alias des patients dans le nom du fichier.

    Retourne :
    - le patient si une seule correspondance est trouvée ;
    - None si aucune ou plusieurs correspondances existent ;
    - la liste des correspondances trouvées.
    """

    nom_normalise = normaliser_texte(
        fichier.stem
    )

    nom_encadre = f" {nom_normalise} "

    correspondances: list[dict] = []

    for patient in patients:
        alias_patient = patient.get(
            "alias_fichiers",
            [],
        )

        correspondance_trouvee = False

        for alias in alias_patient:
            alias_normalise = normaliser_texte(
                str(alias)
            )

            if not alias_normalise:
                continue

            alias_encadre = f" {alias_normalise} "

            if alias_encadre in nom_encadre:
                correspondance_trouvee = True
                break

        if correspondance_trouvee:
            correspondances.append(patient)

    if len(correspondances) == 1:
        return correspondances[0], correspondances

    return None, correspondances


# =========================================================
# DÉTECTION DU VRAI FORMAT DE L'IMAGE
# =========================================================

def detecter_format_reel(
    image_path: Path,
) -> tuple[str, str]:
    """
    Détecte le vrai format interne, indépendamment
    de l'extension du fichier.

    Un HEIC renommé en .jpg sera donc détecté comme HEIF.
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
            "Le format réel de l'image ne peut pas être "
            f"déterminé : {image_path.name}"
        )

    extension_reelle = EXTENSIONS_PAR_FORMAT.get(
        format_reel
    )

    if extension_reelle is None:
        raise ValueError(
            f"Format réel non pris en charge : {format_reel}"
        )

    return format_reel, extension_reelle


# =========================================================
# EMPREINTES ET DOUBLONS
# =========================================================

def calculer_sha256(fichier: Path) -> str:
    """
    Calcule l'empreinte SHA-256 d'un fichier.
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
    Vérifie que deux fichiers sont strictement identiques.
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


def obtenir_destination_unique(
    destination: Path,
) -> Path:
    """
    Évite d'écraser un fichier différent portant déjà
    le même nom.

    Exemple :
    note.heic → note_2.heic
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


# =========================================================
# COPIE DE L'ORIGINAL DANS LE DOSSIER PATIENT
# =========================================================

def copier_dans_dossier_patient(
    fichier_source: Path,
    patient: dict,
) -> tuple[Path, bool, str]:
    """
    Copie l'image dans notes_originales en utilisant
    l'extension correspondant à son vrai format.

    Retourne :
    - le chemin de l'image dans le dossier patient ;
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

    destination_initiale = (
        dossier_notes
        / f"{fichier_source.stem}{extension_reelle}"
    )

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


# =========================================================
# CONVERSION TEMPORAIRE DE L'IMAGE POUR L'API
# =========================================================

def convertir_image_en_data_url(
    image_path: Path,
) -> str:
    """
    Corrige l'orientation, réduit la résolution et convertit
    temporairement l'image en JPEG en mémoire.

    L'original n'est jamais modifié.
    """

    try:
        with Image.open(image_path) as image:
            print(
                f"    Format réel : {image.format}"
            )
            print(
                f"    Dimensions originales : {image.size}"
            )

            image = ImageOps.exif_transpose(
                image
            )

            image.thumbnail(
                MAX_IMAGE_SIZE,
                Image.Resampling.LANCZOS,
            )

            print(
                f"    Dimensions envoyées : {image.size}"
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
            "Impossible de préparer l'image pour l'API : "
            f"{image_path}\n"
            f"Détail : {erreur}"
        ) from erreur

    if not donnees_jpeg:
        raise ValueError(
            "La conversion a produit une image vide."
        )

    taille_ko = len(donnees_jpeg) / 1024

    print(
        f"    Taille envoyée : {taille_ko:.1f} Ko"
    )

    contenu_base64 = base64.b64encode(
        donnees_jpeg
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        f"{contenu_base64}"
    )


# =========================================================
# CHEMINS DES FICHIERS PRODUITS
# =========================================================

def obtenir_chemin_transcription(
    image_path: Path,
) -> Path:
    """
    Retourne le chemin du fichier de transcription.
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


def obtenir_chemin_donnees_cliniques(
    image_path: Path,
) -> Path:
    """
    Retourne le chemin du fichier JSON clinique.
    """

    dossier_patient = image_path.parent.parent

    dossier_donnees = (
        dossier_patient
        / "donnees_cliniques"
    )

    dossier_donnees.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        dossier_donnees
        / f"{image_path.stem}.json"
    )


# =========================================================
# VÉRIFICATION DES FICHIERS EXISTANTS
# =========================================================

def transcription_valide(
    transcription_path: Path,
) -> bool:
    """
    Une transcription est considérée valide lorsqu'elle
    existe et contient du texte.
    """

    if not transcription_path.exists():
        return False

    if not transcription_path.is_file():
        return False

    try:
        contenu = transcription_path.read_text(
            encoding="utf-8-sig"
        ).strip()

    except Exception:
        return False

    return bool(contenu)


def donnees_cliniques_valides(
    json_path: Path,
    transcription_path: Path,
) -> bool:
    """
    Vérifie que le JSON :
    - existe ;
    - respecte le schéma Pydantic ;
    - n'est pas plus ancien que la transcription.

    Si la transcription est corrigée manuellement après
    l'extraction, le JSON sera donc régénéré.
    """

    if not json_path.exists():
        return False

    if not json_path.is_file():
        return False

    try:
        contenu = json_path.read_text(
            encoding="utf-8-sig"
        )

        DonneesCliniques.model_validate_json(
            contenu
        )

    except Exception:
        return False

    if transcription_path.exists():
        date_json = json_path.stat().st_mtime
        date_transcription = (
            transcription_path.stat().st_mtime
        )

        if date_transcription > date_json:
            return False

    return True


# =========================================================
# TRANSCRIPTION OCR
# =========================================================

def transcrire_image(
    client: OpenAI,
    image_path: Path,
):
    """
    Envoie l'image à GPT-5.6 Terra et demande une
    transcription fidèle, sans analyse clinique.
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

        max_output_tokens=MAX_OUTPUT_TOKENS_OCR,

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
                            "- Ne résume pas.\n"
                            "- N'analyse pas le contenu.\n"
                            "- N'interprète pas les informations.\n"
                            "- Ne complète aucune information absente.\n"
                            "- N'invente aucun mot.\n"
                            "- Ne corrige pas les formulations.\n"
                            "- Conserve les accents tels qu'ils sont lus.\n"
                            "- Conserve autant que possible les titres, "
                            "les paragraphes, les listes, la ponctuation "
                            "et les symboles présents sur la note.\n"
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


def enregistrer_transcription(
    transcription_path: Path,
    transcription: str,
) -> None:
    """
    Enregistre la transcription en UTF-8.
    """

    transcription_path.write_text(
        transcription,
        encoding="utf-8",
    )


def lire_transcription(
    transcription_path: Path,
) -> str:
    """
    Lit une transcription existante.
    """

    if not transcription_valide(
        transcription_path
    ):
        raise ValueError(
            "La transcription est absente ou vide : "
            f"{transcription_path}"
        )

    return transcription_path.read_text(
        encoding="utf-8-sig"
    ).strip()


# =========================================================
# EXTRACTION CLINIQUE STRUCTURÉE
# =========================================================

def extraire_donnees_cliniques(
    client: OpenAI,
    transcription: str,
):
    """
    Transforme la transcription en données cliniques
    structurées, sans analyse fonctionnelle.
    """

    prompt_systeme = (
        "Tu extrais des informations structurées à partir "
        "d'une transcription de notes de séance de "
        "psychothérapie.\n\n"

        "Tu dois rester strictement fidèle au texte source.\n\n"

        "Règles impératives :\n"
        "- N'invente aucune information.\n"
        "- Ne pose aucun diagnostic.\n"
        "- Ne produis aucune analyse fonctionnelle.\n"
        "- Ne déduis aucune émotion, cognition ou intention.\n"
        "- Ne crée aucun lien causal absent de la note.\n"
        "- Ne transforme pas une possibilité en certitude.\n"
        "- Ne transforme pas une crainte en événement survenu.\n"
        "- Ne transforme pas une proposition en tâche réalisée.\n"
        "- Utilise des formulations courtes et proches du texte.\n"
        "- Utilise une liste vide si une catégorie est absente.\n"
        "- Normalise la date au format AAAA-MM-JJ uniquement "
        "si elle est explicitement identifiable.\n"
        "- Mets date_seance à null si la date est absente "
        "ou incertaine.\n"
        "- Une émotion est un état affectif, pas une pensée.\n"
        "- Une cognition est une pensée, une anticipation, "
        "une croyance ou une interprétation.\n"
        "- Un évitement doit être explicitement indiqué.\n"
        "- Les interventions concernent les exercices ou "
        "stratégies proposés ou réalisés dans le cadre "
        "thérapeutique.\n"
        "- Les tâches interséances concernent uniquement ce "
        "qui est explicitement demandé après la séance.\n"
        "- Évite les doublons inutiles entre les catégories.\n"
        "- Un même élément peut apparaître dans interventions "
        "et taches_interseances seulement si le texte établit "
        "clairement les deux fonctions.\n"
        "- Place les passages [illisible] et [mot incertain] "
        "dans elements_incertains.\n"
        "- En cas de doute, place l'information dans "
        "elements_incertains plutôt que de l'affirmer."
    )

    prompt_utilisateur = (
        "Voici la transcription à structurer :\n\n"
        "----- DÉBUT DE LA TRANSCRIPTION -----\n"
        f"{transcription}\n"
        "----- FIN DE LA TRANSCRIPTION -----"
    )

    reponse = client.responses.parse(
        model=MODEL,

        reasoning={
            "effort": "none",
        },

        store=False,

        max_output_tokens=MAX_OUTPUT_TOKENS_EXTRACTION,

        input=[
            {
                "role": "system",
                "content": prompt_systeme,
            },
            {
                "role": "user",
                "content": prompt_utilisateur,
            },
        ],

        text_format=DonneesCliniques,
    )

    if getattr(
        reponse,
        "status",
        None,
    ) == "incomplete":
        details = getattr(
            reponse,
            "incomplete_details",
            None,
        )

        raise RuntimeError(
            "La réponse d'extraction est incomplète. "
            f"Détails : {details}"
        )

    donnees = reponse.output_parsed

    if donnees is None:
        raise RuntimeError(
            "Le modèle n'a pas retourné de données "
            "cliniques structurées valides."
        )

    return donnees, reponse


def enregistrer_donnees_cliniques(
    donnees: DonneesCliniques,
    json_path: Path,
) -> None:
    """
    Enregistre les données cliniques dans un JSON lisible.
    """

    contenu = donnees.model_dump(
        mode="json"
    )

    json_path.write_text(
        json.dumps(
            contenu,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


# =========================================================
# UTILISATION DE L'API
# =========================================================

def obtenir_utilisation(
    reponse,
) -> tuple[int, int, int]:
    """
    Récupère les tokens indiqués par l'API.
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


def ajouter_utilisation(
    statistiques: dict,
    categorie: str,
    reponse,
) -> tuple[int, int, int]:
    """
    Ajoute les tokens aux totaux globaux et aux sous-totaux
    OCR ou extraction.
    """

    input_tokens, output_tokens, total_tokens = (
        obtenir_utilisation(reponse)
    )

    statistiques["api_input_tokens"] += input_tokens
    statistiques["api_output_tokens"] += output_tokens
    statistiques["api_total_tokens"] += total_tokens

    statistiques[
        f"{categorie}_input_tokens"
    ] += input_tokens

    statistiques[
        f"{categorie}_output_tokens"
    ] += output_tokens

    statistiques[
        f"{categorie}_total_tokens"
    ] += total_tokens

    return (
        input_tokens,
        output_tokens,
        total_tokens,
    )


# =========================================================
# LISTE DES IMAGES À TRAITER
# =========================================================

def obtenir_images_entree() -> list[Path]:
    """
    Retourne les images présentes dans entree.
    """

    ENTREE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    images = [
        fichier
        for fichier in ENTREE_DIR.iterdir()
        if fichier.is_file()
        and fichier.suffix.lower()
        in EXTENSIONS_ENTREE
    ]

    return sorted(
        images,
        key=lambda fichier: fichier.name.lower(),
    )


# =========================================================
# TRAITEMENT COMPLET D'UNE IMAGE
# =========================================================

def traiter_image(
    fichier_source: Path,
    patients: list[dict],
    cache_client: dict[str, OpenAI],
    statistiques: dict,
) -> None:
    """
    Exécute toute la chaîne pour une image :

    1. Identification du patient
    2. Archivage de l'original
    3. Transcription si nécessaire
    4. Extraction clinique si nécessaire
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
            statistiques["non_identifies"] += 1

            print(
                "Résultat : patient non identifié."
            )
            print(
                "Le fichier reste dans entree et "
                "n'est pas copié."
            )

            return

        statistiques["ambigus"] += 1

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

        return

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
        statistiques["photos_copiees"] += 1

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

    transcription_path = (
        obtenir_chemin_transcription(
            image_patient
        )
    )

    json_path = (
        obtenir_chemin_donnees_cliniques(
            image_patient
        )
    )

    appel_effectue = False

    # -----------------------------------------------------
    # ÉTAPE 1 : TRANSCRIPTION
    # -----------------------------------------------------

    if transcription_valide(
        transcription_path
    ):
        print(
            "\nTranscription valide déjà existante."
        )
        print(
            f"Fichier réutilisé : {transcription_path}"
        )

    else:
        if transcription_path.exists():
            print(
                "\nLa transcription existante est vide "
                "ou illisible. Elle va être recréée."
            )

        else:
            print(
                "\nAucune transcription existante."
            )

        print(
            "Préparation et envoi de l'image à "
            "GPT-5.6 Terra..."
        )

        client = obtenir_client(
            cache_client
        )

        transcription, reponse_ocr = (
            transcrire_image(
                client,
                image_patient,
            )
        )

        enregistrer_transcription(
            transcription_path,
            transcription,
        )

        statistiques[
            "transcriptions_creees"
        ] += 1

        appel_effectue = True

        (
            input_tokens,
            output_tokens,
            total_tokens,
        ) = ajouter_utilisation(
            statistiques,
            "ocr",
            reponse_ocr,
        )

        print("\n--- TRANSCRIPTION ---\n")
        print(transcription)

        print("\n--- UTILISATION OCR ---")
        print(
            f"Tokens d'entrée : {input_tokens}"
        )
        print(
            f"Tokens de sortie : {output_tokens}"
        )
        print(
            f"Tokens totaux : {total_tokens}"
        )

        print("\n--- ENREGISTREMENT OCR ---")
        print(
            f"Transcription créée : "
            f"{transcription_path}"
        )

    # -----------------------------------------------------
    # ÉTAPE 2 : EXTRACTION CLINIQUE
    # -----------------------------------------------------

    transcription = lire_transcription(
        transcription_path
    )

    if donnees_cliniques_valides(
        json_path,
        transcription_path,
    ):
        print(
            "\nDonnées cliniques valides déjà existantes."
        )
        print(
            f"Fichier réutilisé : {json_path}"
        )

    else:
        if json_path.exists():
            print(
                "\nLe JSON clinique existant est invalide "
                "ou plus ancien que la transcription."
            )
            print(
                "Il va être régénéré."
            )

        else:
            print(
                "\nAucune extraction clinique existante."
            )

        print(
            "Extraction clinique structurée avec "
            "GPT-5.6 Terra..."
        )

        client = obtenir_client(
            cache_client
        )

        donnees, reponse_extraction = (
            extraire_donnees_cliniques(
                client,
                transcription,
            )
        )

        enregistrer_donnees_cliniques(
            donnees,
            json_path,
        )

        statistiques[
            "extractions_creees"
        ] += 1

        appel_effectue = True

        (
            input_tokens,
            output_tokens,
            total_tokens,
        ) = ajouter_utilisation(
            statistiques,
            "extraction",
            reponse_extraction,
        )

        donnees_affichage = donnees.model_dump(
            mode="json"
        )

        print(
            "\n--- DONNÉES CLINIQUES ---\n"
        )

        print(
            json.dumps(
                donnees_affichage,
                ensure_ascii=False,
                indent=2,
            )
        )

        print(
            "\n--- UTILISATION EXTRACTION ---"
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

        print(
            "\n--- ENREGISTREMENT EXTRACTION ---"
        )
        print(
            f"JSON clinique créé : {json_path}"
        )

    if not appel_effectue:
        statistiques[
            "deja_complets"
        ] += 1

        print(
            "\nTraitement déjà complet."
        )
        print(
            "Aucun nouvel appel API n'a été effectué."
        )

    else:
        statistiques[
            "traitements_modifies"
        ] += 1

        print(
            "\nTraitement terminé pour cette image."
        )


# =========================================================
# STATISTIQUES
# =========================================================

def creer_statistiques() -> dict:
    """
    Crée les compteurs du programme.
    """

    return {
        "photos_copiees": 0,
        "transcriptions_creees": 0,
        "extractions_creees": 0,
        "traitements_modifies": 0,
        "deja_complets": 0,
        "non_identifies": 0,
        "ambigus": 0,
        "erreurs": 0,

        "ocr_input_tokens": 0,
        "ocr_output_tokens": 0,
        "ocr_total_tokens": 0,

        "extraction_input_tokens": 0,
        "extraction_output_tokens": 0,
        "extraction_total_tokens": 0,

        "api_input_tokens": 0,
        "api_output_tokens": 0,
        "api_total_tokens": 0,
    }


def afficher_resume(
    statistiques: dict,
) -> None:
    """
    Affiche le résumé global.
    """

    print("\n" + "=" * 70)
    print("RÉSUMÉ DU TRAITEMENT")
    print("=" * 70)

    print(
        f"Photos nouvellement copiées : "
        f"{statistiques['photos_copiees']}"
    )

    print(
        f"Transcriptions créées : "
        f"{statistiques['transcriptions_creees']}"
    )

    print(
        f"Extractions cliniques créées : "
        f"{statistiques['extractions_creees']}"
    )

    print(
        f"Fichiers déjà complètement traités : "
        f"{statistiques['deja_complets']}"
    )

    print(
        f"Patients non identifiés : "
        f"{statistiques['non_identifies']}"
    )

    print(
        f"Identifications ambiguës : "
        f"{statistiques['ambigus']}"
    )

    print(
        f"Erreurs : "
        f"{statistiques['erreurs']}"
    )

    print("\n--- OCR ---")

    print(
        f"Tokens d'entrée : "
        f"{statistiques['ocr_input_tokens']}"
    )

    print(
        f"Tokens de sortie : "
        f"{statistiques['ocr_output_tokens']}"
    )

    print(
        f"Tokens totaux : "
        f"{statistiques['ocr_total_tokens']}"
    )

    print("\n--- EXTRACTION CLINIQUE ---")

    print(
        f"Tokens d'entrée : "
        f"{statistiques['extraction_input_tokens']}"
    )

    print(
        f"Tokens de sortie : "
        f"{statistiques['extraction_output_tokens']}"
    )

    print(
        f"Tokens totaux : "
        f"{statistiques['extraction_total_tokens']}"
    )

    print("\n--- TOTAL API ---")

    print(
        f"Tokens d'entrée : "
        f"{statistiques['api_input_tokens']}"
    )

    print(
        f"Tokens de sortie : "
        f"{statistiques['api_output_tokens']}"
    )

    print(
        f"Tokens totaux : "
        f"{statistiques['api_total_tokens']}"
    )

    print(
        "\nLes fichiers originaux restent conservés "
        "dans entree."
    )


# =========================================================
# PROGRAMME PRINCIPAL
# =========================================================

def main() -> None:
    print("=" * 70)
    print(
        "PSYCHO IA — CLASSEMENT, TRANSCRIPTION "
        "ET EXTRACTION CLINIQUE"
    )
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

        statistiques = creer_statistiques()

        # Le client OpenAI n'est chargé que lorsqu'un appel
        # est réellement nécessaire.
        cache_client: dict[str, OpenAI] = {}

        for image in images:
            try:
                traiter_image(
                    image,
                    patients,
                    cache_client,
                    statistiques,
                )

            except Exception as erreur:
                statistiques["erreurs"] += 1

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

        afficher_resume(
            statistiques
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