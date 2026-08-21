"""CLI explicite de l'analyse fonctionnelle synchronique V1."""

from __future__ import annotations

from pathlib import Path
import argparse
import os

from dotenv import load_dotenv

from analyse_fonctionnelle_episode import (
    ErreurAnalyseFonctionnelle,
    charger_analyse_en_cache,
    chemins_sortie_analyse,
    construire_prompt_utilisateur,
    enregistrer_analyse,
    generer_analyse_fonctionnelle,
    preparer_contexte_analyse,
    rendre_analyse_clinicien,
)


def construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        description=(
            "Analyse un episode clinique fictif explicitement choisi, sans detection automatique."
        )
    )
    sous_commandes = parseur.add_subparsers(dest="commande", required=True)
    for nom in ("preparer", "generer"):
        commande = sous_commandes.add_parser(nom)
        commande.add_argument("--dossier-patient", type=Path, required=True)
        commande.add_argument("--transcription", required=True)
        commande.add_argument("--episode", required=True)
        commande.add_argument(
            "--source-complementaire",
            action="append",
            default=[],
            help="Transcription confirmee explicitement choisie pour un effet differe ou une variation.",
        )
        if nom == "generer":
            commande.add_argument(
                "--autoriser-appel-api",
                action="store_true",
                help="Autorisation explicite d'un unique appel Terra si le cache est absent.",
            )
    return parseur


def afficher_preparation(contexte) -> None:
    print("\nANALYSE FONCTIONNELLE SYNCHRONIQUE V1")
    print("-" * 60)
    print(f"Patient fictif : {contexte.dossier_id_pseudonymise}")
    print(f"Episode choisi par le clinicien : {contexte.episode_decrit_par_clinicien}")
    print(f"Source principale : {contexte.source_principale.transcription}")
    for source in contexte.sources_complementaires:
        print(f"Source complementaire explicite : {source.transcription}")
    print(f"Elements JSON atomiques disponibles : {len(contexte.catalogue.entrees)}")
    print("Assertions JSON validees individuellement : non")
    print("Detection automatique d'episode : non")
    print("Diagnostic, protocole et plan de traitement : interdits")
    print(f"Empreinte de generation : {contexte.empreinte_generation}")
    chemin_json, chemin_markdown = chemins_sortie_analyse(contexte)
    print(f"Sortie JSON prevue : {chemin_json}")
    print(f"Rendu clinique prevu : {chemin_markdown}")


def charger_client():
    racine = Path(__file__).resolve().parent.parent
    load_dotenv(racine / ".env")
    cle = os.getenv("OPENAI_API_KEY")
    if not cle:
        raise RuntimeError("OPENAI_API_KEY absente du fichier .env.")
    from openai import OpenAI

    return OpenAI(api_key=cle)


def afficher_utilisation(reponse) -> None:
    utilisation = getattr(reponse, "usage", None)
    if utilisation is None:
        return
    print("\nUTILISATION API")
    print(f"Tokens d'entree : {getattr(utilisation, 'input_tokens', 0)}")
    print(f"Tokens de sortie : {getattr(utilisation, 'output_tokens', 0)}")
    print(f"Tokens totaux : {getattr(utilisation, 'total_tokens', 0)}")


def main() -> None:
    arguments = construire_parseur().parse_args()
    try:
        contexte = preparer_contexte_analyse(
            arguments.dossier_patient,
            arguments.transcription,
            arguments.episode,
            tuple(arguments.source_complementaire),
        )
        afficher_preparation(contexte)
        cache = charger_analyse_en_cache(contexte)
        if cache is not None:
            print("\nResultat : analyse deja a jour, aucun appel API.")
            print("\n" + rendre_analyse_clinicien(cache))
            return
        if arguments.commande == "preparer":
            print("\nResultat : contexte valide. Aucun appel API effectue.")
            return
        if not arguments.autoriser_appel_api:
            raise ValueError(
                "Ajoutez --autoriser-appel-api apres avoir verifie le contexte affiche."
            )
        analyse, reponse = generer_analyse_fonctionnelle(
            charger_client(),
            contexte,
        )
        afficher_utilisation(reponse)
        chemin_json, chemin_markdown = enregistrer_analyse(analyse, contexte)
        print("\nAnalyse creee.")
        print(f"JSON : {chemin_json}")
        print(f"Rendu clinique : {chemin_markdown}")
        print("\n" + rendre_analyse_clinicien(analyse))
    except (ErreurAnalyseFonctionnelle, OSError, RuntimeError, ValueError) as erreur:
        if isinstance(erreur, ErreurAnalyseFonctionnelle):
            afficher_utilisation(erreur.reponse)
        raise SystemExit(f"Operation impossible : {erreur}") from erreur


if __name__ == "__main__":
    main()
