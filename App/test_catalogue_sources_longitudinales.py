from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from pydantic import ValidationError

from catalogue_sources_longitudinales import (
    AucunDocumentCliniqueValide,
    CatalogueSourcesPatientV1,
    DocumentCatalogueInvalide,
    DossierPatientCatalogueInvalide,
    ReferenceCatalogueInvalide,
    SourceCatalogueInconnue,
    construire_catalogue_sources_patient,
    verifier_catalogue_resoluble,
)
from resolution_provenance import resoudre_reference_source_v1


class TestCatalogueSourcesLongitudinales(unittest.TestCase):
    def setUp(self) -> None:
        self.temporaire = TemporaryDirectory()
        self.racine = Path(self.temporaire.name)
        self.dossier_id = "P-FICTIF-CATALOGUE"
        self.dossier_patient = self.racine / self.dossier_id
        self.dossier_clinique = self.dossier_patient / "donnees_cliniques"
        self.dossier_clinique.mkdir(parents=True)
        self._ecrire(
            "z-seance.json",
            self._document(
                "2026-08-08",
                faits=["Fait fictif plus recent."],
            ),
        )
        self._ecrire(
            "a-seance.json",
            self._document(
                "2026-08-01",
                faits=["Fait fictif initial."],
                emotions=[
                    {
                        "contenu": "Emotion fictive",
                        "contexte": "Contexte fictif",
                        "intensite": "4/10",
                    }
                ],
                taches=["Tache fictive proposee."],
                incertains=["Element fictif [illisible]."],
            ),
        )

    def tearDown(self) -> None:
        self.temporaire.cleanup()

    @staticmethod
    def _document(
        date_seance: str,
        *,
        faits: list[str] | None = None,
        emotions: list[dict] | None = None,
        taches: list[str] | None = None,
        incertains: list[str] | None = None,
    ) -> dict:
        return {
            "schema_version": "2.0",
            "date_seance": date_seance,
            "faits_rapportes": faits or [],
            "emotions": emotions or [],
            "cognitions": [],
            "comportements": [],
            "evitements": [],
            "interventions": [],
            "taches_interseances": taches or [],
            "elements_incertains": incertains or [],
        }

    def _ecrire(self, nom: str, document: dict) -> Path:
        chemin = self.dossier_clinique / nom
        chemin.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return chemin

    def _catalogue(self) -> CatalogueSourcesPatientV1:
        return construire_catalogue_sources_patient(
            self.dossier_patient,
            self.dossier_id,
        )

    def test_ordre_deterministe_date_document_categorie_index(self) -> None:
        catalogue = self._catalogue()

        self.assertEqual(
            [entree.source_id for entree in catalogue.entrees],
            [
                "source_0001",
                "source_0002",
                "source_0003",
                "source_0004",
                "source_0005",
            ],
        )
        self.assertEqual(catalogue.entrees[0].contenu, "Fait fictif initial.")
        self.assertEqual(catalogue.entrees[-1].contenu, "Fait fictif plus recent.")
        self.assertEqual(catalogue.date_coupure.isoformat(), "2026-08-08")

    def test_deux_constructions_identiques(self) -> None:
        premier = self._catalogue()
        second = self._catalogue()

        self.assertEqual(premier, second)
        self.assertEqual(
            premier.empreinte_sources_sha256,
            second.empreinte_sources_sha256,
        )

    def test_toutes_les_references_se_resolvent(self) -> None:
        catalogue = self._catalogue()

        for entree in catalogue.entrees:
            resolue = resoudre_reference_source_v1(
                entree.reference,
                self.dossier_patient,
                self.dossier_id,
            )
            self.assertEqual(resolue.element, entree.contenu)
            self.assertEqual(resolue.reference_id, entree.reference.id)

    def test_vue_terra_exclut_toute_reference_technique(self) -> None:
        vue = self._catalogue().vue_terra()
        texte = json.dumps(vue, ensure_ascii=False)

        for interdit in (
            "document_sha256",
            "element_sha256",
            "json_pointer",
            "ReferenceSourceV1",
            "donnees_cliniques/",
            "src_",
        ):
            self.assertNotIn(interdit, texte)
        self.assertIn("source_0001", texte)
        self.assertIn("Contexte fictif", texte)
        self.assertIn("4/10", texte)

    def test_reconversion_source_id_vers_reference(self) -> None:
        entree = self._catalogue().entree_pour("source_0003")

        self.assertEqual(entree.categorie, "taches_interseances")
        self.assertTrue(entree.reference.id.startswith("src_"))

    def test_source_id_inconnu_refuse(self) -> None:
        with self.assertRaises(SourceCatalogueInconnue):
            self._catalogue().entree_pour("source_9999")

    def test_reference_obsolete_refusee(self) -> None:
        catalogue = self._catalogue()
        chemin = self.dossier_clinique / "a-seance.json"
        document = json.loads(chemin.read_text(encoding="utf-8"))
        document["faits_rapportes"][0] = "Fait fictif modifie."
        self._ecrire("a-seance.json", document)

        with self.assertRaises(ReferenceCatalogueInvalide):
            verifier_catalogue_resoluble(catalogue, self.dossier_patient)

    def test_document_v2_invalide_interrompt_tout_le_catalogue(self) -> None:
        document = self._document("2026-08-15")
        document["champ_inconnu"] = []
        self._ecrire("invalide.json", document)

        with self.assertRaises(DocumentCatalogueInvalide):
            self._catalogue()

    def test_json_non_standard_refuse(self) -> None:
        (self.dossier_clinique / "invalide.json").write_text(
            '{"schema_version":"2.0","date_seance":NaN}',
            encoding="utf-8",
        )

        with self.assertRaises(DocumentCatalogueInvalide):
            self._catalogue()

    def test_dossier_patient_incoherent_refuse(self) -> None:
        with self.assertRaises(DossierPatientCatalogueInvalide):
            construire_catalogue_sources_patient(
                self.dossier_patient,
                "P-AUTRE",
            )

    def test_absence_de_document_refusee(self) -> None:
        for chemin in self.dossier_clinique.glob("*.json"):
            chemin.unlink()

        with self.assertRaises(AucunDocumentCliniqueValide):
            self._catalogue()

    def test_serialisation_deserialisation_du_catalogue(self) -> None:
        catalogue = self._catalogue()
        recharge = CatalogueSourcesPatientV1.model_validate_json(
            catalogue.model_dump_json()
        )

        self.assertEqual(recharge, catalogue)

    def test_modele_refuse_une_entree_d_un_autre_patient(self) -> None:
        catalogue = self._catalogue()
        entree = catalogue.entrees[0]
        reference = entree.reference.model_copy(
            update={"dossier_id_pseudonymise": "P-AUTRE"}
        )
        entree_invalide = entree.model_copy(update={"reference": reference})

        with self.assertRaises(ValidationError):
            CatalogueSourcesPatientV1(
                dossier_id_pseudonymise=self.dossier_id,
                date_coupure=catalogue.date_coupure,
                entrees=(entree_invalide,),
                empreinte_sources_sha256=catalogue.empreinte_sources_sha256,
            )


if __name__ == "__main__":
    unittest.main()
