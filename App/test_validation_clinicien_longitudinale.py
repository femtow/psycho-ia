from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import unittest

from catalogue_sources_longitudinales import construire_catalogue_sources_patient
from generation_propositions_longitudinales import (
    RevueTacheTerra,
    SortieTerraPropositionsV1,
    construire_fichier_propositions,
    construire_plan_revue_taches,
    integrer_revues_taches,
)
from modeles_longitudinaux import (
    FichierPropositionsLongitudinalesV1,
    RegistreLongitudinalV1,
    RejetPropositionLongitudinale,
    StatutEpistemique,
    enregistrer_propositions,
    enregistrer_registre,
)
from validation_clinicien_longitudinale import (
    ConfirmationClinicienManquante,
    DecisionTerminaleExistante,
    ModificationHorsPerimetre,
    PersistanceValidationEchouee,
    PropositionIntrouvable,
    PropositionObsolete,
    ServiceValidationClinicienV1,
    TypeDecisionClinicienV1,
    charger_decisions,
)


class TestValidationClinicienLongitudinale(unittest.TestCase):
    def setUp(self) -> None:
        self.temporaire = TemporaryDirectory()
        self.dossier_patient = Path(self.temporaire.name) / "P-FICTIF-VALIDATION"
        self.dossier_clinique = self.dossier_patient / "donnees_cliniques"
        self.dossier_longitudinal = self.dossier_patient / "longitudinal"
        self.dossier_clinique.mkdir(parents=True)
        self._ecrire_seance(
            "2026-08-08",
            faits_rapportes=["Difficulte fictive documentee."],
            taches_interseances=["Realiser une tache fictive cette semaine."],
        )
        self._ecrire_seance(
            "2026-08-15",
            comportements=[
                {
                    "contenu": "A realise la tache fictive.",
                    "contexte": "Cette semaine.",
                }
            ],
            taches_interseances=["Realiser une seconde tache fictive."],
        )
        catalogue = construire_catalogue_sources_patient(
            self.dossier_patient,
            self.dossier_patient.name,
        )
        plan = construire_plan_revue_taches(catalogue)
        revues = tuple(
            RevueTacheTerra(
                task_id=str(tache["task_id"]),
                source_consigne_id=str(tache["source_consigne_id"]),
                statut_resultat_propose="resultat_non_documente",
                justification="Revue fictive sans resultat retenu.",
            )
            for tache in plan
        )
        sortie = integrer_revues_taches(
            SortieTerraPropositionsV1(revues_taches=revues),
            catalogue,
            plan,
        )
        self.fichier_propositions = construire_fichier_propositions(
            sortie,
            catalogue,
            self.dossier_patient,
            cree_le=datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc),
        )
        self.registre = RegistreLongitudinalV1(
            dossier_id_pseudonymise=self.dossier_patient.name,
            version_registre=1,
            date_coupure=catalogue.date_coupure,
            statut_documentaire="valide_clinicien",
            references_sources=tuple(
                entree.reference for entree in catalogue.entrees
            ),
        )
        self.chemin_propositions = self.dossier_longitudinal / "propositions.json"
        self.chemin_registre = self.dossier_longitudinal / "registre.json"
        self.chemin_decisions = self.dossier_longitudinal / "decisions.json"
        enregistrer_propositions(self.fichier_propositions, self.chemin_propositions)
        enregistrer_registre(self.registre, self.chemin_registre)
        self.octets_proposition_originaux = self.chemin_propositions.read_bytes()
        self.service = self._creer_service()
        self.vue = self.service.lister_propositions()[0]
        self.instant = datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temporaire.cleanup()

    def _ecrire_seance(self, date_seance: str, **categories) -> None:
        document = {
            "schema_version": "2.0",
            "date_seance": date_seance,
            "faits_rapportes": [],
            "emotions": [],
            "cognitions": [],
            "comportements": [],
            "evitements": [],
            "interventions": [],
            "taches_interseances": [],
            "elements_incertains": [],
        }
        document.update(categories)
        (self.dossier_clinique / f"{date_seance}.json").write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _creer_service(self, remplacer=os.replace):
        return ServiceValidationClinicienV1(
            self.dossier_patient,
            self.chemin_propositions,
            self.chemin_registre,
            self.chemin_decisions,
            remplacer_fichier=remplacer,
        )

    def _arguments_communs(self):
        return {
            "validateur_id": "CLINICIEN-FICTIF",
            "empreinte_fichier_affichee": (
                self.vue.empreinte_fichier_propositions_sha256
            ),
            "version_registre_affichee": self.vue.version_registre,
            "confirmation_explicite": True,
            "decide_le": self.instant,
        }

    def _accepter(self):
        return self.service.accepter(
            self.vue.proposition_id,
            **self._arguments_communs(),
        )

    def _modifier(self, **remplacements):
        arguments = {
            **self._arguments_communs(),
            "nouvelle_formulation": "Realiser une tache fictive pendant la semaine.",
            "statut_epistemique_final": StatutEpistemique.EXPLICITE,
            "confirmation_sources": True,
            "confirmation_statut_epistemique": True,
        }
        arguments.update(remplacements)
        return self.service.modifier_puis_accepter(
            self.vue.proposition_id,
            **arguments,
        )

    def test_accepter_une_proposition_valide(self) -> None:
        resultat = self._accepter()
        self.assertEqual(resultat.decision.decision, TypeDecisionClinicienV1.ACCEPTER)

    def test_acceptation_cree_objet_dans_registre(self) -> None:
        resultat = self._accepter()
        self.assertEqual(len(resultat.registre.taches_intersession), 1)
        self.assertEqual(resultat.registre.version_registre, 2)

    def test_proposition_originale_inchangee_apres_acceptation(self) -> None:
        self._accepter()
        self.assertEqual(self.chemin_propositions.read_bytes(), self.octets_proposition_originaux)

    def test_decision_acceptation_est_tracable(self) -> None:
        resultat = self._accepter()
        recharge = charger_decisions(self.chemin_decisions).decisions[0]
        self.assertEqual(recharge, resultat.decision)
        self.assertEqual(recharge.validateur_id, "CLINICIEN-FICTIF")

    def test_refuser_une_proposition(self) -> None:
        resultat = self.service.refuser(
            self.vue.proposition_id,
            commentaire="Proposition non retenue.",
            **self._arguments_communs(),
        )
        self.assertEqual(resultat.decision.decision, TypeDecisionClinicienV1.REFUSER)

    def test_refus_ne_modifie_pas_registre(self) -> None:
        avant = self.chemin_registre.read_bytes()
        self.service.refuser(self.vue.proposition_id, **self._arguments_communs())
        self.assertEqual(self.chemin_registre.read_bytes(), avant)

    def test_refus_n_est_pas_donnee_clinique_negative(self) -> None:
        resultat = self.service.refuser(self.vue.proposition_id, **self._arguments_communs())
        self.assertIsNone(resultat.decision.contenu_final)
        self.assertIsNone(resultat.decision.objet_promu_id)
        self.assertEqual(resultat.registre.tous_les_objets(), ())

    def test_differer_une_proposition(self) -> None:
        resultat = self.service.differer(self.vue.proposition_id, **self._arguments_communs())
        self.assertEqual(resultat.decision.decision, TypeDecisionClinicienV1.DIFFERER)
        self.assertFalse(resultat.decision.terminale)

    def test_differer_ne_modifie_pas_registre_ni_etat_clinique(self) -> None:
        avant = self.chemin_registre.read_bytes()
        resultat = self.service.differer(self.vue.proposition_id, **self._arguments_communs())
        self.assertEqual(self.chemin_registre.read_bytes(), avant)
        self.assertEqual(resultat.registre.tous_les_objets(), ())

    def test_proposition_differee_peut_etre_revue_puis_acceptee(self) -> None:
        self.service.differer(self.vue.proposition_id, **self._arguments_communs())
        vue_actualisee = self.service.lister_propositions()[0]
        resultat = self.service.accepter(
            vue_actualisee.proposition_id,
            validateur_id="CLINICIEN-FICTIF",
            empreinte_fichier_affichee=vue_actualisee.empreinte_fichier_propositions_sha256,
            version_registre_affichee=vue_actualisee.version_registre,
            confirmation_explicite=True,
            decide_le=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(resultat.decision.decision, TypeDecisionClinicienV1.ACCEPTER)

    def test_modifier_puis_accepter(self) -> None:
        resultat = self._modifier()
        self.assertEqual(
            resultat.registre.taches_intersession[0].consigne.contenu,
            "Realiser une tache fictive pendant la semaine.",
        )

    def test_modification_conserve_avant_apres(self) -> None:
        decision = self._modifier().decision
        self.assertEqual(decision.differences_clinicien[0].avant, self.vue.contenu_principal)
        self.assertEqual(
            decision.differences_clinicien[0].apres,
            "Realiser une tache fictive pendant la semaine.",
        )

    def test_proposition_originale_inchangee_apres_modification(self) -> None:
        resultat = self._modifier()
        self.assertEqual(resultat.proposition_originale.contenu_propose, self.fichier_propositions.propositions[0].contenu_propose)
        self.assertEqual(self.chemin_propositions.read_bytes(), self.octets_proposition_originaux)

    def test_modification_exige_confirmations_explicites(self) -> None:
        for champ in (
            "confirmation_sources",
            "confirmation_statut_epistemique",
            "confirmation_explicite",
        ):
            with self.subTest(champ=champ), self.assertRaises(ConfirmationClinicienManquante):
                self._modifier(**{champ: False})

    def test_modification_hors_perimetre_structurel_est_bloquee(self) -> None:
        with self.assertRaises(ModificationHorsPerimetre):
            self._modifier(statut_epistemique_final=StatutEpistemique.SYNTHESE_PRUDENTE)

    def test_acceptation_simple_conserve_statut_epistemique(self) -> None:
        resultat = self._accepter()
        self.assertEqual(
            resultat.registre.taches_intersession[0].consigne.statut_epistemique,
            StatutEpistemique.EXPLICITE,
        )

    def test_changement_statut_exige_action_explicite(self) -> None:
        with self.assertRaises(ConfirmationClinicienManquante):
            self._modifier(confirmation_statut_epistemique=False)

    def test_source_obsolete_avant_acceptation_bloque_promotion(self) -> None:
        chemin = self.dossier_clinique / "2026-08-08.json"
        document = json.loads(chemin.read_text(encoding="utf-8"))
        document["taches_interseances"][0] = "Tache source modifiee."
        chemin.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(PropositionObsolete):
            self._accepter()
        self.assertEqual(RegistreLongitudinalV1.model_validate_json(self.chemin_registre.read_bytes()).tous_les_objets(), ())

    def test_source_obsolete_avant_modification_bloque_promotion(self) -> None:
        chemin = self.dossier_clinique / "2026-08-08.json"
        chemin.write_text("{}", encoding="utf-8")
        with self.assertRaises(PropositionObsolete):
            self._modifier()

    def test_rejet_technique_est_non_promotable(self) -> None:
        rejet = RejetPropositionLongitudinale(
            position_sortie=1,
            type_objet="tache_intersession",
            operation="creation",
            contenu_principal="Rejet technique fictif.",
            source_ids_courts=("source_0001",),
            code="rejet_fictif",
            motif="Proposition volontairement rejetee.",
        )
        fichier = FichierPropositionsLongitudinalesV1.model_validate(
            {**self.fichier_propositions.model_dump(), "rejets": (rejet,)}
        )
        enregistrer_propositions(fichier, self.chemin_propositions)
        service = self._creer_service()
        vue = service.lister_propositions()[0]
        self.assertEqual(len(service.lister_rejets_techniques()), 1)
        with self.assertRaises(PropositionIntrouvable):
            service.accepter(
                "prop_" + "f" * 32,
                validateur_id="CLINICIEN-FICTIF",
                empreinte_fichier_affichee=vue.empreinte_fichier_propositions_sha256,
                version_registre_affichee=vue.version_registre,
                confirmation_explicite=True,
            )

    def test_double_acceptation_est_impossible(self) -> None:
        self._accepter()
        vue = self.service.lister_propositions()[0]
        with self.assertRaises(DecisionTerminaleExistante):
            self.service.accepter(
                vue.proposition_id,
                validateur_id="CLINICIEN-FICTIF",
                empreinte_fichier_affichee=vue.empreinte_fichier_propositions_sha256,
                version_registre_affichee=vue.version_registre,
                confirmation_explicite=True,
            )

    def test_relance_service_ne_cree_pas_doublon(self) -> None:
        self._accepter()
        service = self._creer_service()
        vue = service.lister_propositions()[0]
        with self.assertRaises(DecisionTerminaleExistante):
            service.accepter(
                vue.proposition_id,
                validateur_id="CLINICIEN-FICTIF",
                empreinte_fichier_affichee=vue.empreinte_fichier_propositions_sha256,
                version_registre_affichee=vue.version_registre,
                confirmation_explicite=True,
            )
        registre = RegistreLongitudinalV1.model_validate_json(self.chemin_registre.read_bytes())
        self.assertEqual(len(registre.taches_intersession), 1)

    def test_proposition_refusee_n_est_plus_promotable(self) -> None:
        self.service.refuser(self.vue.proposition_id, **self._arguments_communs())
        vue = self.service.lister_propositions()[0]
        with self.assertRaises(DecisionTerminaleExistante):
            self.service.accepter(
                vue.proposition_id,
                validateur_id="CLINICIEN-FICTIF",
                empreinte_fichier_affichee=vue.empreinte_fichier_propositions_sha256,
                version_registre_affichee=vue.version_registre,
                confirmation_explicite=True,
            )

    def test_provenance_est_conservee_dans_objet_valide(self) -> None:
        resultat = self._accepter()
        objet = resultat.registre.taches_intersession[0]
        self.assertEqual(objet.consigne.source_ids, self.fichier_propositions.propositions[0].source_ids)
        self.assertTrue(all(source in {r.id for r in resultat.registre.references_sources} for source in objet.consigne.source_ids))

    def test_serialisation_deserialisation_decisions(self) -> None:
        decision = self.service.differer(self.vue.proposition_id, **self._arguments_communs()).decision
        self.assertEqual(charger_decisions(self.chemin_decisions).decisions, (decision,))

    def test_erreur_persistance_annule_ecritures_partielles(self) -> None:
        compteur = 0

        def echouer_second_remplacement(source, destination):
            nonlocal compteur
            compteur += 1
            if compteur == 2:
                raise OSError("Echec fictif du second remplacement.")
            os.replace(source, destination)

        service = self._creer_service(echouer_second_remplacement)
        avant_registre = self.chemin_registre.read_bytes()
        with self.assertRaises(PersistanceValidationEchouee):
            service.accepter(
                self.vue.proposition_id,
                **self._arguments_communs(),
            )
        self.assertEqual(self.chemin_registre.read_bytes(), avant_registre)
        self.assertFalse(self.chemin_decisions.exists())

    def test_service_est_independant_cli_et_openai(self) -> None:
        module = Path(__file__).with_name("validation_clinicien_longitudinale.py")
        texte = module.read_text(encoding="utf-8").lower()
        self.assertNotIn("validation_clinicien_cli", texte)
        self.assertNotIn("from openai", texte)
        self.assertNotIn("import openai", texte)

    def test_empreinte_affichee_obsolete_bloque_decision(self) -> None:
        with self.assertRaises(PropositionObsolete):
            self.service.accepter(
                self.vue.proposition_id,
                **{
                    **self._arguments_communs(),
                    "empreinte_fichier_affichee": "0" * 64,
                },
            )

    def test_version_registre_affichee_obsolete_bloque_decision(self) -> None:
        with self.assertRaises(PropositionObsolete):
            self.service.accepter(
                self.vue.proposition_id,
                **{
                    **self._arguments_communs(),
                    "version_registre_affichee": 99,
                },
            )


if __name__ == "__main__":
    unittest.main()
