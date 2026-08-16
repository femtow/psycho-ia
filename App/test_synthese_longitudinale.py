from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
import hashlib
import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

PATIENT_ID = "P-0001"

PATIENT_DIR = (
    BASE_DIR
    / "patients_test"
    / PATIENT_ID
)

DONNEES_DIR = (
    PATIENT_DIR
    / "donnees_cliniques"
)

SYNTHESES_DIR = (
    PATIENT_DIR
    / "syntheses"
)

OUTPUT_PATH = (
    SYNTHESES_DIR
    / "synthese_longitudinale.json"
)

MODEL = "gpt-5.6-terra"

REASONING_EFFORT = "low"

MAX_OUTPUT_TOKENS = 5000

INPUT_SCHEMA_VERSION = "2.0"

SYNTHESIS_SCHEMA_VERSION = "1.1"


# =========================================================
# SCHÉMA DES JSON CLINIQUES V2 EN ENTRÉE
# =========================================================

class ElementContextualise(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    contenu: str
    contexte: str | None


class EmotionContextualisee(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    contenu: str
    contexte: str | None
    intensite: str | None


class CognitionContextualisee(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    contenu: str
    contexte: str | None

    referent_contextuel: str | None

    referent_explicitement_identifie: (
        bool | None
    )


class DonneesCliniques(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    schema_version: Literal["2.0"]

    date_seance: date | None

    faits_rapportes: list[str]

    emotions: list[
        EmotionContextualisee
    ]

    cognitions: list[
        CognitionContextualisee
    ]

    comportements: list[
        ElementContextualise
    ]

    evitements: list[
        ElementContextualise
    ]

    interventions: list[str]

    taches_interseances: list[str]

    elements_incertains: list[str]


# =========================================================
# SCHÉMA DE LA SYNTHÈSE LONGITUDINALE
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

    model_config = ConfigDict(
        extra="forbid"
    )

    contenu: str = Field(
        description=(
            "Information clinique concise et compréhensible "
            "isolément."
        )
    )

    statut: StatutInformation = Field(
        description=(
            "'explicite' si l'information apparaît directement "
            "dans les données sources ; 'synthese_prudente' si "
            "elle résulte d'un rapprochement prudent de plusieurs "
            "éléments explicites."
        )
    )

    dates_sources: list[date] = Field(
        description=(
            "Dates des séances qui soutiennent directement "
            "cet élément."
        )
    )


class EvolutionLongitudinale(BaseModel):
    """
    Évolution d'un domaine clinique dans le temps.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    domaine: str = Field(
        description=(
            "Domaine concerné par l'évolution, par exemple "
            "évitement des transports ou anxiété dans le tram."
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
            "Une évolution compare plusieurs séances et "
            "constitue donc toujours une synthèse prudente."
        )
    )

    dates_sources: list[date] = Field(
        min_length=2,
        description=(
            "Au moins deux dates de séances distinctes "
            "soutenant l'évolution."
        ),
    )


class InterventionLongitudinale(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    contenu: str

    dates_sources: list[date]


class PointAReprendre(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    contenu: str = Field(
        description=(
            "Point pertinent à vérifier, préciser ou reprendre "
            "lors d'une séance ultérieure."
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

    model_config = ConfigDict(
        extra="forbid"
    )

    problematiques_actuelles: list[
        ElementLongitudinal
    ]

    evolution: list[
        EvolutionLongitudinale
    ]

    emotions_actuelles: list[
        ElementLongitudinal
    ]

    cognitions_recurrentes: list[
        ElementLongitudinal
    ]

    comportements_significatifs: list[
        ElementLongitudinal
    ]

    evitements_actuels: list[
        ElementLongitudinal
    ]

    interventions_documentees: list[
        InterventionLongitudinale
    ]

    reponse_aux_interventions: list[
        ElementLongitudinal
    ]

    taches_actuelles: list[
        ElementLongitudinal
    ]

    elements_incertains: list[
        ElementLongitudinal
    ]

    points_a_reprendre: list[
        PointAReprendre
    ]


# =========================================================
# MÉTADONNÉES DÉTERMINISTES
# =========================================================

class MetadataSynthese(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

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
    """
    Structure finale enregistrée sur disque.

    Les métadonnées sont produites par Python.
    La synthèse clinique est produite par Terra.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    metadata: MetadataSynthese

    synthese: SyntheseLongitudinale


# =========================================================
# CLIENT OPENAI
# =========================================================

def charger_client() -> OpenAI:
    """
    Charge la clé API OpenAI depuis .env.
    """

    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f"Fichier .env introuvable : "
            f"{ENV_PATH}"
        )

    load_dotenv(
        ENV_PATH
    )

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY est absente ou "
            "vide dans le fichier .env."
        )

    return OpenAI(
        api_key=api_key
    )


# =========================================================
# CHARGEMENT DES SÉANCES
# =========================================================

def obtenir_fichiers_cliniques() -> list[Path]:
    """
    Retourne tous les JSON de séances du patient.
    """

    if not DONNEES_DIR.exists():
        raise FileNotFoundError(
            "Dossier donnees_cliniques "
            f"introuvable : {DONNEES_DIR}"
        )

    fichiers = sorted(
        DONNEES_DIR.glob("*.json"),
        key=lambda fichier: fichier.name.lower(),
    )

    if not fichiers:
        raise RuntimeError(
            "Aucun JSON clinique trouvé pour "
            f"{PATIENT_ID}."
        )

    return fichiers


def charger_seances(
    fichiers: list[Path],
) -> list[
    tuple[Path, DonneesCliniques]
]:
    """
    Charge et valide tous les JSON cliniques V2.
    """

    seances: list[
        tuple[Path, DonneesCliniques]
    ] = []

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

        except Exception as erreur:
            raise ValueError(
                f"JSON clinique invalide : "
                f"{fichier}\n"
                f"Détail : {erreur}"
            ) from erreur

        if (
            donnees.schema_version
            != INPUT_SCHEMA_VERSION
        ):
            raise ValueError(
                f"Ancien schéma détecté dans "
                f"{fichier.name}."
            )

        if donnees.date_seance is None:
            raise ValueError(
                "Une date de séance est nécessaire "
                "pour la synthèse longitudinale : "
                f"{fichier.name}"
            )

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

    return seances


# =========================================================
# EMPREINTE DES SOURCES
# =========================================================

def calculer_empreinte_sources(
    fichiers: list[Path],
) -> str:
    """
    Calcule une empreinte unique de l'ensemble des JSON
    utilisés.

    Si une séance est ajoutée, supprimée ou modifiée,
    l'empreinte change.
    """

    calcul = hashlib.sha256()

    for fichier in sorted(
        fichiers,
        key=lambda f: f.name.lower(),
    ):
        calcul.update(
            fichier.name.encode("utf-8")
        )

        calcul.update(
            b"\0"
        )

        calcul.update(
            fichier.read_bytes()
        )

        calcul.update(
            b"\0"
        )

    return calcul.hexdigest()


# =========================================================
# ANTI-DOUBLON / FRAÎCHEUR
# =========================================================

def synthese_deja_a_jour(
    output_path: Path,
    empreinte_sources: str,
) -> bool:
    """
    Vérifie qu'une synthèse existe déjà pour exactement
    les mêmes fichiers sources.
    """

    if not output_path.exists():
        return False

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


# =========================================================
# PRÉPARATION DES DONNÉES POUR TERRA
# =========================================================

def preparer_seances_pour_api(
    seances: list[
        tuple[Path, DonneesCliniques]
    ],
) -> str:
    """
    Prépare un JSON propre avec toutes les séances.

    Aucun nom réel n'est ajouté au prompt.
    """

    contenu = []

    for fichier, donnees in seances:
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


# =========================================================
# SYNTHÈSE PAR GPT-5.6 TERRA
# =========================================================

def generer_synthese(
    client: OpenAI,
    seances: list[
        tuple[Path, DonneesCliniques]
    ],
):
    """
    Génère une synthèse longitudinale prudente à partir
    des JSON séance par séance.
    """

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
        model=MODEL,

        reasoning={
            "effort": REASONING_EFFORT,
        },

        store=False,

        max_output_tokens=MAX_OUTPUT_TOKENS,

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
            "La réponse de synthèse est "
            "incomplète. "
            f"Détails : {details}"
        )

    synthese = reponse.output_parsed

    if synthese is None:
        raise RuntimeError(
            "Terra n'a pas retourné de synthèse "
            "structurée valide."
        )

    return synthese, reponse


# =========================================================
# CONTRÔLE DÉTERMINISTE DES DATES SOURCES
# =========================================================

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
            "La synthèse contient des dates sources "
            f"inexistantes : {invalides}"
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
            "Les entrées evolution suivantes ne comparent "
            "pas au moins deux séances distinctes : "
            f"{positions}"
        )


