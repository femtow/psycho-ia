from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Literal
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
# HEIC / HEIF
# =========================================================

register_heif_opener()


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ENTREE_DIR = BASE_DIR / "entree"
PATIENTS_DIR = BASE_DIR / "patients_test"
ENV_PATH = BASE_DIR / ".env"

MODEL_OCR = "gpt-5.6-sol"
MODEL_EXTRACTION = "gpt-5.6-terra"

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
MAX_OUTPUT_TOKENS_EXTRACTION = 2500

SCHEMA_VERSION = "2.0"


# =========================================================
# SCHÉMA CLINIQUE V2
# =========================================================

class ElementContextualise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contenu: str = Field(
        description=(
            "Contenu clinique proche de la formulation source."
        )
    )

    contexte: str | None = Field(
        description=(
            "Situation ou contexte nécessaire pour comprendre "
            "l'élément lorsqu'il est lu isolément. Null si aucun "
            "contexte utile n'est disponible."
        )
    )


class EmotionContextualisee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contenu: str = Field(
        description=(
            "Émotion explicitement présente dans la note."
        )
    )

    contexte: str | None = Field(
        description=(
            "Situation dans laquelle l'émotion apparaît. "
            "Null si elle n'est pas identifiable."
        )
    )

    intensite: str | None = Field(
        description=(
            "Intensité explicitement indiquée, par exemple 7/10. "
            "Null si aucune intensité n'est indiquée."
        )
    )


class CognitionContextualisee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contenu: str = Field(
        description=(
            "Pensée, anticipation, croyance ou interprétation "
            "en conservant autant que possible sa formulation source."
        )
    )

    contexte: str | None = Field(
        description=(
            "Situation permettant de comprendre la cognition "
            "lorsqu'elle est lue isolément."
        )
    )

    referent_contextuel: str | None = Field(
        description=(
            "Personne ou objet auquel semble renvoyer un pronom "
            "dans la cognition, lorsque le contexte permet de "
            "l'identifier. Null si aucun référent n'est utile "
            "ou suffisamment identifiable."
        )
    )

    referent_explicitement_identifie: bool | None = Field(
        description=(
            "True si le référent est explicitement identifié dans "
            "la formulation de la cognition elle-même. False si le "
            "référent est seulement compris grâce au contexte. "
            "Null s'il n'y a pas de référent contextuel."
        )
    )


class DonneesCliniques(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.0"] = Field(
        description="Version du schéma clinique."
    )

    date_seance: date | None = Field(
        description=(
            "Date explicite de la séance au format AAAA-MM-JJ. "
            "Null si absente ou incertaine."
        )
    )

    faits_rapportes: list[str] = Field(
        description=(
            "Faits, événements, symptômes ou circonstances "
            "explicitement rapportés qui ne sont pas déjà mieux "
            "représentés dans une autre catégorie."
        )
    )

    emotions: list[EmotionContextualisee] = Field(
        description=(
            "Émotions explicitement présentes avec leur contexte "
            "et leur intensité lorsqu'ils sont disponibles."
        )
    )

    cognitions: list[CognitionContextualisee] = Field(
        description=(
            "Pensées, anticipations, croyances ou interprétations "
            "avec le contexte nécessaire pour les comprendre."
        )
    )

    comportements: list[ElementContextualise] = Field(
        description=(
            "Comportements observables explicitement présents."
        )
    )

    evitements: list[ElementContextualise] = Field(
        description=(
            "Évitements explicitement présents."
        )
    )

    interventions: list[str] = Field(
        description=(
            "Interventions ou exercices thérapeutiques proposés "
            "ou réalisés."
        )
    )

    taches_interseances: list[str] = Field(
        description=(
            "Tâches explicitement demandées entre les séances."
        )
    )

    elements_incertains: list[str] = Field(
        description=(
            "Éléments ambigus ou incertains. Les lignes contenant "
            "des marqueurs OCR d'incertitude seront également "
            "ajoutées automatiquement par Python."
        )
    )


