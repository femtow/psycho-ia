"""CLI minimale de confirmation d'une transcription clinique fictive."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import argparse
import shutil
import tempfile

from source_clinique_confirmee import (
    ErreurSourceClinique,
    ServiceSourceCliniqueConfirmeeV1,
)


def preparer_smoke(source_patient: Path, nom_transcription: str) -> Path:
    source = source_patient.resolve(strict=True)
    transcription = _trouver_transcription(source, nom_transcription)
    racine_temporaire = Path(tempfile.mkdtemp(prefix="psycho-ia-source-clinique-"))
    destination = racine_temporaire / source.name
    (destination / "Transcriptions").mkdir(parents=True)
    shutil.copy2(transcription, destination / "Transcriptions" / transcription.name)

    profil = source / "profil.json"
    if profil.is_file():
        shutil.copy2(profil, destination / profil.name)

    json_source = source / "donnees_cliniques" / f"{transcription.stem}.json"
    if json_source.is_file():
        dossier_json = destination / "donnees_cliniques"
        dossier_json.mkdir()
        shutil.copy2(json_source, dossier_json / json_source.name)
    return destination


def revoir_source(dossier_patient: Path, nom_transcription: str) -> None:
    transcription = _trouver_transcription(dossier_patient, nom_transcription)
    date_seance = date.fromisoformat(transcription.stem[:10])
    service = ServiceSourceCliniqueConfirmeeV1(
        dossier_patient,
        transcription,
        date_seance,
        dossier_patient.name,
    )
    print("\n" + "-" * 60)
    print(f"Seance du {date_seance.strftime('%d/%m/%Y')}")
    print("\nTranscription :\n")
    print(service.lire_transcription())
    passages = service.passages_signales()
    if passages:
        print("\nPassages signales :")
        for passage in passages:
            print(f"- {passage}")
    print("\n[C] Confirmer  [M] Corriger  [Q] Quitter")
    choix = input("Choix : ").strip().upper()
    if choix == "Q":
        print("Aucune confirmation enregistree.")
        return

    clinicien_id = input("Identifiant du clinicien : ").strip()
    if not clinicien_id:
        raise ValueError("L'identifiant du clinicien est obligatoire.")

    if choix == "C":
        resultat = service.confirmer(
            clinicien_id=clinicien_id,
            confirmation_explicite=True,
            accepter_incertitudes=True,
        )
    elif choix == "M":
        avant = service.lire_transcription()
        fragment = input("Texte exact a remplacer : ")
        remplacement = input("Nouveau texte : ")
        if avant.count(fragment) != 1:
            raise ValueError(
                "Le texte a remplacer doit apparaitre exactement une fois."
            )
        apres = avant.replace(fragment, remplacement, 1)
        print("\nAVANT :")
        print(fragment)
        print("\nAPRES :")
        print(remplacement)
        confirme = input("Enregistrer et confirmer cette correction ? [O/N] : ").strip().upper()
        if confirme != "O":
            print("Aucune correction enregistree.")
            return
        resultat = service.corriger_et_confirmer(
            apres,
            clinicien_id=clinicien_id,
            confirmation_explicite=True,
            accepter_incertitudes=True,
        )
    else:
        raise ValueError("Choix inconnu.")

    etat = resultat.etat
    print("\nSource clinique confirmee")
    print(f"Patient fictif : {etat.dossier_id_pseudonymise}")
    print(f"Seance : {etat.date_seance.strftime('%d/%m/%Y')}")
    print(f"Version : {etat.version}")
    print("Confirmation enregistree.")
    if not etat.json_clinique_lie:
        print(
            "Le JSON existant ne porte pas encore de provenance exacte vers "
            "cette version; il devra etre regenere ou relie ulterieurement."
        )


def _trouver_transcription(dossier_patient: Path, nom: str) -> Path:
    for dossier in ("Transcriptions", "transcriptions"):
        chemin = dossier_patient / dossier / nom
        if chemin.is_file():
            return chemin
    raise FileNotFoundError(f"Transcription introuvable : {nom}")


def construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        description="Confirmation locale d'une source clinique fictive"
    )
    sous_commandes = parseur.add_subparsers(dest="commande", required=True)
    revoir = sous_commandes.add_parser("revoir")
    revoir.add_argument("--dossier-patient", type=Path, required=True)
    revoir.add_argument("--transcription", required=True)
    smoke = sous_commandes.add_parser("smoke")
    smoke.add_argument("--source-patient", type=Path, required=True)
    smoke.add_argument("--transcription", required=True)
    return parseur


def main() -> None:
    arguments = construire_parseur().parse_args()
    try:
        if arguments.commande == "smoke":
            dossier = preparer_smoke(
                arguments.source_patient,
                arguments.transcription,
            )
            print(f"Copie temporaire : {dossier}")
            revoir_source(dossier, arguments.transcription)
        else:
            revoir_source(arguments.dossier_patient, arguments.transcription)
    except (ErreurSourceClinique, OSError, ValueError) as erreur:
        raise SystemExit(f"Operation impossible : {erreur}") from erreur


if __name__ == "__main__":
    main()
