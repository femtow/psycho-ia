from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from catalogue_sources_longitudinales import construire_catalogue_sources_patient
from generation_propositions_longitudinales import (
    ReponseTerraInvalide,
    RevueTacheTerra,
    SortieTerraPropositionsV1,
    construire_fichier_propositions,
    construire_plan_revue_taches,
    integrer_revues_taches,
)


class TestRevueTachesLongitudinales(unittest.TestCase):
    def setUp(self) -> None:
        self.temporaire = TemporaryDirectory()
        self.dossier_id = "P-FICTIF-TACHES"
        self.dossier_patient = Path(self.temporaire.name) / self.dossier_id
        self.dossier_clinique = self.dossier_patient / "donnees_cliniques"
        self.dossier_clinique.mkdir(parents=True)
        self._ecrire_seance(
            "2026-08-08",
            faits_rapportes=["Anxiete avant le premier trajet."],
            taches_interseances=[
                "Prendre le tram 15 minutes trois fois.",
                "Noter l'anxiete avant et apres chaque trajet.",
            ],
        )
        self._ecrire_seance(
            "2026-08-15",
            faits_rapportes=[
                "Trois trajets realises; le troisieme a ete ecourte."
            ],
            emotions=[
                {
                    "contenu": "Anxiete passee de 8/10 a 4/10.",
                    "contexte": "Pendant les trajets.",
                    "intensite": "4/10",
                }
            ],
            interventions=["Discussion sur la reprise des trajets."],
            taches_interseances=["Prendre le tram 20 minutes trois fois."],
        )
        self._ecrire_seance(
            "2026-08-22",
            faits_rapportes=["A note l'anxiete avant et apres chaque trajet."],
            comportements=[
                {
                    "contenu": "A realise trois trajets de 20 minutes.",
                    "contexte": "Au cours de la semaine.",
                }
            ],
            taches_interseances=["Prendre le tram 25 minutes trois fois."],
        )
        self._ecrire_seance(
            "2026-08-29",
            faits_rapportes=["N'a pas realise les trajets de 25 minutes."],
        )
        self.catalogue = construire_catalogue_sources_patient(
            self.dossier_patient,
            self.dossier_id,
        )
        self.plan = construire_plan_revue_taches(self.catalogue)
        self.cree_le = datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)

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

    def _source(self, texte: str) -> str:
        for entree in self.catalogue.entrees:
            if texte in json.dumps(entree.contenu, ensure_ascii=False):
                return entree.source_id
        self.fail(f"Source introuvable : {texte}")

    def _revues(self, modifications=None):
        modifications = modifications or {}
        revues = []
        for tache in self.plan:
            donnees = {
                "task_id": tache["task_id"],
                "source_consigne_id": tache["source_consigne_id"],
                "statut_resultat_propose": "resultat_non_documente",
                "realisation_documentee": None,
                "source_ids_realisation": (),
                "justification": "Aucun retour explicite admissible retrouve.",
            }
            donnees.update(modifications.get(tache["task_id"], {}))
            revues.append(RevueTacheTerra(**donnees))
        return tuple(revues)

    def _construire(self, modifications=None):
        sortie = SortieTerraPropositionsV1(
            revues_taches=self._revues(modifications)
        )
        sortie = integrer_revues_taches(sortie, self.catalogue, self.plan)
        return construire_fichier_propositions(
            sortie,
            self.catalogue,
            self.dossier_patient,
            cree_le=self.cree_le,
        )

    def test_toutes_les_taches_sont_enumerees_et_revues_une_fois(self) -> None:
        self.assertEqual(len(self.plan), 4)
        sortie = integrer_revues_taches(
            SortieTerraPropositionsV1(revues_taches=self._revues()),
            self.catalogue,
            self.plan,
        )
        self.assertEqual(len(sortie.taches_intersession), 4)
        self.assertEqual(
            [tache.source_ids[0] for tache in sortie.taches_intersession],
            [tache["source_consigne_id"] for tache in self.plan],
        )

    def test_task_id_dupliquee_est_detectee(self) -> None:
        revues = list(self._revues())
        revues[-1] = revues[0]
        with self.assertRaises(ReponseTerraInvalide):
            integrer_revues_taches(
                SortieTerraPropositionsV1(revues_taches=tuple(revues)),
                self.catalogue,
                self.plan,
            )

    def test_omission_task_id_est_detectee(self) -> None:
        with self.assertRaises(ReponseTerraInvalide):
            integrer_revues_taches(
                SortieTerraPropositionsV1(revues_taches=self._revues()[:-1]),
                self.catalogue,
                self.plan,
            )

    def test_task_id_inconnue_est_rejetee(self) -> None:
        revues = list(self._revues())
        revues[-1] = revues[-1].model_copy(update={"task_id": "task_9999"})
        with self.assertRaises(ReponseTerraInvalide):
            integrer_revues_taches(
                SortieTerraPropositionsV1(revues_taches=tuple(revues)),
                self.catalogue,
                self.plan,
            )

    def test_tache_sans_retour_devient_resultat_non_documente(self) -> None:
        fichier = self._construire()
        self.assertEqual(
            fichier.propositions[-1].contenu_propose["statut_resultat"],
            "resultat_non_documente",
        )

    def test_retour_realise_est_associe_a_la_bonne_tache(self) -> None:
        source = self._source("trois trajets de 20 minutes")
        fichier = self._construire(
            {
                "task_0003": {
                    "statut_resultat_propose": "realisee",
                    "realisation_documentee": "Trois trajets de 20 minutes realises.",
                    "source_ids_realisation": (source,),
                    "justification": "Realisation explicite de la consigne de 20 minutes.",
                }
            }
        )
        contenu = fichier.propositions[2].contenu_propose
        self.assertEqual(contenu["statut_resultat"], "realisee")
        self.assertIn("20 minutes", contenu["resultat_documente"]["contenu"])

    def test_retour_partiel_est_conserve(self) -> None:
        source = self._source("troisieme a ete ecourte")
        fichier = self._construire(
            {
                "task_0001": {
                    "statut_resultat_propose": "partielle",
                    "realisation_documentee": "Trois trajets, dont le troisieme ecourte.",
                    "source_ids_realisation": (source,),
                    "justification": "Le retour documente une realisation partielle.",
                }
            }
        )
        self.assertEqual(
            fichier.propositions[0].contenu_propose["statut_resultat"],
            "partielle",
        )

    def test_non_realisation_explicite_est_conservee(self) -> None:
        source = self._source("pas realise les trajets de 25 minutes")
        fichier = self._construire(
            {
                "task_0004": {
                    "statut_resultat_propose": "non_realisee_rapportee",
                    "realisation_documentee": "Trajets de 25 minutes non realises.",
                    "source_ids_realisation": (source,),
                    "justification": "Non-realisation explicitement rapportee.",
                }
            }
        )
        self.assertEqual(
            fichier.propositions[3].contenu_propose["statut_resultat"],
            "non_realisee_rapportee",
        )

    def test_trois_taches_proches_conservent_leur_identite(self) -> None:
        sortie = integrer_revues_taches(
            SortieTerraPropositionsV1(revues_taches=self._revues()),
            self.catalogue,
            self.plan,
        )
        consignes = [tache.consigne for tache in sortie.taches_intersession]
        self.assertIn("15 minutes", consignes[0])
        self.assertIn("20 minutes", consignes[2])
        self.assertIn("25 minutes", consignes[3])

    def test_resultat_anterieur_a_la_prescription_est_interdit(self) -> None:
        source = self._source("Anxiete avant le premier trajet")
        fichier = self._construire(
            {
                "task_0003": {
                    "statut_resultat_propose": "realisee",
                    "realisation_documentee": "Realisation pretendue.",
                    "source_ids_realisation": (source,),
                    "justification": "Source anterieure volontairement invalide.",
                }
            }
        )
        self.assertTrue(any("posterieure" in rejet.motif for rejet in fichier.rejets))

    def test_nouvelle_tache_plus_difficile_ne_prouve_pas_la_precedente(self) -> None:
        premiere = self.plan[0]
        categories = {
            source["categorie"]
            for source in premiere["sources_cliniques_posterieures"]
        }
        self.assertNotIn("taches_interseances", categories)
        self.assertEqual(
            self._construire().propositions[0].contenu_propose["statut_resultat"],
            "resultat_non_documente",
        )

    def test_baisse_anxiete_ne_prouve_pas_realisation_complete(self) -> None:
        source = self._source("8/10 a 4/10")
        fichier = self._construire(
            {
                "task_0001": {
                    "statut_resultat_propose": "realisee",
                    "realisation_documentee": "Tache declaree realisee.",
                    "source_ids_realisation": (source,),
                    "justification": "Emotion utilisee a tort comme preuve.",
                }
            }
        )
        self.assertTrue(any("reponse clinique" in rejet.motif for rejet in fichier.rejets))

    def test_intervention_seule_ne_prouve_pas_realisation(self) -> None:
        source = self._source("Discussion sur la reprise")
        fichier = self._construire(
            {
                "task_0001": {
                    "statut_resultat_propose": "realisee",
                    "realisation_documentee": "Tache declaree realisee.",
                    "source_ids_realisation": (source,),
                    "justification": "Intervention utilisee a tort comme preuve.",
                }
            }
        )
        self.assertTrue(any("reponse clinique" in rejet.motif for rejet in fichier.rejets))

    def test_source_admissible_resolue_conserve_le_resultat(self) -> None:
        source = self._source("A note l'anxiete")
        fichier = self._construire(
            {
                "task_0002": {
                    "statut_resultat_propose": "realisee",
                    "realisation_documentee": "Anxiete notee avant et apres les trajets.",
                    "source_ids_realisation": (source,),
                    "justification": "Retour explicite dans les faits rapportes.",
                }
            }
        )
        assertion = fichier.propositions[1].contenu_propose["resultat_documente"]
        self.assertTrue(assertion["source_ids"][0].startswith("src_"))

    def test_resultat_sans_provenance_resoluble_est_rejete(self) -> None:
        fichier = self._construire(
            {
                "task_0001": {
                    "statut_resultat_propose": "realisee",
                    "realisation_documentee": "Realisation sans provenance valide.",
                    "source_ids_realisation": ("source_9999",),
                    "justification": "Source inconnue volontairement invalide.",
                }
            }
        )
        self.assertTrue(any("inconnu" in rejet.motif for rejet in fichier.rejets))


if __name__ == "__main__":
    unittest.main()