# =========================================================
# CLIENT OPENAI
# =========================================================

def charger_client() -> OpenAI:
    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f"Fichier .env introuvable : {ENV_PATH}"
        )

    load_dotenv(ENV_PATH)

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY est absente ou vide dans .env."
        )

    return OpenAI(api_key=api_key)


def obtenir_client(
    cache_client: dict[str, OpenAI],
) -> OpenAI:

    if "client" not in cache_client:
        cache_client["client"] = charger_client()

    return cache_client["client"]


# =========================================================
# OUTILS TEXTE
# =========================================================

def normaliser_texte(texte: str) -> str:
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


def cle_dedoublonnage(texte: str) -> str:
    """
    Normalisation légère utilisée uniquement pour supprimer
    des doublons stricts ou quasi stricts.
    """

    return " ".join(
        normaliser_texte(texte).split()
    )


# =========================================================
# GESTION DÉTERMINISTE DE L'INCERTITUDE OCR
# =========================================================

def ligne_contient_incertitude(
    ligne: str,
) -> bool:
    """
    Détecte les marqueurs produits par notre OCR.
    """

    ligne_minuscule = ligne.lower()

    return (
        "[illisible]" in ligne_minuscule
        or "[mot incertain" in ligne_minuscule
    )


def separer_transcription_certaine_et_incertaine(
    transcription: str,
) -> tuple[str, list[str]]:
    """
    Règle volontairement conservatrice :

    toute ligne contenant un marqueur OCR d'incertitude
    est retirée du texte utilisé pour produire les catégories
    certaines.

    La ligne originale reste disponible dans
    elements_incertains.

    Ainsi :
    "Sommeil difficile depuis [mot incertain : quelques] jours"

    ne peut pas devenir :
    "Sommeil difficile depuis quelques jours"

    comme fait certain.
    """

    lignes_certaines: list[str] = []
    lignes_incertaines: list[str] = []

    for ligne in transcription.splitlines():
        ligne_nettoyee = ligne.strip()

        if not ligne_nettoyee:
            lignes_certaines.append(ligne)
            continue

        if ligne_contient_incertitude(
            ligne_nettoyee
        ):
            lignes_incertaines.append(
                ligne_nettoyee
            )
        else:
            lignes_certaines.append(ligne)

    texte_certain = "\n".join(
        lignes_certaines
    ).strip()

    return (
        texte_certain,
        lignes_incertaines,
    )


def ajouter_incertitudes_deterministes(
    donnees: DonneesCliniques,
    lignes_incertaines: list[str],
) -> DonneesCliniques:
    """
    Les lignes incertaines détectées par Python sont ajoutées
    quoi qu'ait répondu le modèle.
    """

    resultat: list[str] = []
    deja_vus: set[str] = set()

    for element in (
        lignes_incertaines
        + donnees.elements_incertains
    ):
        cle = cle_dedoublonnage(element)

        if not cle:
            continue

        if cle in deja_vus:
            continue

        deja_vus.add(cle)
        resultat.append(element)

    return donnees.model_copy(
        update={
            "elements_incertains": resultat
        }
    )


# =========================================================
# DÉDOUBLONNAGE SIMPLE
# =========================================================

def dedoublonner_textes(
    elements: list[str],
) -> list[str]:

    resultat: list[str] = []
    deja_vus: set[str] = set()

    for element in elements:
        cle = cle_dedoublonnage(element)

        if not cle:
            continue

        if cle in deja_vus:
            continue

        deja_vus.add(cle)
        resultat.append(element)

    return resultat


