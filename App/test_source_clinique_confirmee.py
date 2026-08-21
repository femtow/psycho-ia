from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import unittest

from source_clinique_confirmee import (
    DossierSourceCliniqueV1,
    PersistanceSourceEchouee,
    ServiceSourceCliniqueConfirmeeV1,
    SourceCliniqueInvalide,
    StatutSourceCliniqueV1,
    calculer_sha256_octets,
    charger_provenance_json,
    enregistrer_provenance_json_depuis_source_confirmee,
    enregistrer_provenance_json_produite,
)


class TestSourceCliniqueConfirmee(unittest.TestCase):
    def setUp(self) -> None:
        self.temporaire = TemporaryDirectory()
        self.dossier_patient = Path(self.temporaire.name) / "P-FICTIF-SOURCE"
        self.dossier_transcriptions = self.dossier_patient / "Transcriptions"
        self.dossier_json = self.dossier_patient / "donnees_cliniques"
        self.dossier_transcriptions.mkdir(parents=True)
        self.dossier_json.mkdir()
        self.date_seance = date(2026, 8, 22)
        self.transcription = (
            self.dossier_transcriptions / "2026-08-22-PA.txt"
        )
        self.texte_machine = (
            "Patient fictif - Seance 22-08-2026\n"
            "Tache fictive documentee.\n"
        )
        self.transcription.write_text(self.texte_machine, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporaire.cleanup()

    def creer_service(self, **options) -> ServiceSourceCliniqueConfirmeeV1:
        return ServiceSourceCliniqueConfirmeeV1(
            self.dossier_patient,
            self.transcription,
            self.date_seance,
            self.dossier_patient.name,
            **options,
        )

    def confirmer(self, service=None):
        service = service or self.creer_service()
        return service.confirmer(
            clinicien_id="clinicien-fictif",
            confirmation_explicite=True,
            accepter_incertitudes=True,
            confirmee_le=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        )

    def test_transcription_jamais_confirmee(self) -> None:
        etat = self.creer_service().verifier_autorite()
        self.assertEqual(etat.statut, StatutSourceCliniqueV1.PRODUITE)
        self.assertFalse(etat.est_confirmee)

    def test_confirmation_simple(self) -> None:
        resultat = self.confirmer()
        self.assertEqual(resultat.etat.statut, StatutSourceCliniqueV1.CONFIRMEE)
        self.assertFalse(resultat.deja_confirmee)

    def test_confirmation_liee_a_empreinte_exacte(self) -> None:
        resultat = self.confirmer()
        attendu = calculer_sha256_octets(self.transcription.read_bytes())
        self.assertEqual(resultat.confirmation.transcription_sha256, attendu)

    def test_rechargement_reconnait_confirmation(self) -> None:
        self.confirmer()
        etat = self.creer_service().verifier_autorite()
        self.assertTrue(etat.est_confirmee)
        self.assertEqual(etat.version, 1)

    def test_modification_apres_confirmation_rend_source_obsolete(self) -> None:
        self.confirmer()
        self.transcription.write_text("Version modifiee.\n", encoding="utf-8")
        etat = self.creer_service().verifier_autorite()
        self.assertEqual(etat.statut, StatutSourceCliniqueV1.OBSOLETE)

    def test_correction_humaine_puis_confirmation(self) -> None:
        resultat = self.creer_service().corriger_et_confirmer(
            self.texte_machine.replace("fictive", "fictive corrigee"),
            clinicien_id="clinicien-fictif",
            confirmation_explicite=True,
            accepter_incertitudes=True,
            instant=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            resultat.etat.statut,
            StatutSourceCliniqueV1.CORRIGEE_ET_CONFIRMEE,
        )
        self.assertEqual(resultat.etat.version, 2)

    def test_original_machine_conserve_apres_correction(self) -> None:
        self.creer_service().corriger_et_confirmer(
            self.texte_machine + "Correction.\n",
            clinicien_id="clinicien-fictif",
            confirmation_explicite=True,
            accepter_incertitudes=True,
        )
        self.assertEqual(
            self.transcription.read_text(encoding="utf-8"),
            self.texte_machine,
        )

    def test_avant_apres_conserves(self) -> None:
        service = self.creer_service()
        apres = self.texte_machine.replace("documentee", "corrigee")
        service.corriger(
            apres,
            clinicien_id="clinicien-fictif",
            corrigee_le=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        )
        dossier = DossierSourceCliniqueV1.model_validate_json(
            service.chemin_dossier_source.read_bytes()
        )
        correction = dossier.corrections[0]
        avant = self.dossier_patient / Path(correction.avant_instantane)
        nouveau = self.dossier_patient / Path(correction.apres_instantane)
        self.assertEqual(avant.read_text(encoding="utf-8"), self.texte_machine)
        self.assertEqual(nouveau.read_text(encoding="utf-8"), apres)

    def test_illisible_peut_rester_confirme(self) -> None:
        self.transcription.write_text(
            "Sommeil difficile depuis [illisible].\n",
            encoding="utf-8",
        )
        resultat = self.confirmer()
        self.assertTrue(resultat.etat.est_confirmee)
        self.assertEqual(len(resultat.etat.passages_signales), 1)

    def test_aucune_reconstruction_automatique_illisible(self) -> None:
        texte = "Sommeil difficile depuis [illisible].\n"
        self.transcription.write_text(texte, encoding="utf-8")
        self.confirmer()
        self.assertEqual(self.creer_service().lire_transcription(), texte)

    def test_mot_incertain_conserve(self) -> None:
        texte = "Depuis [mot incertain : plusieurs] jours.\n"
        self.transcription.write_text(texte, encoding="utf-8")
        resultat = self.confirmer()
        self.assertEqual(resultat.confirmation.passages_signales, (texte.strip(),))
        self.assertIn("[mot incertain", self.creer_service().lire_transcription())

    def test_patient_incorrect_rejete(self) -> None:
        with self.assertRaises(SourceCliniqueInvalide):
            ServiceSourceCliniqueConfirmeeV1(
                self.dossier_patient,
                self.transcription,
                self.date_seance,
                "P-AUTRE",
            )

    def test_mauvaise_seance_rejetee(self) -> None:
        with self.assertRaises(SourceCliniqueInvalide):
            ServiceSourceCliniqueConfirmeeV1(
                self.dossier_patient,
                self.transcription,
                date(2026, 8, 23),
                self.dossier_patient.name,
            )

    def test_double_confirmation_idempotente(self) -> None:
        premiere = self.confirmer()
        seconde = self.confirmer()
        self.assertTrue(seconde.deja_confirmee)
        self.assertEqual(premiere.confirmation.id, seconde.confirmation.id)

    def test_simple_chargement_ne_confirme_rien(self) -> None:
        service = self.creer_service()
        service.lire_transcription()
        self.assertFalse(service.chemin_dossier_source.exists())
        self.assertFalse(service.verifier_autorite().est_confirmee)

    def test_module_sans_dependance_openai(self) -> None:
        module = Path(__file__).with_name("source_clinique_confirmee.py")
        contenu = module.read_text(encoding="utf-8").lower()
        self.assertNotIn("import openai", contenu)
        self.assertNotIn("from openai", contenu)

    def test_serialisation_deserialisation(self) -> None:
        self.confirmer()
        chemin = self.creer_service().chemin_dossier_source
        dossier = DossierSourceCliniqueV1.model_validate_json(chemin.read_bytes())
        recharge = DossierSourceCliniqueV1.model_validate_json(
            dossier.model_dump_json()
        )
        self.assertEqual(recharge, dossier)

    def test_correction_persistee_atomiquement(self) -> None:
        self.confirmer()
        service_normal = self.creer_service()
        contenu_initial = service_normal.chemin_dossier_source.read_bytes()
        appels = 0

        def remplacer(source: Path, destination: Path) -> None:
            nonlocal appels
            appels += 1
            if appels == 2:
                raise OSError("echec simule")
            os.replace(source, destination)

        service = self.creer_service(remplacer_fichier=remplacer)
        with self.assertRaises(PersistanceSourceEchouee):
            service.corriger(
                self.texte_machine + "Correction non persistee.\n",
                clinicien_id="clinicien-fictif",
            )
        self.assertEqual(
            service.chemin_dossier_source.read_bytes(),
            contenu_initial,
        )
        correction = (
            service.dossier_session
            / "versions"
            / "v0002_correction_clinicien.txt"
        )
        self.assertFalse(correction.exists())

    def test_correction_non_confirmee_ne_devient_pas_autoritative(self) -> None:
        service = self.creer_service()
        service.corriger(
            self.texte_machine + "Correction en attente.\n",
            clinicien_id="clinicien-fictif",
        )
        etat = service.verifier_autorite()
        self.assertEqual(etat.statut, StatutSourceCliniqueV1.PRODUITE)
        self.assertFalse(etat.est_confirmee)

    def test_provenance_json_liee_apres_confirmation_exacte(self) -> None:
        json_path = self.dossier_json / "2026-08-22-PA.json"
        json_path.write_text(
            json.dumps(
                {"schema_version": "2.0", "date_seance": "2026-08-22"}
            ),
            encoding="utf-8",
        )
        chemin_provenance = enregistrer_provenance_json_produite(
            self.dossier_patient,
            self.dossier_patient.name,
            self.date_seance,
            self.transcription,
            json_path,
        )
        resultat = self.confirmer()
        provenance = charger_provenance_json(chemin_provenance)
        self.assertEqual(provenance.confirmation_id, resultat.confirmation.id)
        self.assertTrue(resultat.etat.json_clinique_lie)

    def test_json_ne_pretend_pas_valider_ses_assertions(self) -> None:
        json_path = self.dossier_json / "2026-08-22-PA.json"
        json_path.write_text(
            '{"schema_version":"2.0","date_seance":"2026-08-22"}',
            encoding="utf-8",
        )
        chemin = enregistrer_provenance_json_produite(
            self.dossier_patient,
            self.dossier_patient.name,
            self.date_seance,
            self.transcription,
            json_path,
        )
        provenance = charger_provenance_json(chemin)
        self.assertFalse(provenance.assertions_json_validees_individuellement)
        self.assertIsNone(provenance.confirmation_id)

    def test_json_regenere_lie_exactement_a_correction_confirmee(self) -> None:
        service = self.creer_service()
        resultat = service.corriger_et_confirmer(
            self.texte_machine + "Correction clinique.\n",
            clinicien_id="clinicien-fictif",
            confirmation_explicite=True,
            accepter_incertitudes=True,
            instant=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        )
        json_path = self.dossier_json / "2026-08-22-PA.json"
        json_path.write_text(
            '{"schema_version":"2.0","date_seance":"2026-08-22"}',
            encoding="utf-8",
        )
        chemin_version = self.dossier_patient / Path(
            service._charger_dossier().versions[-1].document_courant
        )
        chemin = enregistrer_provenance_json_depuis_source_confirmee(
            service,
            json_path,
            calculer_sha256_octets(chemin_version.read_bytes()),
        )
        provenance = charger_provenance_json(chemin)
        self.assertEqual(provenance.confirmation_id, resultat.confirmation.id)
        self.assertEqual(
            provenance.transcription_sha256,
            resultat.confirmation.transcription_sha256,
        )
        self.assertTrue(service.verifier_autorite().json_clinique_lie)
        self.assertFalse(provenance.assertions_json_validees_individuellement)

    def test_liaison_refuse_une_empreinte_non_utilisee(self) -> None:
        service = self.creer_service()
        service.corriger_et_confirmer(
            self.texte_machine + "Correction clinique.\n",
            clinicien_id="clinicien-fictif",
            confirmation_explicite=True,
            accepter_incertitudes=True,
        )
        json_path = self.dossier_json / "2026-08-22-PA.json"
        json_path.write_text(
            '{"schema_version":"2.0","date_seance":"2026-08-22"}',
            encoding="utf-8",
        )
        with self.assertRaises(SourceCliniqueInvalide):
            enregistrer_provenance_json_depuis_source_confirmee(
                service,
                json_path,
                "0" * 64,
            )


if __name__ == "__main__":
    unittest.main()
