"""Adaptateur terminal minimal pour la validation clinicien V1."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import shutil
import tempfile

from catalogue_sources_longitudinales import construire_catalogue_sources_patient
from generation_propositions_longitudinales import (
    RevueTacheTerra,
    SortieTerraPropositionsV1,
    construire_fichier_propositions,
    construire_plan_revue_taches,
    integrer_revues_taches,
)
from modeles_longitudinaux import (
    RegistreLongitudinalV1,
    StatutEpistemique,
    enregistrer_propositions,
    enregistrer_registre,
)
from validation_clinicien_longitudinale import (
    STATUTS_MODIFICATION_AUTORISES,
    ErreurValidationClinicien,
    ServiceValidationClinicienV1,
    TypeDecisionClinicienV1,
)


DOSSIER_LONGITUDINAL = "longitudinal"
NOM_PROPOSITIONS = "propositions_smoke.json"
NOM_REGISTRE = "registre_longitudinal.json"
NOM_DECISIONS = "decisions_clinicien.json"


def creer_service(dossier_patient: Path) -> ServiceValidationClinicienV1:
    dossier = dossier_patient / DOSSIER_LONGITUDINAL
    return ServiceValidationClinicienV1(
        dossier_patient,
        dossier / NOM_PROPOSITIONS,
        dossier / NOM_REGISTRE,
        dossier / NOM_DECISIONS,
    )


def preparer_smoke(source_patient: Path) -> Path:
    if not source_patient.is_dir():
        raise FileNotFoundError(f"Dossier fictif introuvable : {source_patient}")
    racine = Path(tempfile.mkdtemp(prefix="psycho-ia-validation-"))
    destination = racine / source_patient.name
    destination.mkdir()
    shutil.copytree(
        source_patient / "donnees_cliniques",
        destination / "donnees_cliniques",
    )
    profil = source_patient / "profil.json"
    if profil.is_file():
        shutil.copy2(profil, destination / profil.name)

    catalogue = construire_catalogue_sources_patient(
        destination,
        destination.name,
    )
    plan = construire_plan_revue_taches(catalogue)
    revues = tuple(
        RevueTacheTerra(
            task_id=str(tache["task_id"]),
            source_consigne_id=str(tache["source_consigne_id"]),
            statut_resultat_propose="resultat_non_documente",
            justification="Fixture hors ligne : resultat laisse a valider dans le smoke test.",
        )
        for tache in plan
    )
    sortie = integrer_revues_taches(
        SortieTerraPropositionsV1(revues_taches=revues),
        catalogue,
        plan,
    )
    propositions = construire_fichier_propositions(
        sortie,
        catalogue,
        destination,
    )
    registre = RegistreLongitudinalV1(
        dossier_id_pseudonymise=destination.name,
        version_registre=1,
        date_coupure=catalogue.date_coupure,
        statut_documentaire="valide_clinicien",
        references_sources=tuple(
            entree.reference for entree in catalogue.entrees
        ),
    )
    dossier_longitudinal = destination / DOSSIER_LONGITUDINAL
    enregistrer_propositions(
        propositions,
        dossier_longitudinal / NOM_PROPOSITIONS,
    )
    enregistrer_registre(
        registre,
        dossier_longitudinal / NOM_REGISTRE,
    )
    return destination


def afficher_source(source) -> None:
    contenu = (
        source.contenu
        if isinstance(source.contenu, str)
        else json.dumps(source.contenu, ensure_ascii=False)
    )
    print(f"  {source.date_seance} | {source.categorie} | {contenu}")


def demander_confirmation(message: str) -> bool:
    return input(f"{message} [oui/N] : ").strip().lower() == "oui"


def choisir_statut(type_objet, statut_actuel: StatutEpistemique) -> StatutEpistemique:
    autorises = STATUTS_MODIFICATION_AUTORISES[type_objet]
    print("Statut actuel :", statut_actuel.value)
    print("  explicite : directement confirme comme tel par le clinicien")
    print("  synthese_prudente : regroupement prudent de sources")
    print("  inconnu_a_explorer : information incertaine a clarifier")
    print("Statuts autorises :", ", ".join(sorted(s.value for s in autorises)))
    valeur = input("Statut final : ").strip()
    try:
        statut = StatutEpistemique(valeur)
    except ValueError as erreur:
        raise ValueError("Statut epistemique inconnu.") from erreur
    if statut not in autorises:
        raise ValueError("Statut interdit pour ce type d'objet.")
    return statut


def revoir_dossier(dossier_patient: Path) -> None:
    service = creer_service(dossier_patient)
    validateur_id = input("Identifiant du clinicien : ").strip()
    if not validateur_id:
        raise ValueError("L'identifiant du clinicien est obligatoire.")
    traites_session: set[str] = set()

    rejets = service.lister_rejets_techniques()
    if rejets:
        print("\nPROPOSITIONS REJETEES AUTOMATIQUEMENT (non promotables)")
        for rejet in rejets:
            print(f"- {rejet.type_objet.value}: {rejet.contenu_principal}")
            print(f"  {rejet.code}: {rejet.motif}")

    while True:
        vues = service.lister_propositions()
        disponibles = [
            vue
            for vue in vues
            if vue.decision_terminale is None
            and vue.proposition_id not in traites_session
        ]
        if not disponibles:
            print("\nAucune autre proposition a revoir dans cette session.")
            break
        vue = disponibles[0]
        print("\n" + "-" * 64)
        print(f"PROPOSITION {len(vues) - len(disponibles) + 1} / {len(vues)}")
        print("Type :", vue.type_objet.value)
        print("Statut epistemique :", ", ".join(s.value for s in vue.statuts_epistemiques))
        print("Statut d'action :", vue.statut_action)
        print("Proposition :", vue.contenu_principal)
        print("Pourquoi ?", vue.justification)
        print("Sources cliniques :")
        for source in vue.sources:
            afficher_source(source)
        choix = input("Decision [A]ccepter [M]odifier [R]efuser [D]ifferer [Q]uitter : ").strip().upper()
        if choix == "Q":
            print("Validation interrompue sans decision supplementaire.")
            break
        commentaire = None
        try:
            if choix == "A":
                confirme = demander_confirmation(
                    "Confirmez-vous explicitement l'acceptation et la promotion"
                )
                resultat = service.accepter(
                    vue.proposition_id,
                    validateur_id=validateur_id,
                    empreinte_fichier_affichee=vue.empreinte_fichier_propositions_sha256,
                    version_registre_affichee=vue.version_registre,
                    confirmation_explicite=confirme,
                )
            elif choix == "M":
                nouvelle = input("Nouvelle formulation : ").strip()
                print("AVANT :", vue.contenu_principal)
                print("APRES :", nouvelle)
                print("Sources rappelees :")
                for source in vue.sources:
                    afficher_source(source)
                sources_confirmees = demander_confirmation(
                    "Confirmez-vous que les sources soutiennent encore cette formulation"
                )
                statut_actuel = vue.statuts_epistemiques[0]
                statut = choisir_statut(vue.type_objet, statut_actuel)
                statut_confirme = demander_confirmation(
                    f"Confirmez-vous explicitement le statut {statut.value}"
                )
                print("Resume final :", nouvelle, "|", statut.value)
                promotion_confirmee = demander_confirmation(
                    "Confirmez-vous la modification et la promotion"
                )
                resultat = service.modifier_puis_accepter(
                    vue.proposition_id,
                    nouvelle_formulation=nouvelle,
                    statut_epistemique_final=statut,
                    validateur_id=validateur_id,
                    empreinte_fichier_affichee=vue.empreinte_fichier_propositions_sha256,
                    version_registre_affichee=vue.version_registre,
                    confirmation_sources=sources_confirmees,
                    confirmation_statut_epistemique=statut_confirme,
                    confirmation_explicite=promotion_confirmee,
                )
            elif choix == "R":
                commentaire = input("Motif facultatif : ").strip() or None
                confirme = demander_confirmation("Confirmez-vous explicitement le refus")
                resultat = service.refuser(
                    vue.proposition_id,
                    validateur_id=validateur_id,
                    empreinte_fichier_affichee=vue.empreinte_fichier_propositions_sha256,
                    version_registre_affichee=vue.version_registre,
                    confirmation_explicite=confirme,
                    commentaire=commentaire,
                )
            elif choix == "D":
                commentaire = input("Commentaire facultatif : ").strip() or None
                confirme = demander_confirmation("Confirmez-vous le report de la decision")
                resultat = service.differer(
                    vue.proposition_id,
                    validateur_id=validateur_id,
                    empreinte_fichier_affichee=vue.empreinte_fichier_propositions_sha256,
                    version_registre_affichee=vue.version_registre,
                    confirmation_explicite=confirme,
                    commentaire=commentaire,
                )
                traites_session.add(vue.proposition_id)
            else:
                print("Choix invalide. Aucune decision enregistree.")
                continue
        except (ErreurValidationClinicien, ValueError) as erreur:
            print("DECISION NON APPLIQUEE :", erreur)
            continue
        print("Decision enregistree :", resultat.decision.decision.value)
        if resultat.objet_promu_id:
            print("Objet longitudinal cree :", resultat.objet_promu_id)

    dossier = dossier_patient / DOSSIER_LONGITUDINAL
    print("\nResultats consultables dans :", dossier)


def construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(description="Validation clinicien V1 hors ligne")
    sous_commandes = parseur.add_subparsers(dest="commande", required=True)
    revoir = sous_commandes.add_parser("revoir")
    revoir.add_argument("--dossier-patient", type=Path, required=True)
    smoke = sous_commandes.add_parser("smoke")
    smoke.add_argument("--source-patient", type=Path, required=True)
    return parseur


def main() -> None:
    arguments = construire_parseur().parse_args()
    if arguments.commande == "smoke":
        dossier = preparer_smoke(arguments.source_patient)
        print("Copie de travail temporaire :", dossier)
        revoir_dossier(dossier)
    else:
        revoir_dossier(arguments.dossier_patient)


if __name__ == "__main__":
    main()