def dedoublonner_donnees(
    donnees: DonneesCliniques,
) -> DonneesCliniques:
    """
    Retire uniquement les doublons déterministes.

    On ne tente PAS de supprimer automatiquement deux phrases
    simplement parce qu'elles semblent sémantiquement proches.
    """

    emotions: list[EmotionContextualisee] = []
    cles_emotions: set[tuple] = set()

    for element in donnees.emotions:
        cle = (
            cle_dedoublonnage(element.contenu),
            cle_dedoublonnage(element.contexte or ""),
            cle_dedoublonnage(element.intensite or ""),
        )

        if cle not in cles_emotions:
            cles_emotions.add(cle)
            emotions.append(element)

    cognitions: list[CognitionContextualisee] = []
    cles_cognitions: set[tuple] = set()

    for element in donnees.cognitions:
        cle = (
            cle_dedoublonnage(element.contenu),
            cle_dedoublonnage(element.contexte or ""),
            cle_dedoublonnage(
                element.referent_contextuel or ""
            ),
        )

        if cle not in cles_cognitions:
            cles_cognitions.add(cle)
            cognitions.append(element)

    comportements: list[ElementContextualise] = []
    cles_comportements: set[tuple] = set()

    for element in donnees.comportements:
        cle = (
            cle_dedoublonnage(element.contenu),
            cle_dedoublonnage(element.contexte or ""),
        )

        if cle not in cles_comportements:
            cles_comportements.add(cle)
            comportements.append(element)

    evitements: list[ElementContextualise] = []
    cles_evitements: set[tuple] = set()

    for element in donnees.evitements:
        cle = (
            cle_dedoublonnage(element.contenu),
            cle_dedoublonnage(element.contexte or ""),
        )

        if cle not in cles_evitements:
            cles_evitements.add(cle)
            evitements.append(element)

    return donnees.model_copy(
        update={
            "faits_rapportes": dedoublonner_textes(
                donnees.faits_rapportes
            ),
            "emotions": emotions,
            "cognitions": cognitions,
            "comportements": comportements,
            "evitements": evitements,
            "interventions": dedoublonner_textes(
                donnees.interventions
            ),
            "taches_interseances": dedoublonner_textes(
                donnees.taches_interseances
            ),
        }
    )


# =========================================================
# PROFILS PATIENTS
# =========================================================

def charger_patients() -> list[dict]:
    if not PATIENTS_DIR.exists():
        raise FileNotFoundError(
            f"Dossier patients introuvable : {PATIENTS_DIR}"
        )

    patients: list[dict] = []

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
                f"JSON invalide : {profil_path}\n"
                f"{erreur}"
            ) from erreur

        if not profil.get("identifiant"):
            raise ValueError(
                f"Identifiant absent : {profil_path}"
            )

        profil["dossier"] = profil_path.parent

        patients.append(profil)

    if not patients:
        raise RuntimeError(
            "Aucun profil patient trouvé."
        )

    return patients


# =========================================================
# IDENTIFICATION PATIENT
# =========================================================

def identifier_patient_depuis_nom(
    fichier: Path,
    patients: list[dict],
) -> tuple[dict | None, list[dict]]:

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

        correspondance = False

        for alias in alias_patient:
            alias_normalise = normaliser_texte(
                str(alias)
            )

            if not alias_normalise:
                continue

            if (
                f" {alias_normalise} "
                in nom_encadre
            ):
                correspondance = True
                break

        if correspondance:
            correspondances.append(patient)

    if len(correspondances) == 1:
        return correspondances[0], correspondances

    return None, correspondances


# =========================================================
# FORMAT IMAGE
# =========================================================

def detecter_format_reel(
    image_path: Path,
) -> tuple[str, str]:

    try:
        with Image.open(image_path) as image:
            format_reel = (
                image.format or ""
            ).upper()

    except Exception as erreur:
        raise ValueError(
            f"Image invalide : {image_path.name}\n"
            f"{erreur}"
        ) from erreur

    extension = EXTENSIONS_PAR_FORMAT.get(
        format_reel
    )

    if extension is None:
        raise ValueError(
            f"Format non pris en charge : {format_reel}"
        )

    return format_reel, extension


