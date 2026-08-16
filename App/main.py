from __future__ import annotations

from datetime import date, datetime, timezone
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
MAX_OUTPUT_TOKENS_SYNTHESE = 5000

REASONING_EFFORT_SYNTHESE = "low"

SCHEMA_VERSION = "2.0"
SYNTHESIS_SCHEMA_VERSION = "1.1"

MIN_SEANCES_SYNTHESE = 2

NOMBRE_LIGNES_ENTETE_DATE = 5

MOTIF_DATE_NOM_FICHIER = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_"
)

MOTIFS_DATE_TRANSCRIPTION = (
    re.compile(
        r"(?<!\d)(?P<jour>\d{1,2})[-/.]"
        r"(?P<mois>\d{1,2})[-/.]"
        r"(?P<annee>\d{4})(?!\d)"
    ),
    re.compile(
        r"(?<!\d)(?P<annee>\d{4})[-/.]"
        r"(?P<mois>\d{1,2})[-/.]"
        r"(?P<jour>\d{1,2})(?!\d)"
    ),
)


class ErreurDateSeance(ValueError):
    """Erreur déterministe liée à la date d'une séance."""


class DateNomFichierInvalide(ErreurDateSeance):
    """Le nom de fichier ne contient pas une date ISO valide."""


class DateTranscriptionInvalide(ErreurDateSeance):
    """L'en-tête OCR contient une date invalide ou ambiguë."""


class DivergenceDateTranscription(ErreurDateSeance):
    """La date OCR contredit la date déterministe du fichier."""


class DivergenceDateDonneesCliniques(ErreurDateSeance):
    """La date du JSON clinique contredit celle du fichier."""


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
# SCHÉMA DE SYNTHÈSE LONGITUDINALE
# =========================================================

StatutInformation = Literal[
    "explicite",
    "synthese_prudente",
]


class ElementLongitudinal(BaseModel):
    """
    Élément clinique synthétique avec traçabilité
    vers les séances sources.
    """

    model_config = ConfigDict(extra="forbid")

    contenu: str = Field(
        description=(
            "Information clinique concise et compréhensible isolément."
        )
    )

    statut: StatutInformation = Field(
        description=(
            "'explicite' si l'information apparaît directement dans les "
            "données sources ; 'synthese_prudente' si elle résulte d'un "
            "rapprochement prudent de plusieurs éléments explicites."
        )
    )

    dates_sources: list[date] = Field(
        description=(
            "Dates des séances qui soutiennent directement cet élément."
        )
    )


class EvolutionLongitudinale(BaseModel):
    """
    Évolution d'un domaine clinique dans le temps.
    """

    model_config = ConfigDict(extra="forbid")

    domaine: str = Field(
        description=(
            "Domaine concerné par l'évolution, par exemple évitement des "
            "transports ou anxiété dans le tram."
        )
    )

    constat: str = Field(
        description=(
            "Description prudente de l'évolution observée."
        )
    )

    direction: Literal[
        "amelioration",
        "aggravation",
        "stable",
        "fluctuation",
        "indeterminee",
    ]

    statut: Literal["synthese_prudente"] = Field(
        description=(
            "Une évolution compare plusieurs séances et constitue donc "
            "toujours une synthèse prudente."
        )
    )

    dates_sources: list[date] = Field(
        min_length=2,
        description=(
            "Au moins deux dates de séances distinctes soutenant "
            "l'évolution."
        ),
    )


