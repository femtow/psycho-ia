from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

MODEL = "gpt-5.6-terra"

TRANSCRIPTION_PATH = (
    BASE_DIR
    / "patients_test"
    / "P-0001"
    / "transcriptions"
    / "2026-08-01_PA.txt"
)

OUTPUT_DIR = (
    BASE_DIR
    / "patients_test"
    / "P-0001"
    / "donnees_cliniques"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "2026-08-01_PA.json"
)

MAX_OUTPUT_TOKENS = 2000


# ---------------------------------------------------------
# SCHÉMA DES DONNÉES CLINIQUES
# ---------------------------------------------------------

class DonneesCliniques(BaseModel):
    """
    Structure obligatoire de la sortie produite par le modèle.

    extra="forbid" interdit l'ajout de catégories
    qui ne figurent pas dans ce schéma.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    date_seance: date | None = Field(
        description=(
            "Date explicite de la séance au format AAAA-MM-JJ. "
            "Valeur null si la date n'est pas présente ou certaine."
        )
    )

    faits_rapportes: list[str] = Field(
        description=(
            "Faits, événements, symptômes, circonstances ou "
            "expériences explicitement rapportés dans la note "
            "et ne relevant pas plus précisément d'une autre catégorie."
        )
    )

    emotions: list[str] = Field(
        description=(
            "Émotions explicitement indiquées, sans les déduire "
            "à partir des pensées ou des comportements."
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
            "présents, hors évitements, interventions du thérapeute "
            "et tâches interséances."
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
            "ou réalisés pendant la séance."
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


# ---------------------------------------------------------
# CHARGEMENT DU CLIENT OPENAI
# ---------------------------------------------------------

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
            "La variable OPENAI_API_KEY est absente "
            "ou vide dans le fichier .env."
        )

    return OpenAI(api_key=api_key)


# ---------------------------------------------------------
# LECTURE DE LA TRANSCRIPTION
# ---------------------------------------------------------

def lire_transcription(
    transcription_path: Path,
) -> str:
    """
    Lit la transcription enregistrée en UTF-8.
    """

    if not transcription_path.exists():
        raise FileNotFoundError(
            "Transcription introuvable : "
            f"{transcription_path}"
        )

    if not transcription_path.is_file():
        raise ValueError(
            "Le chemin de transcription ne correspond "
            f"pas à un fichier : {transcription_path}"
        )

    transcription = transcription_path.read_text(
        encoding="utf-8-sig"
    ).strip()

    if not transcription:
        raise ValueError(
            "Le fichier de transcription est vide."
        )

    return transcription


# ---------------------------------------------------------
# EXTRACTION CLINIQUE
# ---------------------------------------------------------

def extraire_donnees_cliniques(
    client: OpenAI,
    transcription: str,
):
    """
    Transforme la transcription en données structurées.

    Le modèle doit uniquement organiser les informations
    présentes, sans produire d'analyse fonctionnelle.
    """

    prompt_systeme = (
        "Tu extrais des informations structurées à partir "
        "d'une transcription de notes de séance de psychothérapie.\n\n"

        "Tu dois rester strictement fidèle au texte source.\n\n"

        "Règles impératives :\n"
        "- N'invente aucune information.\n"
        "- Ne pose aucun diagnostic.\n"
        "- Ne produis aucune analyse fonctionnelle.\n"
        "- Ne déduis aucune émotion, cognition ou intention.\n"
        "- Ne crée aucun lien causal absent de la note.\n"
        "- Ne transforme pas une possibilité en certitude.\n"
        "- Ne transforme pas une crainte en événement réellement survenu.\n"
        "- Ne transforme pas une proposition en tâche effectivement réalisée.\n"
        "- Utilise des formulations courtes et proches du texte source.\n"
        "- Utilise une liste vide lorsqu'une catégorie n'est pas renseignée.\n"
        "- Normalise la date au format AAAA-MM-JJ uniquement si elle "
        "est explicitement identifiable.\n"
        "- Mets date_seance à null si la date est absente ou incertaine.\n"
        "- Une émotion est un état affectif, pas une pensée ou un symptôme.\n"
        "- Une cognition est une pensée, une anticipation, une croyance "
        "ou une interprétation.\n"
        "- Un évitement doit être explicitement mentionné ou décrit.\n"
        "- Les interventions concernent ce qui est proposé ou réalisé "
        "dans le cadre thérapeutique.\n"
        "- Les tâches interséances concernent ce qui est demandé après "
        "la séance.\n"
        "- Évite les doublons inutiles entre catégories.\n"
        "- Un même élément peut toutefois apparaître dans interventions "
        "et taches_interseances si la note indique explicitement qu'il "
        "a été proposé puis donné comme exercice.\n"
        "- Place tout passage marqué [illisible] ou [mot incertain] "
        "dans elements_incertains.\n"
        "- En cas de doute sur une information, ne la classe pas comme "
        "certaine : place-la dans elements_incertains."
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
            "effort": "none"
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

        text_format=DonneesCliniques,
    )

    if getattr(reponse, "status", None) == "incomplete":
        details = getattr(
            reponse,
            "incomplete_details",
            None,
        )

        raise RuntimeError(
            "La réponse de l'API est incomplète. "
            f"Détails : {details}"
        )

    donnees = reponse.output_parsed

    if donnees is None:
        raise RuntimeError(
            "Le modèle n'a pas retourné de données "
            "cliniques structurées valides."
        )

    return donnees, reponse


# ---------------------------------------------------------
# ENREGISTREMENT JSON
# ---------------------------------------------------------

def enregistrer_donnees_cliniques(
    donnees: DonneesCliniques,
    output_path: Path,
) -> None:
    """
    Enregistre le résultat en JSON lisible et en UTF-8.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    contenu = donnees.model_dump(
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


# ---------------------------------------------------------
# AFFICHAGE DES TOKENS
# ---------------------------------------------------------

def afficher_utilisation(reponse) -> None:
    """
    Affiche le nombre de tokens consommés.
    """

    print("\n--- UTILISATION API ---")

    usage = getattr(
        reponse,
        "usage",
        None,
    )

    if usage is None:
        print(
            "Informations d'utilisation indisponibles."
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
    print("=" * 70)
    print("PSYCHO IA — TEST D'EXTRACTION CLINIQUE")
    print("=" * 70)

    print(f"Modèle : {MODEL}")
    print(f"Transcription : {TRANSCRIPTION_PATH}")
    print(f"Destination : {OUTPUT_PATH}")

    try:
        # Protection contre un second appel API involontaire.
        if OUTPUT_PATH.exists():
            print(
                "\nDonnées cliniques déjà extraites."
            )
            print(
                "Aucun nouvel appel API n'a été effectué."
            )
            print(
                f"Fichier existant : {OUTPUT_PATH}"
            )
            return

        transcription = lire_transcription(
            TRANSCRIPTION_PATH
        )

        print("\n--- TRANSCRIPTION LUE ---\n")
        print(transcription)

        client = charger_client()

        print(
            "\nExtraction clinique structurée "
            "avec GPT-5.6 Terra..."
        )

        donnees, reponse = (
            extraire_donnees_cliniques(
                client,
                transcription,
            )
        )

        enregistrer_donnees_cliniques(
            donnees,
            OUTPUT_PATH,
        )

        donnees_affichage = donnees.model_dump(
            mode="json"
        )

        print("\n--- DONNÉES CLINIQUES OBTENUES ---\n")

        print(
            json.dumps(
                donnees_affichage,
                ensure_ascii=False,
                indent=2,
            )
        )

        afficher_utilisation(reponse)

        print("\n--- ENREGISTREMENT ---")
        print(
            f"Fichier créé : {OUTPUT_PATH}"
        )

        print(
            "\nVérifie manuellement que rien n'a été "
            "inventé ou interprété."
        )

    except FileNotFoundError as erreur:
        print(
            f"\nErreur de fichier : {erreur}"
        )
        sys.exit(1)

    except ValueError as erreur:
        print(
            f"\nErreur de données : {erreur}"
        )
        sys.exit(1)

    except RuntimeError as erreur:
        print(
            f"\nErreur de traitement : {erreur}"
        )
        sys.exit(1)

    except Exception as erreur:
        print(
            "\nErreur lors de l'appel à l'API : "
            f"{type(erreur).__name__}: {erreur}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()