# =========================================================
# SHA-256 / DOUBLONS
# =========================================================

def calculer_sha256(
    fichier: Path,
) -> str:

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

    if not fichier_a.exists():
        return False

    if not fichier_b.exists():
        return False

    if (
        fichier_a.stat().st_size
        != fichier_b.stat().st_size
    ):
        return False

    return (
        calculer_sha256(fichier_a)
        == calculer_sha256(fichier_b)
    )


def obtenir_destination_unique(
    destination: Path,
) -> Path:

    if not destination.exists():
        return destination

    compteur = 2

    while True:
        nouvelle_destination = (
            destination.with_name(
                f"{destination.stem}_{compteur}"
                f"{destination.suffix}"
            )
        )

        if not nouvelle_destination.exists():
            return nouvelle_destination

        compteur += 1


# =========================================================
# ARCHIVAGE PHOTO
# =========================================================

def copier_dans_dossier_patient(
    fichier_source: Path,
    patient: dict,
) -> tuple[Path, bool, str]:

    format_reel, extension_reelle = (
        detecter_format_reel(
            fichier_source
        )
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

    return (
        destination,
        True,
        format_reel,
    )


# =========================================================
# PRÉPARATION IMAGE POUR API
# =========================================================

def convertir_image_en_data_url(
    image_path: Path,
) -> str:

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
            f"Impossible de préparer l'image : {erreur}"
        ) from erreur

    print(
        f"    Taille envoyée : "
        f"{len(donnees_jpeg) / 1024:.1f} Ko"
    )

    contenu_base64 = base64.b64encode(
        donnees_jpeg
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        f"{contenu_base64}"
    )


# =========================================================
# CHEMINS PRODUITS
# =========================================================

def obtenir_chemin_transcription(
    image_path: Path,
) -> Path:

    dossier = (
        image_path.parent.parent
        / "transcriptions"
    )

    dossier.mkdir(
        parents=True,
        exist_ok=True,
    )

    return dossier / f"{image_path.stem}.txt"


def obtenir_chemin_donnees_cliniques(
    image_path: Path,
) -> Path:

    dossier = (
        image_path.parent.parent
        / "donnees_cliniques"
    )

    dossier.mkdir(
        parents=True,
        exist_ok=True,
    )

    return dossier / f"{image_path.stem}.json"


# =========================================================
# VALIDITÉ DES PRODUITS EXISTANTS
# =========================================================

