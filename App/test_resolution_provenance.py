from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from modeles_longitudinaux import (
    ReferenceSourceV1,
    RelationSupport,
    calculer_sha256_json_canonique,
    calculer_sha256_octets,
    creer_reference_source_v1,
)
from resolution_provenance import (
    CategorieSourceIntrouvable,
    CheminSourceInterdit,
    DocumentCliniqueInvalide,
    EmpreinteDocumentIncorrecte,
    EmpreinteElementIncorrecte,
    IndexSourceHorsLimites,
    PatientIncoherent,
    PointeurSourceInvalide,
    SchemaCliniqueIncompatible,
    SourceAbsente,
    resoudre_reference_source_v1,
)


class TestResolutionProvenance(unittest.TestCase):
    def setUp(self) -> None:
        self.temporaire = TemporaryDirectory()
        self.racine_temporaire = Path(self.temporaire.name)
        self.dossier_id = "P-FICTIF"
        self.dossier_patient = self.racine_temporaire / self.dossier_id
        self.dossier_clinique = self.dossier_patient / "donnees_cliniques"
        self.dossier_clinique.mkdir(parents=True)
        self.chemin_document = self.dossier_clinique / "seance-fictive.json"
        self.document = self._document_fictif()
        self._ecrire_document(self.document)

    def tearDown(self) -> None:
        self.temporaire.cleanup()

    @staticmethod
    def _document_fictif() -> dict:
        return {
            "schema_version": "2.0",
            "date_seance": "2026-08-01",
            "faits_rapportes": [
                "Un fait clinique entierement fictif."
            ],
            "emotions": [
                {
                    "contenu": "Emotion fictive",
                    "contexte": "Contexte fictif",
                    "intensite": "4/10",
                },
                {
                    "contenu": "Deuxieme emotion fictive",
                    "contexte": None,
                    "intensite": None,
                },
            ],
            "cognitions": [
                {
                    "contenu": "Cognition fictive",
                    "contexte": "Situation fictive",
                    "referent_contextuel": None,
                    "referent_explicitement_identifie": None,
                }
            ],
            "comportements": [
                {
                    "contenu": "Comportement fictif",
                    "contexte": "Situation fictive",
                }
            ],
            "evitements": [
                {
                    "contenu": "Evitement fictif",
                    "contexte": None,
                }
            ],
            "interventions": ["Intervention fictive documentee."],
            "taches_interseances": ["Tache fictive proposee."],
            "elements_incertains": ["Element fictif incertain."],
        }

    def _ecrire_document(self, document: dict) -> None:
        self.chemin_document.write_text(
            json.dumps(
                document,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _reference(
        self,
        categorie: str,
        index: int,
    ) -> ReferenceSourceV1:
        element = self.document[categorie][index]
        return creer_reference_source_v1(
            dossier_id_pseudonymise=self.dossier_id,
            document="donnees_cliniques/seance-fictive.json",
            document_sha256=calculer_sha256_octets(
                self.chemin_document.read_bytes()
            ),
            date_seance=date(2026, 8, 1),
            categorie_source=categorie,
            json_pointer=f"/{categorie}/{index}",
            element_sha256=calculer_sha256_json_canonique(element),
            relation_support=RelationSupport.DIRECT,
            extraction_schema_version="2.0",
        )

    def _resoudre(self, reference: ReferenceSourceV1):
        return resoudre_reference_source_v1(
            reference,
            self.dossier_patient,
            self.dossier_id,
        )

    def test_resolution_fait_rapporte(self) -> None:
        reference = self._reference("faits_rapportes", 0)

        resultat = self._resoudre(reference)

        self.assertEqual(
            resultat.element,
            "Un fait clinique entierement fictif.",
        )
        self.assertEqual(resultat.date_seance_document, date(2026, 8, 1))

    def test_resolution_emotion_contextualisee(self) -> None:
        resultat = self._resoudre(self._reference("emotions", 0))

        self.assertEqual(resultat.element, self.document["emotions"][0])

    def test_resolution_cognition_contextualisee(self) -> None:
        resultat = self._resoudre(self._reference("cognitions", 0))

        self.assertEqual(resultat.element, self.document["cognitions"][0])

    def test_resolution_comportement_et_evitement(self) -> None:
        for categorie in ("comportements", "evitements"):
            with self.subTest(categorie=categorie):
                resultat = self._resoudre(self._reference(categorie, 0))
                self.assertEqual(resultat.element, self.document[categorie][0])

    def test_resolution_categories_textuelles_compatibles(self) -> None:
        categories = (
            "interventions",
            "taches_interseances",
            "elements_incertains",
        )
        for categorie in categories:
            with self.subTest(categorie=categorie):
                resultat = self._resoudre(self._reference(categorie, 0))
                self.assertEqual(resultat.element, self.document[categorie][0])

    def test_empreinte_document_verifiee(self) -> None:
        reference = self._reference("faits_rapportes", 0)

        resultat = self._resoudre(reference)

        self.assertEqual(resultat.document_sha256, reference.document_sha256)

    def test_empreinte_element_verifiee(self) -> None:
        reference = self._reference("emotions", 0)

        resultat = self._resoudre(reference)

        self.assertEqual(resultat.element_sha256, reference.element_sha256)

    def test_fichier_source_absent(self) -> None:
        reference = self._reference("faits_rapportes", 0).model_copy(
            update={"document": "donnees_cliniques/absent.json"}
        )

        with self.assertRaises(SourceAbsente) as capture:
            self._resoudre(reference)
        self.assertEqual(capture.exception.code, "source_absente")

    def test_pointeur_invalide(self) -> None:
        reference = self._reference("faits_rapportes", 0).model_copy(
            update={"json_pointer": "faits_rapportes/0"}
        )

        with self.assertRaises(PointeurSourceInvalide):
            self._resoudre(reference)

    def test_categorie_inexistante(self) -> None:
        reference = self._reference("faits_rapportes", 0).model_copy(
            update={
                "categorie_source": "categorie_absente",
                "json_pointer": "/categorie_absente/0",
            }
        )

        with self.assertRaises(CategorieSourceIntrouvable):
            self._resoudre(reference)

    def test_index_hors_limites(self) -> None:
        reference = self._reference("faits_rapportes", 0).model_copy(
            update={"json_pointer": "/faits_rapportes/9"}
        )

        with self.assertRaises(IndexSourceHorsLimites):
            self._resoudre(reference)

    def test_element_supprime(self) -> None:
        reference = self._reference("faits_rapportes", 0)
        self.document["faits_rapportes"] = []
        self._ecrire_document(self.document)
        reference = reference.model_copy(
            update={
                "document_sha256": calculer_sha256_octets(
                    self.chemin_document.read_bytes()
                )
            }
        )

        with self.assertRaises(IndexSourceHorsLimites):
            self._resoudre(reference)

    def test_element_deplace_n_est_pas_recherche_ailleurs(self) -> None:
        reference = self._reference("emotions", 0)
        self.document["emotions"].reverse()
        self._ecrire_document(self.document)
        reference = reference.model_copy(
            update={
                "document_sha256": calculer_sha256_octets(
                    self.chemin_document.read_bytes()
                )
            }
        )

        with self.assertRaises(EmpreinteElementIncorrecte):
            self._resoudre(reference)

    def test_empreinte_element_obsolete_apres_modification(self) -> None:
        reference = self._reference("faits_rapportes", 0)
        self.document["faits_rapportes"][0] = "Fait fictif modifie."
        self._ecrire_document(self.document)
        reference = reference.model_copy(
            update={
                "document_sha256": calculer_sha256_octets(
                    self.chemin_document.read_bytes()
                )
            }
        )

        with self.assertRaises(EmpreinteElementIncorrecte):
            self._resoudre(reference)

    def test_empreinte_document_obsolete(self) -> None:
        reference = self._reference("faits_rapportes", 0)
        self.document["faits_rapportes"][0] = "Fait fictif modifie."
        self._ecrire_document(self.document)

        with self.assertRaises(EmpreinteDocumentIncorrecte):
            self._resoudre(reference)

    def test_mauvais_patient_dans_reference(self) -> None:
        reference = self._reference("faits_rapportes", 0).model_copy(
            update={"dossier_id_pseudonymise": "AUTRE-PATIENT-FICTIF"}
        )

        with self.assertRaises(PatientIncoherent):
            self._resoudre(reference)

    def test_dossier_physique_d_un_autre_patient(self) -> None:
        reference = self._reference("faits_rapportes", 0)
        autre_dossier = self.racine_temporaire / "AUTRE-PATIENT-FICTIF"
        autre_dossier.mkdir()

        with self.assertRaises(PatientIncoherent):
            resoudre_reference_source_v1(
                reference,
                autre_dossier,
                self.dossier_id,
            )

    def test_tentative_parent_interdite(self) -> None:
        reference = self._reference("faits_rapportes", 0).model_copy(
            update={"document": "../hors-patient.json"}
        )

        with self.assertRaises(CheminSourceInterdit):
            self._resoudre(reference)

    def test_tentative_chemin_absolu_interdite(self) -> None:
        chemin_absolu = self.chemin_document.resolve().as_posix()
        reference = self._reference("faits_rapportes", 0).model_copy(
            update={"document": chemin_absolu}
        )

        with self.assertRaises(CheminSourceInterdit):
            self._resoudre(reference)

    def test_sortie_du_dossier_clinique_apres_normalisation(self) -> None:
        reference = self._reference("faits_rapportes", 0).model_copy(
            update={"document": "donnees_cliniques/../profil.json"}
        )

        with self.assertRaises(CheminSourceInterdit):
            self._resoudre(reference)

    def test_combinaison_de_separateurs_interdite(self) -> None:
        reference = self._reference("faits_rapportes", 0).model_copy(
            update={"document": "donnees_cliniques\\..\\profil.json"}
        )

        with self.assertRaises(CheminSourceInterdit):
            self._resoudre(reference)

    def test_reference_serialisee_resout_le_meme_element(self) -> None:
        reference = self._reference("cognitions", 0)
        rechargee = ReferenceSourceV1.model_validate_json(
            reference.model_dump_json()
        )

        original = self._resoudre(reference)
        recharge = self._resoudre(rechargee)

        self.assertEqual(recharge, original)

    def test_empreinte_json_canonique_stable(self) -> None:
        premier = {"b": 2, "a": "Valeur fictive accentuee"}
        second = {"a": "Valeur fictive accentuee", "b": 2}

        self.assertEqual(
            calculer_sha256_json_canonique(premier),
            calculer_sha256_json_canonique(second),
        )

    def test_empreinte_document_porte_sur_les_octets_exacts(self) -> None:
        contenu_compact = b'{"valeur":"fictive"}'
        contenu_indente = b'{\n  "valeur": "fictive"\n}'

        self.assertNotEqual(
            calculer_sha256_octets(contenu_compact),
            calculer_sha256_octets(contenu_indente),
        )

    def test_schema_incompatible(self) -> None:
        reference = self._reference("faits_rapportes", 0)
        self.document["schema_version"] = "1.0"
        self._ecrire_document(self.document)

        with self.assertRaises(SchemaCliniqueIncompatible):
            self._resoudre(reference)

    def test_document_clinique_invalide(self) -> None:
        reference = self._reference("faits_rapportes", 0)
        self.chemin_document.write_text("{JSON invalide", encoding="utf-8")

        with self.assertRaises(DocumentCliniqueInvalide):
            self._resoudre(reference)


if __name__ == "__main__":
    unittest.main()