class InterventionLongitudinale(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contenu: str

    dates_sources: list[date]


class PointAReprendre(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contenu: str = Field(
        description=(
            "Point pertinent à vérifier, préciser ou reprendre lors d'une "
            "séance ultérieure."
        )
    )

    motif: Literal[
        "suivi_tache",
        "evolution_a_verifier",
        "information_manquante",
        "element_incertain",
    ]

    dates_sources: list[date]


class SyntheseLongitudinale(BaseModel):
    """
    Partie produite par GPT-5.6 Terra.

    Pas de diagnostic ni d'analyse fonctionnelle à ce stade.
    """

    model_config = ConfigDict(extra="forbid")

    problematiques_actuelles: list[ElementLongitudinal]

    evolution: list[EvolutionLongitudinale]

    emotions_actuelles: list[ElementLongitudinal]

    cognitions_recurrentes: list[ElementLongitudinal]

    comportements_significatifs: list[ElementLongitudinal]

    evitements_actuels: list[ElementLongitudinal]

    interventions_documentees: list[InterventionLongitudinale]

    reponse_aux_interventions: list[ElementLongitudinal]

    taches_actuelles: list[ElementLongitudinal]

    elements_incertains: list[ElementLongitudinal]

    points_a_reprendre: list[PointAReprendre]


class MetadataSynthese(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.1"]

    patient_id: str

    modele: str

    genere_le: str

    nombre_seances_integrees: int

    date_premiere_seance: date

    date_derniere_seance: date

    fichiers_sources: list[str]

    empreinte_sources_sha256: str


class FichierSyntheseLongitudinale(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: MetadataSynthese

    synthese: SyntheseLongitudinale


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
# CONTRÔLE DÉTERMINISTE DE LA DATE DE SÉANCE
# =========================================================

def extraire_date_nom_fichier(
    nom_fichier: str,
) -> date:
    """
    Exige un préfixe AAAA-MM-JJ_ dans le nom du fichier.
    """

    nom_sans_extension = Path(
        nom_fichier
    ).stem

    correspondance = (
        MOTIF_DATE_NOM_FICHIER.match(
            nom_sans_extension
        )
    )

    if correspondance is None:
        raise DateNomFichierInvalide(
            "Le nom du fichier doit commencer par une date "
            "valide au format AAAA-MM-JJ suivie d'un "
            "soulignement."
        )

    date_texte = correspondance.group(
        "date"
    )

    try:
        return date.fromisoformat(
            date_texte
        )

    except ValueError as erreur:
        raise DateNomFichierInvalide(
            "La date du nom de fichier est impossible : "
            f"{date_texte}."
        ) from erreur


def extraire_date_entete_transcription(
    transcription: str,
) -> date | None:
    """
    Recherche une date numérique dans les premières lignes non vides.

    Retourne None lorsque l'en-tête ne contient aucune date lisible.
    """

    lignes_entete = [
        ligne.strip()
        for ligne in transcription.splitlines()
        if ligne.strip()
    ][:NOMBRE_LIGNES_ENTETE_DATE]

    dates_trouvees: set[date] = set()

    for ligne in lignes_entete:
        for motif in MOTIFS_DATE_TRANSCRIPTION:
            for correspondance in motif.finditer(
                ligne
            ):
                try:
                    date_trouvee = date(
                        int(
                            correspondance.group(
                                "annee"
                            )
                        ),
                        int(
                            correspondance.group(
                                "mois"
                            )
                        ),
                        int(
                            correspondance.group(
                                "jour"
                            )
                        ),
                    )

                except ValueError as erreur:
                    raise DateTranscriptionInvalide(
                        "L'en-tête de la transcription contient "
                        "une date impossible."
                    ) from erreur

                dates_trouvees.add(
                    date_trouvee
                )

    if not dates_trouvees:
        return None

    if len(dates_trouvees) > 1:
        raise DateTranscriptionInvalide(
            "L'en-tête de la transcription contient plusieurs "
            "dates différentes."
        )

    return next(
        iter(dates_trouvees)
    )


def verifier_date_transcription(
    transcription: str,
    date_attendue: date,
) -> date | None:
    """
    Bloque toute contradiction entre l'en-tête OCR et le nom du fichier.
    """

    date_transcription = (
        extraire_date_entete_transcription(
            transcription
        )
    )

    if (
        date_transcription is not None
        and date_transcription != date_attendue
    ):
        raise DivergenceDateTranscription(
            "Divergence de date : le nom du fichier indique "
            f"{date_attendue.isoformat()}, mais la transcription "
            f"indique {date_transcription.isoformat()}."
        )

    return date_transcription


def verifier_date_donnees_cliniques(
    donnees: DonneesCliniques,
    date_attendue: date,
) -> DonneesCliniques:
    """
    Bloque une date contradictoire et complète une date absente.
    """

    if (
        donnees.date_seance is not None
        and donnees.date_seance != date_attendue
    ):
        raise DivergenceDateDonneesCliniques(
            "Divergence de date : le nom du fichier indique "
            f"{date_attendue.isoformat()}, mais le JSON clinique "
            f"indique {donnees.date_seance.isoformat()}."
        )

    if donnees.date_seance == date_attendue:
        return donnees

    return donnees.model_copy(
        update={
            "date_seance": date_attendue
        }
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


def charger_donnees_cliniques_existantes(
    json_path: Path,
) -> DonneesCliniques | None:

    if not json_path.is_file():
        return None

    try:
        contenu = json_path.read_text(
            encoding="utf-8-sig"
        )

        return (
            DonneesCliniques.model_validate_json(
                contenu
            )
        )

    except Exception:
        return None


def donnees_cliniques_valides(
    json_path: Path,
    transcription_path: Path,
    date_attendue: date,
) -> bool:
    """
    Les anciens JSON V1 seront automatiquement considérés
    comme invalides puisqu'ils n'ont pas schema_version=2.0
    et n'utilisent pas le nouveau schéma contextualisé.
    """

    donnees = (
        charger_donnees_cliniques_existantes(
            json_path
        )
    )

    if donnees is None:
        return False

    if donnees.schema_version != SCHEMA_VERSION:
        return False

    if donnees.date_seance != date_attendue:
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
                        "detail": "high",
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
    date_attendue: date,
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

        "- date_seance doit être exactement "
        f"\"{date_attendue.isoformat()}\". Cette date a été "
        "établie et contrôlée par Python à partir du nom du fichier. "
        "Ne la modifie pas et n'en déduis pas une autre depuis le texte.\n"

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
        "Date de séance déterministe : "
        f"{date_attendue.isoformat()}\n\n"
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
# SYNTHÈSE LONGITUDINALE
# =========================================================

def obtenir_chemin_synthese_longitudinale(
    patient: dict,
) -> Path:

    return (
        patient["dossier"]
        / "syntheses"
        / "synthese_longitudinale.json"
    )


def obtenir_fichiers_cliniques_patient(
    patient: dict,
) -> list[Path]:

    dossier = (
        patient["dossier"]
        / "donnees_cliniques"
    )

    if not dossier.exists():
        return []

    return sorted(
        dossier.glob("*.json"),
        key=lambda fichier: fichier.name.lower(),
    )


def charger_seances_longitudinales(
    fichiers: list[Path],
) -> tuple[
    list[tuple[Path, DonneesCliniques]],
    list[str],
]:
    """
    Charge uniquement les JSON cliniques V2 datés.

    Les fichiers invalides sont ignorés pour que le pipeline
    multi-patients continue, mais ils sont affichés.
    """

    seances: list[
        tuple[Path, DonneesCliniques]
    ] = []

    fichiers_ignores: list[str] = []

    for fichier in fichiers:
        try:
            contenu = fichier.read_text(
                encoding="utf-8-sig"
            )

            donnees = (
                DonneesCliniques.model_validate_json(
                    contenu
                )
            )

            if (
                donnees.schema_version
                != SCHEMA_VERSION
            ):
                fichiers_ignores.append(
                    f"{fichier.name} : schéma différent"
                )
                continue

            if donnees.date_seance is None:
                fichiers_ignores.append(
                    f"{fichier.name} : date de séance absente"
                )
                continue

        except Exception as erreur:
            fichiers_ignores.append(
                f"{fichier.name} : JSON clinique invalide ({erreur})"
            )
            continue

        seances.append(
            (
                fichier,
                donnees,
            )
        )

    seances.sort(
        key=lambda element:
        element[1].date_seance
    )

    return seances, fichiers_ignores


def calculer_empreinte_sources(
    fichiers: list[Path],
) -> str:
    """
    Calcule l'empreinte de l'ensemble exact des JSON sources.
    """

    calcul = hashlib.sha256()

    for fichier in sorted(
        fichiers,
        key=lambda f: f.name.lower(),
    ):
        calcul.update(
            fichier.name.encode("utf-8")
        )
        calcul.update(b"\0")
        calcul.update(
            fichier.read_bytes()
        )
        calcul.update(b"\0")

    return calcul.hexdigest()


def synthese_deja_a_jour(
    output_path: Path,
    empreinte_sources: str,
) -> bool:

    if not output_path.is_file():
        return False

    try:
        contenu = output_path.read_text(
            encoding="utf-8-sig"
        )

        fichier_synthese = (
            FichierSyntheseLongitudinale
            .model_validate_json(
                contenu
            )
        )

    except Exception:
        return False

    return (
        fichier_synthese
        .metadata
        .empreinte_sources_sha256
        == empreinte_sources
    )


def preparer_seances_pour_api(
    seances: list[
        tuple[Path, DonneesCliniques]
    ],
) -> str:

    contenu = []

    for _, donnees in seances:
        contenu.append(
            {
                "date_seance": (
                    donnees.date_seance.isoformat()
                    if donnees.date_seance
                    else None
                ),
                "donnees": donnees.model_dump(
                    mode="json"
                ),
            }
        )

    return json.dumps(
        contenu,
        ensure_ascii=False,
        indent=2,
    )


def generer_synthese_longitudinale(
    client: OpenAI,
    seances: list[
        tuple[Path, DonneesCliniques]
    ],
):

    donnees_source = (
        preparer_seances_pour_api(
            seances
        )
    )

    prompt_systeme = (
        "Tu construis une synthèse longitudinale à partir "
        "de données structurées issues de plusieurs séances "
        "de psychothérapie.\n\n"

        "Cette étape est une SYNTHÈSE CLINIQUE PRUDENTE. "
        "Ce n'est ni un diagnostic ni une analyse "
        "fonctionnelle complète.\n\n"

        "RÈGLES FONDAMENTALES :\n"
        "- Utilise exclusivement les informations fournies.\n"
        "- N'invente aucune information.\n"
        "- Ne pose aucun diagnostic.\n"
        "- N'invente aucun antécédent.\n"
        "- N'invente aucune causalité.\n"
        "- N'invente aucune intention du patient.\n"
        "- N'interprète pas l'absence d'une information comme "
        "la preuve de son absence clinique.\n"
        "- Conserve la distinction entre faits explicites et "
        "synthèses prudentes.\n"
        "- Toutes les dates_sources doivent correspondre à "
        "des dates réellement présentes dans les données.\n\n"

        "STATUT DES INFORMATIONS :\n"
        "- Utilise 'explicite' si l'élément est directement "
        "présent dans une ou plusieurs séances.\n"
        "- Utilise 'synthese_prudente' lorsqu'il s'agit d'un "
        "rapprochement raisonnable de plusieurs informations "
        "explicites.\n"
        "- Toute entrée dans evolution compare plusieurs séances et doit "
        "donc avoir le statut 'synthese_prudente', même lorsque les faits "
        "comparés sont chacun explicites.\n"
        "- Une synthèse prudente doit rester formulée avec "
        "mesure et ne doit jamais devenir un diagnostic.\n\n"

        "PROBLÉMATIQUES ACTUELLES :\n"
        "- Résume uniquement les difficultés dont le caractère actuel "
        "est soutenu par les données récentes.\n"
        "- Une problématique peut être considérée comme actuelle si elle "
        "est présente dans la séance la plus récente ou si sa persistance "
        "jusqu'aux séances récentes est soutenue par plusieurs données.\n"
        "- Une difficulté mentionnée uniquement dans une ancienne séance "
        "ne doit pas être présentée comme actuelle simplement parce "
        "qu'aucune résolution ultérieure n'est mentionnée.\n"
        "- L'absence de mention ultérieure ne prouve ni la résolution "
        "ni la persistance d'une difficulté.\n"
        "- N'utilise pas d'étiquette diagnostique non présente.\n\n"

        "ÉVOLUTION :\n"
        "- Ce champ décrit une évolution ENTRE plusieurs séances.\n"
        "- Une entrée dans evolution doit être soutenue par "
        "au moins deux dates de séance différentes.\n"
        "- Son statut doit toujours être 'synthese_prudente'.\n"
        "- Une amélioration, aggravation, stabilité ou fluctuation "
        "longitudinale ne doit pas être déduite d'une seule séance.\n"
        "- Une variation observée à l'intérieur d'une seule séance ou "
        "d'une seule situation, par exemple une anxiété passant de 7/10 "
        "à 4/10 pendant un trajet, n'est pas à elle seule une évolution "
        "longitudinale.\n"
        "- Dans ce cas, conserve l'information dans la catégorie clinique "
        "appropriée, par exemple emotions_actuelles, mais ne crée pas "
        "d'entrée correspondante dans evolution.\n"
        "- Compare uniquement ce qui peut réellement être comparé entre "
        "plusieurs séances.\n"
        "- Utilise 'amelioration' seulement lorsqu'un changement favorable "
        "entre plusieurs séances est soutenu par les données.\n"
        "- Utilise 'aggravation' seulement lorsqu'un changement défavorable "
        "entre plusieurs séances est soutenu par les données.\n"
        "- Utilise 'stable' ou 'fluctuation' uniquement si plusieurs séances "
        "permettent réellement cette conclusion.\n"
        "- Utilise 'indeterminee' si les données longitudinales ne permettent "
        "pas de conclure.\n"
        "- Ne confonds jamais changement temporel et effet causal d'une "
        "intervention.\n\n"

        "ÉMOTIONS ACTUELLES :\n"
        "- Conserve les émotions encore pertinentes dans les "
        "séances récentes.\n"
        "- Ne déduis jamais une émotion absente des sources.\n\n"

        "COGNITIONS RÉCURRENTES :\n"
        "- Réserve ce champ aux cognitions ou thèmes cognitifs "
        "qui apparaissent à plusieurs reprises, ou dont la "
        "continuité est directement soutenue par les données.\n"
        "- Ne transforme pas deux pensées différentes en une "
        "croyance générale sans justification.\n"
        "- Si referent_contextuel est renseigné, utilise-le lors d'une "
        "reformulation afin d'éviter qu'un pronom change de référent ou "
        "devienne grammaticalement ambigu.\n\n"

        "COMPORTEMENTS ET ÉVITEMENTS :\n"
        "- Résume les comportements cliniquement pertinents "
        "et les évitements actuels.\n"
        "- evitements_actuels doit contenir uniquement des comportements "
        "d'évitement réellement rapportés comme actuels ou dont la "
        "persistance récente est explicitement soutenue.\n"
        "- Une pensée, une crainte ou une envie de fuir ne constitue pas "
        "un évitement comportemental si la personne reste dans la situation.\n"
        "- Un évitement ancien ne doit pas rester dans evitements_actuels "
        "si les données les plus récentes indiquent explicitement que ce "
        "comportement ne s'est pas reproduit. Il peut être mentionné dans "
        "evolution si cela est pertinent.\n"
        "- Si un évitement initial est suivi d'une confrontation "
        "à la situation, décris prudemment cette évolution sans "
        "affirmer que le problème est résolu.\n\n"

        "INTERVENTIONS DOCUMENTÉES :\n"
        "- Recense les interventions, exercices ou consignes explicitement "
        "documentés dans les sources.\n"
        "- Respecte leur statut : proposé, discuté ou réalisé lorsqu'il est "
        "possible de le déterminer.\n"
        "- Ne transforme pas une intervention proposée en intervention réalisée.\n"
        "- Regroupe les formulations manifestement équivalentes sans perdre "
        "l'information temporelle.\n\n"

        "RÉPONSE AUX INTERVENTIONS :\n"
        "- Ne renseigne ce champ que lorsqu'une séance ultérieure "
        "contient des éléments permettant d'observer ce qui s'est "
        "passé après une intervention ou une tâche.\n"
        "- Une succession temporelle n'établit jamais à elle seule "
        "une causalité ni même la réalisation exacte de l'exercice proposé.\n"
        "- Lorsque tu relies une intervention d'une séance à des éléments "
        "rapportés lors d'une séance ultérieure, utilise normalement le "
        "statut 'synthese_prudente'.\n"
        "- Utilise 'explicite' uniquement si les données sources indiquent "
        "elles-mêmes explicitement que l'élément observé constitue une "
        "réponse à cette intervention précise.\n"
        "- Écris 'après la proposition de l'exercice...' lorsque les données "
        "indiquent seulement que l'exercice a été proposé.\n"
        "- N'écris pas 'après l'exercice...' si sa réalisation exacte "
        "n'est pas explicitement attestée.\n"
        "- Ne suppose jamais que des trajets effectués ultérieurement avaient "
        "la durée prescrite si cette durée n'est pas explicitement rapportée.\n"
        "- Ne formule jamais 'grâce à', 'a entraîné', 'a permis' ou toute "
        "autre causalité non explicitement soutenue.\n\n"

        "TÂCHES ACTUELLES :\n"
        "- Conserve les tâches interséances les plus récentes "
        "qui doivent encore être réalisées ou suivies.\n"
        "- Une ancienne tâche remplacée par une nouvelle ne doit "
        "pas être présentée comme tâche actuelle.\n\n"

        "ÉLÉMENTS INCERTAINS :\n"
        "- Conserve uniquement les incertitudes pertinentes présentes dans "
        "les champs elements_incertains des séances sources.\n"
        "- Ne transforme jamais une donnée incertaine en donnée "
        "certaine.\n"
        "- referent_explicitement_identifie=false ne constitue pas à lui "
        "seul un élément incertain lorsque referent_contextuel est renseigné.\n"
        "- N'invente pas une incertitude à partir d'un simple pronom dont "
        "le référent contextuel est fourni.\n\n"

        "POINTS À REPRENDRE :\n"
        "- Ce champ peut identifier ce qu'il serait pertinent "
        "de vérifier lors d'une prochaine séance.\n"
        "- Il doit découler directement des données : tâche à "
        "suivre, évolution à vérifier, information manquante "
        "importante ou élément incertain.\n"
        "- N'invente pas un nouvel objectif thérapeutique.\n\n"

        "TRAÇABILITÉ :\n"
        "- Chaque élément doit comporter uniquement les dates "
        "qui soutiennent réellement son contenu.\n"
        "- Lorsqu'une citation contient un pronom, préserve la citation ou "
        "remplace clairement le pronom par son referent_contextuel ; ne "
        "produis pas une reformulation grammaticalement ambiguë.\n"
        "- Évite les doublons et les paraphrases inutiles."
    )

    prompt_utilisateur = (
        "Voici les séances structurées, dans l'ordre "
        "chronologique :\n\n"
        "----- DÉBUT DES DONNÉES -----\n"
        f"{donnees_source}\n"
        "----- FIN DES DONNÉES -----"
    )

    reponse = client.responses.parse(
        model=MODEL_EXTRACTION,

        reasoning={
            "effort": REASONING_EFFORT_SYNTHESE,
        },

        store=False,

        max_output_tokens=MAX_OUTPUT_TOKENS_SYNTHESE,

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

        text_format=SyntheseLongitudinale,
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
            "La réponse de synthèse est incomplète. "
            f"Détails : {details}"
        )

    synthese = reponse.output_parsed

    if synthese is None:
        raise RuntimeError(
            "Terra n'a pas retourné de synthèse structurée valide."
        )

    return synthese, reponse


def obtenir_dates_autorisees(
    seances: list[
        tuple[Path, DonneesCliniques]
    ],
) -> set[date]:

    return {
        donnees.date_seance
        for _, donnees in seances
        if donnees.date_seance is not None
    }


def verifier_dates_sources(
    synthese: SyntheseLongitudinale,
    dates_autorisees: set[date],
) -> None:
    """
    Empêche le modèle d'inventer une date de séance.
    """

    dates_utilisees: list[date] = []

    collections_elements = [
        synthese.problematiques_actuelles,
        synthese.emotions_actuelles,
        synthese.cognitions_recurrentes,
        synthese.comportements_significatifs,
        synthese.evitements_actuels,
        synthese.reponse_aux_interventions,
        synthese.taches_actuelles,
        synthese.elements_incertains,
    ]

    for collection in collections_elements:
        for element in collection:
            dates_utilisees.extend(
                element.dates_sources
            )

    for element in synthese.evolution:
        dates_utilisees.extend(
            element.dates_sources
        )

    for element in (
        synthese.interventions_documentees
    ):
        dates_utilisees.extend(
            element.dates_sources
        )

    for element in synthese.points_a_reprendre:
        dates_utilisees.extend(
            element.dates_sources
        )

    dates_invalides = {
        date_source
        for date_source in dates_utilisees
        if date_source not in dates_autorisees
    }

    if dates_invalides:
        invalides = ", ".join(
            sorted(
                d.isoformat()
                for d in dates_invalides
            )
        )

        raise ValueError(
            "La synthèse contient des dates sources inexistantes : "
            f"{invalides}"
        )


def verifier_evolutions_longitudinales(
    synthese: SyntheseLongitudinale,
) -> None:
    """
    Garantit qu'une évolution compare au moins deux séances distinctes.
    """

    positions_invalides = [
        position
        for position, element in enumerate(
            synthese.evolution,
            start=1,
        )
        if len(set(element.dates_sources)) < 2
    ]

    if positions_invalides:
        positions = ", ".join(
            str(position)
            for position in positions_invalides
        )

        raise ValueError(
            "Les entrées evolution suivantes ne comparent pas au moins "
            f"deux séances distinctes : {positions}"
        )


def construire_fichier_synthese(
    patient: dict,
    synthese: SyntheseLongitudinale,
    seances: list[
        tuple[Path, DonneesCliniques]
    ],
    empreinte_sources: str,
) -> FichierSyntheseLongitudinale:

    dates = [
        donnees.date_seance
        for _, donnees in seances
        if donnees.date_seance is not None
    ]

    fichiers_sources = [
        fichier.name
        for fichier, _ in seances
    ]

    metadata = MetadataSynthese(
        schema_version=SYNTHESIS_SCHEMA_VERSION,
        patient_id=patient["identifiant"],
        modele=MODEL_EXTRACTION,
        genere_le=(
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        nombre_seances_integrees=len(
            seances
        ),
        date_premiere_seance=min(
            dates
        ),
        date_derniere_seance=max(
            dates
        ),
        fichiers_sources=fichiers_sources,
        empreinte_sources_sha256=empreinte_sources,
    )

    return FichierSyntheseLongitudinale(
        metadata=metadata,
        synthese=synthese,
    )


def enregistrer_synthese_longitudinale(
    fichier_final: FichierSyntheseLongitudinale,
    output_path: Path,
) -> None:

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    contenu = fichier_final.model_dump(
        mode="json"
    )

    output_path.write_text(
        json.dumps(
            contenu,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def mettre_a_jour_synthese_longitudinale(
    patient: dict,
    cache_client: dict[str, OpenAI],
    statistiques: dict,
) -> bool:
    """
    Met à jour la synthèse uniquement si les JSON cliniques
    V2 datés du patient ont changé.

    Retourne True lorsqu'un appel API de synthèse a été effectué.
    """

    print(
        "\n--- SYNTHÈSE LONGITUDINALE ---"
    )

    fichiers = obtenir_fichiers_cliniques_patient(
        patient
    )

    seances, fichiers_ignores = (
        charger_seances_longitudinales(
            fichiers
        )
    )

    if fichiers_ignores:
        print(
            "Fichiers cliniques ignorés pour la synthèse :"
        )

        for element in fichiers_ignores:
            print(
                f"- {element}"
            )

    print(
        f"Séances V2 valides trouvées : {len(seances)}"
    )

    if len(seances) < MIN_SEANCES_SYNTHESE:
        statistiques[
            "syntheses_ignorees"
        ] += 1

        print(
            "Synthèse non générée : au moins "
            f"{MIN_SEANCES_SYNTHESE} séances valides "
            "sont nécessaires."
        )

        return False

    fichiers_sources = [
        fichier
        for fichier, _ in seances
    ]

    empreinte_sources = (
        calculer_empreinte_sources(
            fichiers_sources
        )
    )

    output_path = (
        obtenir_chemin_synthese_longitudinale(
            patient
        )
    )

    print(
        "Empreinte sources : "
        f"{empreinte_sources[:16]}..."
    )

    if synthese_deja_a_jour(
        output_path,
        empreinte_sources,
    ):
        statistiques[
            "syntheses_deja_a_jour"
        ] += 1

        print(
            "Synthèse longitudinale déjà à jour."
        )
        print(
            "Aucun nouvel appel API de synthèse."
        )
        print(
            f"Fichier existant : {output_path}"
        )

        return False

    client = obtenir_client(
        cache_client
    )

    print(
        "Génération de la synthèse longitudinale "
        f"avec {MODEL_EXTRACTION}..."
    )

    synthese, reponse = (
        generer_synthese_longitudinale(
            client,
            seances,
        )
    )

    dates_autorisees = (
        obtenir_dates_autorisees(
            seances
        )
    )

    verifier_dates_sources(
        synthese,
        dates_autorisees,
    )

    verifier_evolutions_longitudinales(
        synthese
    )

    fichier_final = (
        construire_fichier_synthese(
            patient,
            synthese,
            seances,
            empreinte_sources,
        )
    )

    enregistrer_synthese_longitudinale(
        fichier_final,
        output_path,
    )

    statistiques[
        "syntheses_creees"
    ] += 1

    (
        input_tokens,
        output_tokens,
        total_tokens,
    ) = ajouter_utilisation(
        statistiques,
        "synthese",
        reponse,
    )

    print(
        "Synthèse longitudinale créée : "
        f"{output_path}"
    )

    print(
        "\n--- UTILISATION SYNTHÈSE ---"
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

    return True


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

    try:
        date_attendue = extraire_date_nom_fichier(
            fichier_source.name
        )

    except DateNomFichierInvalide:
        statistiques[
            "dates_nom_invalides"
        ] += 1

        print(
            "Résultat : date du nom de fichier invalide."
        )
        print(
            "Aucun appel API ne sera effectué pour cette image."
        )

        raise

    print(
        "Date déterministe du fichier : "
        f"{date_attendue.isoformat()}"
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

    try:
        date_transcription = (
            verifier_date_transcription(
                transcription,
                date_attendue,
            )
        )

    except DateTranscriptionInvalide:
        statistiques[
            "dates_transcription_invalides"
        ] += 1

        print(
            "\nRésultat : date OCR invalide ou ambiguë."
        )
        print(
            "Le JSON clinique et la synthèse ne seront pas mis à jour."
        )

        raise

    except DivergenceDateTranscription:
        statistiques[
            "dates_transcription_divergentes"
        ] += 1

        print(
            "\nRésultat : divergence entre la date du fichier "
            "et la transcription."
        )
        print(
            "Le JSON clinique et la synthèse ne seront pas mis à jour."
        )

        raise

    if date_transcription is None:
        statistiques[
            "dates_transcription_absentes"
        ] += 1

        print(
            "\nDate absente de l'en-tête OCR : "
            "la date déterministe du fichier sera utilisée."
        )

    else:
        print(
            "\nDate de transcription confirmée : "
            f"{date_transcription.isoformat()}"
        )

    donnees_existantes = (
        charger_donnees_cliniques_existantes(
            json_path
        )
    )

    if donnees_existantes is not None:
        try:
            verifier_date_donnees_cliniques(
                donnees_existantes,
                date_attendue,
            )

        except DivergenceDateDonneesCliniques:
            statistiques[
                "dates_json_divergentes"
            ] += 1

            print(
                "\nRésultat : divergence entre la date du fichier "
                "et le JSON clinique existant."
            )
            print(
                "La synthèse ne sera pas mise à jour."
            )

            raise

    if donnees_cliniques_valides(
        json_path,
        transcription_path,
        date_attendue,
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
            date_attendue,
        )

        (
            input_tokens,
            output_tokens,
            total_tokens,
        ) = ajouter_utilisation(
            statistiques,
            "extraction",
            reponse_extraction,
        )

        appel_effectue = True

        try:
            donnees = (
                verifier_date_donnees_cliniques(
                    donnees,
                    date_attendue,
                )
            )

        except DivergenceDateDonneesCliniques:
            statistiques[
                "dates_json_divergentes"
            ] += 1

            print(
                "\nRésultat : Terra a retourné une date différente "
                "de celle du fichier."
            )
            print(
                "Le JSON clinique et la synthèse ne seront pas mis à jour."
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

            raise

        enregistrer_donnees_cliniques(
            donnees,
            json_path,
        )

        statistiques[
            "extractions_creees"
        ] += 1

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

    synthese_api_effectuee = (
        mettre_a_jour_synthese_longitudinale(
            patient,
            cache_client,
            statistiques,
        )
    )

    if synthese_api_effectuee:
        appel_effectue = True

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
        "syntheses_creees": 0,
        "syntheses_deja_a_jour": 0,
        "syntheses_ignorees": 0,
        "deja_complets": 0,
        "non_identifies": 0,
        "ambigus": 0,
        "dates_nom_invalides": 0,
        "dates_transcription_absentes": 0,
        "dates_transcription_invalides": 0,
        "dates_transcription_divergentes": 0,
        "dates_json_divergentes": 0,
        "erreurs": 0,

        "ocr_input_tokens": 0,
        "ocr_output_tokens": 0,
        "ocr_total_tokens": 0,

        "extraction_input_tokens": 0,
        "extraction_output_tokens": 0,
        "extraction_total_tokens": 0,

        "synthese_input_tokens": 0,
        "synthese_output_tokens": 0,
        "synthese_total_tokens": 0,

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
        f"Synthèses longitudinales créées : "
        f"{statistiques['syntheses_creees']}"
    )

    print(
        f"Synthèses longitudinales déjà à jour : "
        f"{statistiques['syntheses_deja_a_jour']}"
    )

    print(
        f"Synthèses longitudinales ignorées : "
        f"{statistiques['syntheses_ignorees']}"
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
        f"Dates invalides dans les noms : "
        f"{statistiques['dates_nom_invalides']}"
    )

    print(
        f"Dates absentes des transcriptions : "
        f"{statistiques['dates_transcription_absentes']}"
    )

    print(
        f"Dates de transcription invalides : "
        f"{statistiques['dates_transcription_invalides']}"
    )

    print(
        f"Divergences fichier/transcription : "
        f"{statistiques['dates_transcription_divergentes']}"
    )

    print(
        f"Divergences fichier/JSON clinique : "
        f"{statistiques['dates_json_divergentes']}"
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

    print("\n--- SYNTHÈSE LONGITUDINALE ---")

    print(
        f"Tokens d'entrée : "
        f"{statistiques['synthese_input_tokens']}"
    )

    print(
        f"Tokens de sortie : "
        f"{statistiques['synthese_output_tokens']}"
    )

    print(
        f"Tokens totaux : "
        f"{statistiques['synthese_total_tokens']}"
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
