"""CLI minimale de confirmation d'une transcription clinique fictive."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import argparse
import json
import os
import shutil
import tempfile

from source_clinique_confirmee import (
    ErreurSourceClinique,
    ServiceSourceCliniqueConfirmeeV1,
    calculer_sha256_octets,
    enregistrer_provenance_json_depuis_source_confirmee,
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


def preparer_regeneration_json(
    dossier_patient: Path,
    nom_transcription: str,
) -> tuple[ServiceSourceCliniqueConfirmeeV1, Path, str]:
    transcription = _trouver_transcription(dossier_patient, nom_transcription)
    date_seance = date.fromisoformat(transcription.stem[:10])
    service = ServiceSourceCliniqueConfirmeeV1(
        dossier_patient,
        transcription,
        date_seance,
        dossier_patient.name,
    )
    etat = service.verifier_autorite()
    if not etat.est_confirmee or etat.confirmation_id is None:
        raise ValueError("La version courante n'est pas confirmee.")
    transcription_confirmee = service.lire_transcription()
    dossier = service._charger_dossier()
    if dossier is None:
        raise ValueError("Le dossier de source confirmee est absent.")
    version = dossier.versions[-1]
    chemin_version = dossier_patient.joinpath(*Path(version.document_courant).parts)
    empreinte = calculer_sha256_octets(chemin_version.read_bytes())
    json_path = (
        dossier_patient
        / "donnees_cliniques"
        / f"{transcription.stem}.json"
    )
    print("\nREGENERATION CIBLEE DU JSON CLINIQUE")
    print("-" * 60)
    print(f"Patient fictif : {dossier_patient.name}")
    print(f"Transcription : {nom_transcription}")
    print(f"Version confirmee : {etat.version}")
    print(f"Confirmation : {etat.confirmation_id}")
    print(f"Empreinte utilisee : {empreinte}")
    print(f"JSON remplace apres validation : {json_path}")
    print("Modele : gpt-5.6-terra")
    print("Appels prevus : 1")
    print("OCR : aucun appel")
    print("Produit : un JSON clinique V2 regenere depuis la V2 confirmee")
    print("Provenance : creee seulement apres validation du nouveau JSON")
    print(f"JSON actuellement lie : {'oui' if etat.json_clinique_lie else 'non'}")
    return service, json_path, transcription_confirmee


def regenerer_json_confirme(
    dossier_patient: Path,
    nom_transcription: str,
    autoriser_appel_api: bool,
) -> None:
    service, json_path, transcription = preparer_regeneration_json(
        dossier_patient,
        nom_transcription,
    )
    if service.verifier_autorite().json_clinique_lie:
        print("\nLe JSON courant est deja lie exactement. Aucun appel API.")
        return
    if not autoriser_appel_api:
        raise ValueError(
            "Ajoutez --autoriser-appel-api apres validation explicite de la commande."
        )

    from main import (
        charger_client,
        extraire_donnees_cliniques,
        verifier_date_donnees_cliniques,
    )

    client = charger_client()
    donnees, reponse, _ = extraire_donnees_cliniques(
        client,
        transcription,
        service.date_seance,
    )
    donnees = verifier_date_donnees_cliniques(
        donnees,
        service.date_seance,
    )
    contenu = (
        json.dumps(
            donnees.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    ancien_contenu = json_path.read_bytes() if json_path.is_file() else None
    provenance_existait = service.chemin_provenance_json.is_file()
    try:
        _ecrire_atomique(json_path, contenu)
        dossier = service._charger_dossier()
        if dossier is None:
            raise ValueError("Le dossier de source confirmee est absent.")
        version = dossier.versions[-1]
        chemin_version = dossier_patient.joinpath(
            *Path(version.document_courant).parts
        )
        enregistrer_provenance_json_depuis_source_confirmee(
            service,
            json_path,
            calculer_sha256_octets(chemin_version.read_bytes()),
        )
        if not service.verifier_autorite().json_clinique_lie:
            raise ValueError("La provenance exacte n'a pas pu etre validee.")
    except Exception:
        if ancien_contenu is None:
            json_path.unlink(missing_ok=True)
        else:
            _ecrire_atomique(json_path, ancien_contenu)
        if not provenance_existait:
            service.chemin_provenance_json.unlink(missing_ok=True)
        raise

    utilisation = getattr(reponse, "usage", None)
    print("\nJSON clinique V2 regenere et lie a la V2 confirmee.")
    print(f"JSON : {json_path}")
    print(f"Provenance : {service.chemin_provenance_json}")
    if utilisation is not None:
        print(f"Tokens d'entree : {getattr(utilisation, 'input_tokens', 0)}")
        print(f"Tokens de sortie : {getattr(utilisation, 'output_tokens', 0)}")
        print(f"Tokens totaux : {getattr(utilisation, 'total_tokens', 0)}")


def _ecrire_atomique(chemin: Path, contenu: bytes) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=chemin.parent,
            prefix=f".{chemin.name}.",
            suffix=".tmp",
            delete=False,
        ) as fichier:
            fichier.write(contenu)
            fichier.flush()
            os.fsync(fichier.fileno())
            temporaire = Path(fichier.name)
        os.replace(temporaire, chemin)
    finally:
        if temporaire is not None and temporaire.exists():
            temporaire.unlink()


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
    for nom in ("preparer-regeneration-json", "regenerer-json-confirme"):
        regeneration = sous_commandes.add_parser(nom)
        regeneration.add_argument("--dossier-patient", type=Path, required=True)
        regeneration.add_argument("--transcription", required=True)
        if nom == "regenerer-json-confirme":
            regeneration.add_argument(
                "--autoriser-appel-api",
                action="store_true",
            )
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
        elif arguments.commande == "revoir":
            revoir_source(arguments.dossier_patient, arguments.transcription)
        elif arguments.commande == "preparer-regeneration-json":
            preparer_regeneration_json(
                arguments.dossier_patient.resolve(strict=True),
                arguments.transcription,
            )
            print("\nAucun appel API effectue.")
        else:
            regenerer_json_confirme(
                arguments.dossier_patient.resolve(strict=True),
                arguments.transcription,
                arguments.autoriser_appel_api,
            )
    except (ErreurSourceClinique, OSError, ValueError) as erreur:
        raise SystemExit(f"Operation impossible : {erreur}") from erreur


if __name__ == "__main__":
    main()