# =========================================================
# MÉTADONNÉES ET ENREGISTREMENT
# =========================================================

def construire_fichier_final(
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

        patient_id=PATIENT_ID,

        modele=MODEL,

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

        empreinte_sources_sha256=(
            empreinte_sources
        ),
    )

    return FichierSyntheseLongitudinale(
        metadata=metadata,
        synthese=synthese,
    )


def enregistrer_synthese(
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


# =========================================================
# TOKENS
# =========================================================

def afficher_utilisation(
    reponse,
) -> None:

    print("\n--- UTILISATION API ---")

    usage = getattr(
        reponse,
        "usage",
        None,
    )

    if usage is None:
        print(
            "Informations d'utilisation "
            "indisponibles."
        )
        return

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

    print(
        f"Tokens d'entrée : "
        f"{input_tokens}"
    )

    print(
        f"Tokens de sortie : "
        f"{output_tokens}"
    )

    print(
        f"Tokens totaux : "
        f"{total_tokens}"
    )


# =========================================================
# MAIN
# =========================================================

def main() -> None:

    print("=" * 70)
    print(
        "PSYCHO IA — TEST DE SYNTHÈSE "
        "LONGITUDINALE"
    )
    print("=" * 70)

    print(
        f"Patient test : {PATIENT_ID}"
    )

    print(
        f"Modèle : {MODEL}"
    )

    print(
        f"Raisonnement : "
        f"{REASONING_EFFORT}"
    )

    print(
        f"Source : {DONNEES_DIR}"
    )

    print(
        f"Destination : {OUTPUT_PATH}"
    )

    try:
        fichiers = (
            obtenir_fichiers_cliniques()
        )

        seances = charger_seances(
            fichiers
        )

        print(
            f"\nNombre de séances trouvées : "
            f"{len(seances)}"
        )

        for fichier, donnees in seances:
            print(
                f"- {donnees.date_seance} "
                f"→ {fichier.name}"
            )

        if len(seances) < 2:
            print(
                "\nAttention : une synthèse "
                "longitudinale est beaucoup plus "
                "pertinente à partir de plusieurs "
                "séances."
            )

        empreinte_sources = (
            calculer_empreinte_sources(
                fichiers
            )
        )

        print(
            "\nEmpreinte des sources : "
            f"{empreinte_sources[:16]}..."
        )

        # -------------------------------------------------
        # ANTI-DOUBLON
        # -------------------------------------------------

        if synthese_deja_a_jour(
            OUTPUT_PATH,
            empreinte_sources,
        ):
            print(
                "\nSynthèse longitudinale déjà "
                "à jour."
            )

            print(
                "Aucun nouvel appel API "
                "n'a été effectué."
            )

            print(
                f"Fichier existant : "
                f"{OUTPUT_PATH}"
            )

            return

        # -------------------------------------------------
        # APPEL API
        # -------------------------------------------------

        client = charger_client()

        print(
            "\nGénération de la synthèse "
            "longitudinale avec "
            "GPT-5.6 Terra..."
        )

        synthese, reponse = (
            generer_synthese(
                client,
                seances,
            )
        )

        # -------------------------------------------------
        # CONTRÔLE DÉTERMINISTE
        # -------------------------------------------------

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

        # -------------------------------------------------
        # FICHIER FINAL
        # -------------------------------------------------

        fichier_final = (
            construire_fichier_final(
                synthese,
                seances,
                empreinte_sources,
            )
        )

        enregistrer_synthese(
            fichier_final,
            OUTPUT_PATH,
        )

        # -------------------------------------------------
        # AFFICHAGE
        # -------------------------------------------------

        print(
            "\n--- SYNTHÈSE "
            "LONGITUDINALE ---\n"
        )

        print(
            json.dumps(
                synthese.model_dump(
                    mode="json"
                ),
                ensure_ascii=False,
                indent=2,
            )
        )

        afficher_utilisation(
            reponse
        )

        print(
            "\n--- ENREGISTREMENT ---"
        )

        print(
            f"Fichier créé : "
            f"{OUTPUT_PATH}"
        )

        print(
            "\nVérifie manuellement surtout :"
        )

        print(
            "- les problematiques_actuelles"
        )

        print(
            "- l'évolution"
        )

        print(
            "- la réponse aux interventions"
        )

        print(
            "- les points à reprendre"
        )

        print(
            "- qu'aucun diagnostic ou lien "
            "causal n'a été inventé"
        )

    except FileNotFoundError as erreur:
        print(
            f"\nErreur de fichier : "
            f"{erreur}"
        )
        sys.exit(1)

    except ValueError as erreur:
        print(
            f"\nErreur de validation : "
            f"{erreur}"
        )
        sys.exit(1)

    except RuntimeError as erreur:
        print(
            f"\nErreur de traitement : "
            f"{erreur}"
        )
        sys.exit(1)

    except Exception as erreur:
        print(
            "\nErreur lors de l'appel "
            "à l'API : "
            f"{type(erreur).__name__}: "
            f"{erreur}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