def transcription_valide(
    transcription_path: Path,
) -> bool:

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
    Les anciens JSON V1 seront automatiquement considérés
    comme invalides puisqu'ils n'ont pas schema_version=2.0
    et n'utilisent pas le nouveau schéma contextualisé.
    """

    if not json_path.is_file():
        return False

    try:
        contenu = json_path.read_text(
            encoding="utf-8-sig"
        )

        donnees = (
            DonneesCliniques.model_validate_json(
                contenu
            )
        )

        if donnees.schema_version != SCHEMA_VERSION:
            return False

    except Exception:
        return False

    if transcription_path.exists():
        if (
            transcription_path.stat().st_mtime
            > json_path.stat().st_mtime
        ):
            return False

    return True


# =========================================================
# OCR
# =========================================================

def transcrire_image(
    client: OpenAI,
    image_path: Path,
):

    image_data_url = convertir_image_en_data_url(
        image_path
    )

    reponse = client.responses.create(
        model=MODEL_OCR,

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
                            "- Conserve les titres, paragraphes, "
                            "listes, ponctuation et symboles.\n"
                            "- Écris [illisible] lorsqu'un passage "
                            "ne peut pas être lu avec suffisamment "
                            "de certitude.\n"
                            "- Écris [mot incertain : proposition] "
                            "lorsqu'un mot semble probable mais reste "
                            "incertain.\n"
                            "- Retourne uniquement la transcription."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url,
                        "detail": "original",
                    },
                ],
            }
        ],
    )

    transcription = reponse.output_text.strip()

    if not transcription:
        raise RuntimeError(
            "Aucune transcription retournée."
        )

    return transcription, reponse


def enregistrer_transcription(
    transcription_path: Path,
    transcription: str,
) -> None:

    transcription_path.write_text(
        transcription,
        encoding="utf-8",
    )


def lire_transcription(
    transcription_path: Path,
) -> str:

    if not transcription_valide(
        transcription_path
    ):
        raise ValueError(
            f"Transcription absente ou vide : "
            f"{transcription_path}"
        )

    return transcription_path.read_text(
        encoding="utf-8-sig"
    ).strip()


# =========================================================
# EXTRACTION CLINIQUE V2
# =========================================================

def extraire_donnees_cliniques(
    client: OpenAI,
    transcription: str,
):
    """
    Les lignes comportant une incertitude OCR ne sont PAS
    fournies au modèle pour les catégories certaines.

    C'est Python, ensuite, qui les ajoute à
    elements_incertains.
    """

    (
        transcription_certaine,
        lignes_incertaines,
    ) = separer_transcription_certaine_et_incertaine(
        transcription
    )

    prompt_systeme = (
        "Tu structures des notes de séance de psychothérapie.\n\n"

        "Tu ne disposes ici que des lignes considérées comme "
        "suffisamment certaines par le système OCR.\n\n"

        "Règles impératives :\n"

        f"- schema_version doit être exactement "
        f"\"{SCHEMA_VERSION}\".\n"

        "- N'invente aucune information.\n"
        "- Ne pose aucun diagnostic.\n"
        "- Ne produis aucune analyse fonctionnelle.\n"
        "- Ne crée aucun lien causal absent du texte.\n"
        "- Ne transforme jamais une hypothèse en fait.\n"
        "- Ne transforme jamais une crainte en événement survenu.\n"
        "- Une information doit apparaître une seule fois dans "
        "la catégorie clinique qui la représente le mieux.\n"
        "- Ne crée pas une deuxième entrée uniquement pour "
        "paraphraser ou expliciter la première.\n\n"

        "RÈGLE DE CONTEXTE :\n"
        "- Le champ contenu conserve la formulation clinique "
        "elle-même.\n"
        "- N'altère pas contenu uniquement pour résoudre un "
        "pronom ou ajouter du contexte.\n"
        "- Utilise contexte pour conserver les informations "
        "nécessaires à la compréhension isolée de l'élément.\n\n"

        "EXEMPLE :\n"
        "Source : 'Dispute avec son responsable lundi. "
        "Pensée : « il ne me respecte jamais ».'\n"
        "La cognition doit conserver comme contenu : "
        "'Il ne me respecte jamais'.\n"
        "Son contexte peut être : "
        "'Dispute avec son responsable lundi'.\n"
        "referent_contextuel peut être 'responsable'.\n"
        "referent_explicitement_identifie doit être false, "
        "car le mot responsable n'est pas contenu dans la "
        "cognition elle-même.\n"
        "Ne crée surtout pas une deuxième cognition du type "
        "'Le responsable ne le respecte jamais'.\n\n"

        "ÉMOTIONS :\n"
        "- Ne déduis jamais une émotion.\n"
        "- Sépare son contenu, son contexte et son intensité.\n\n"

        "COGNITIONS :\n"
        "- Une cognition est une pensée, anticipation, croyance "
        "ou interprétation explicitement présente.\n"
        "- Un référent contextuel peut être renseigné lorsque "
        "le contexte rend raisonnablement clair à qui renvoie "
        "un pronom.\n"
        "- Cela ne doit jamais modifier la formulation source.\n\n"

        "COMPORTEMENTS ET ÉVITEMENTS :\n"
        "- Conserve les comportements observables explicitement rapportés "
        "lorsqu'ils sont cliniquement pertinents, notamment les actions, "
        "leur fréquence ou leur répétition.\n"
        "- Une information globale telle que 'a pris le tram trois fois "
        "cette semaine' doit être conservée comme comportement même si "
        "certains trajets sont décrits plus précisément ailleurs.\n"
        "- Un comportement global et un évitement ponctuel ne sont pas "
        "des doublons s'ils décrivent deux informations distinctes.\n"
        "- En revanche, ne duplique pas exactement le même acte dans "
        "comportements et evitements lorsque l'acte lui-même constitue "
        "l'évitement.\n"
        "- Ajoute le contexte nécessaire pour comprendre l'action "
        "lorsqu'elle est lue isolément.\n"
        "- Un évitement doit être explicitement présent.\n\n"

        "INTERVENTIONS :\n"
        "- Seulement les interventions ou exercices explicitement "
        "proposés ou réalisés dans le cadre thérapeutique.\n\n"

        "TÂCHES INTERSÉANCES :\n"
        "- Classe comme tâche interséance une action ou un exercice "
        "explicitement destiné à être réalisé après la séance.\n"
        "- Une fréquence ou une échéance future explicite, par exemple "
        "'trois fois cette semaine', 'chaque jour', 'avant la prochaine "
        "séance' ou 'd'ici la prochaine séance', constitue un indice "
        "suffisant qu'il s'agit d'une tâche interséance.\n"
        "- Un exercice peut apparaître à la fois dans interventions et "
        "taches_interseances s'il est proposé comme intervention puis "
        "destiné à être réalisé entre les séances.\n"
        "- Ne classe pas comme tâche interséance un exercice uniquement "
        "discuté ou réalisé pendant la séance, sans indication qu'il "
        "doit être poursuivi après celle-ci.\n"
        "- Ne déduis pas une tâche interséance à partir d'une simple "
        "intention ou possibilité.\n\n"

        "FAITS RAPPORTÉS :\n"
        "- N'y duplique pas une information déjà mieux représentée "
        "dans emotions, cognitions, comportements ou evitements.\n\n"

        "ELEMENTS INCERTAINS :\n"
        "- N'invente pas d'incertitude supplémentaire.\n"
        "- Le programme ajoutera lui-même les passages OCR "
        "incertains après ta réponse."
    )

    prompt_utilisateur = (
        "Transcription constituée uniquement des lignes "
        "considérées comme certaines :\n\n"
        "----- DÉBUT -----\n"
        f"{transcription_certaine}\n"
        "----- FIN -----"
    )

    reponse = client.responses.parse(
        model=MODEL_EXTRACTION,

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

        raise RuntimeError(
            "Réponse d'extraction incomplète."
        )

    donnees = reponse.output_parsed

    if donnees is None:
        raise RuntimeError(
            "Aucune donnée structurée valide."
        )

    donnees = dedoublonner_donnees(
        donnees
    )

    donnees = ajouter_incertitudes_deterministes(
        donnees,
        lignes_incertaines,
    )

    return (
        donnees,
        reponse,
        lignes_incertaines,
    )


def enregistrer_donnees_cliniques(
    donnees: DonneesCliniques,
    json_path: Path,
) -> None:

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
# TOKENS
# =========================================================

def obtenir_utilisation(
    reponse,
) -> tuple[int, int, int]:

    usage = getattr(
        reponse,
        "usage",
        None,
    )

    if usage is None:
        return 0, 0, 0

    return (
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
        getattr(usage, "total_tokens", 0) or 0,
    )


def ajouter_utilisation(
    statistiques: dict,
    categorie: str,
    reponse,
) -> tuple[int, int, int]:

    (
        input_tokens,
        output_tokens,
        total_tokens,
    ) = obtenir_utilisation(reponse)

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
# IMAGES D'ENTRÉE
# =========================================================

def obtenir_images_entree() -> list[Path]:

    ENTREE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    return sorted(
        [
            fichier
            for fichier in ENTREE_DIR.iterdir()
            if fichier.is_file()
            and fichier.suffix.lower()
            in EXTENSIONS_ENTREE
        ],
        key=lambda fichier: fichier.name.lower(),
    )


# =========================================================
# TRAITEMENT D'UNE IMAGE
# =========================================================

def traiter_image(
    fichier_source: Path,
    patients: list[dict],
    cache_client: dict[str, OpenAI],
    statistiques: dict,
) -> None:

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

        print(
            "Résultat : identification ambiguë."
        )

        print(
            "Patients possibles : "
            + ", ".join(
                p["identifiant"]
                for p in correspondances
            )
        )

        return

    print(
        f"Patient identifié : "
        f"{patient['identifiant']} "
        f"({patient.get('nom_affichage', '')})"
    )

    (
        image_patient,
        copie_creee,
        format_reel,
    ) = copier_dans_dossier_patient(
        fichier_source,
        patient,
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
    # OCR
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
        print(
            "\nAucune transcription valide existante."
        )

        print(
            "Préparation et envoi de l'image à "
            f"{MODEL_OCR}..."
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

    # -----------------------------------------------------
    # EXTRACTION CLINIQUE V2
    # -----------------------------------------------------

    transcription = lire_transcription(
        transcription_path
    )

    if donnees_cliniques_valides(
        json_path,
        transcription_path,
    ):
        print(
            "\nDonnées cliniques V2 valides "
            "déjà existantes."
        )

        print(
            f"Fichier réutilisé : {json_path}"
        )

    else:
        if json_path.exists():
            print(
                "\nLe JSON existant utilise un ancien "
                "schéma, est invalide ou est plus ancien "
                "que la transcription."
            )
            print(
                "Il va être régénéré en schéma V2."
            )

        else:
            print(
                "\nAucune extraction clinique existante."
            )

        client = obtenir_client(
            cache_client
        )

        (
            donnees,
            reponse_extraction,
            lignes_incertaines,
        ) = extraire_donnees_cliniques(
            client,
            transcription,
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

        print(
            "\n--- DONNÉES CLINIQUES V2 ---\n"
        )

        print(
            json.dumps(
                donnees.model_dump(
                    mode="json"
                ),
                ensure_ascii=False,
                indent=2,
            )
        )

        if lignes_incertaines:
            print(
                "\n--- INCERTITUDES OCR "
                "ISOLÉES PAR PYTHON ---"
            )

            for ligne in lignes_incertaines:
                print(
                    f"- {ligne}"
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
            f"\nJSON clinique créé : {json_path}"
        )

    if not appel_effectue:
        statistiques["deja_complets"] += 1

        print(
            "\nTraitement déjà complet."
        )
        print(
            "Aucun nouvel appel API n'a été effectué."
        )
    else:
        print(
            "\nTraitement terminé pour cette image."
        )


# =========================================================
# STATISTIQUES
# =========================================================

def creer_statistiques() -> dict:

    return {
        "photos_copiees": 0,
        "transcriptions_creees": 0,
        "extractions_creees": 0,
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


# =========================================================
# MAIN
# =========================================================

def main() -> None:

    print("=" * 70)
    print(
        "PSYCHO IA — CLASSEMENT, TRANSCRIPTION "
        "ET EXTRACTION CLINIQUE V2"
    )
    print("=" * 70)

    print(f"Modèle OCR : {MODEL_OCR}")
    print(f"Modèle extraction : {MODEL_EXTRACTION}")
    print(f"Schéma clinique : {SCHEMA_VERSION}")
    print(f"Dossier d'entrée : {ENTREE_DIR}")
    print(f"Dossiers patients : {PATIENTS_DIR}")

    try:
        patients = charger_patients()
        images = obtenir_images_entree()

        if not images:
            print(
                "\nAucune image trouvée."
            )
            return

        print(
            f"\nNombre d'images trouvées : "
            f"{len(images)}"
        )

        statistiques = creer_statistiques()

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