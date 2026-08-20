from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest

from pydantic import ValidationError

from catalogue_sources_longitudinales import (
    ReferenceCatalogueInvalide,
    construire_catalogue_sources_patient,
)
from generation_propositions_longitudinales import (
    MODEL_PROPOSITIONS_LONGITUDINALES,
    REASONING_EFFORT_PROPOSITIONS,
    PropositionElementTerra,
    PropositionObjectifTerra,
    PropositionProblemeTerra,
    PropositionTacheTerra,
    ReponseTerraInvalide,
    SortieTerraPropositionsV1,
    calculer_empreinte_generation,
    construire_fichier_propositions,
    generer_propositions_longitudinales,
)
from modeles_longitudinaux import (
    AssertionClinique,
    FichierPropositionsLongitudinalesV1,
    RegistreLongitudinalV1,
    StatutEpistemique,
    TypeObjetLongitudinal,
    ValidationClinique,
    charger_propositions,
    creer_objet_valide,
    enregistrer_propositions,
)


class FauxResponses:
    def __init__(self, reponse) -> None:
        self.reponse = reponse
        self.parametres = None

    def parse(self, **parametres):
        self.parametres = parametres
        return self.reponse


class FauxClient:
    def __init__(self, reponse) -> None:
        self.responses = FauxResponses(reponse)


class TestGenerationPropositionsLongitudinales(unittest.TestCase):
    def setUp(self) -> None:
        self.temporaire = TemporaryDirectory()
        self.racine = Path(self.temporaire.name)
        self.dossier_id = "P-FICTIF-GENERATION"
        self.dossier_patient = self.racine / self.dossier_id
        self.dossier_clinique = self.dossier_patient / "donnees_cliniques"
        self.dossier_clinique.mkdir(parents=True)
        self.chemin_document = self.dossier_clinique / "seance.json"
        self.document = {
            "schema_version": "2.0",
            "date_seance": "2026-08-08",
            "faits_rapportes": ["Difficulte fictive documentee."],
            "emotions": [
                {
                    "contenu": "Emotion fictive",
                    "contexte": "Contexte fictif",
                    "intensite": "6/10",
                }
            ],
            "cognitions": [],
            "comportements": [],
            "evitements": [],
            "interventions": ["Intervention fictive realisee."],
            "taches_interseances": ["Tache fictive proposee."],
            "elements_incertains": ["Information fictive [illisible]."],
        }
        self._ecrire_document()
        self.catalogue = construire_catalogue_sources_patient(
            self.dossier_patient,
            self.dossier_id,
        )
        self.cree_le = datetime(2026, 8, 9, 9, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temporaire.cleanup()

    def _ecrire_document(self) -> None:
        self.chemin_document.write_text(
            json.dumps(self.document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _sortie_quatre_types(self) -> SortieTerraPropositionsV1:
        return SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="synthese_prudente",
                    source_ids=("source_0001", "source_0002"),
                    justification="Deux donnees fictives soutiennent le candidat.",
                    libelle="Difficulte fictive suivie.",
                ),
            ),
            objectifs_therapeutiques=(
                PropositionObjectifTerra(
                    operation="creation",
                    statut_epistemique="synthese_prudente",
                    source_ids=("source_0001",),
                    justification="Direction fictive a confirmer avec le clinicien.",
                    formulation="Clarifier une direction fictive de changement.",
                    type_objectif="resultat",
                ),
            ),
            taches_intersession=(
                PropositionTacheTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0004",),
                    justification="La tache est explicitement documentee.",
                    consigne="Tache fictive proposee.",
                    date_proposition_ou_accord=date(2026, 8, 8),
                ),
            ),
            elements_a_reprendre=(
                PropositionElementTerra(
                    operation="creation",
                    statut_epistemique="inconnu_a_explorer",
                    source_ids=("source_0005",),
                    justification="L'incertitude fictive doit rester visible.",
                    contenu="Clarifier l'information fictive illisible.",
                    source_cible_id="source_0005",
                ),
            ),
        )

    def _construire(self, sortie=None, registre=None):
        return construire_fichier_propositions(
            sortie or self._sortie_quatre_types(),
            self.catalogue,
            self.dossier_patient,
            registre=registre,
            cree_le=self.cree_le,
        )

    def _assert_rejet_unique(self, sortie, motif: str | None = None):
        fichier = self._construire(sortie)
        self.assertEqual(fichier.propositions, ())
        self.assertEqual(len(fichier.rejets), 1)
        if motif is not None:
            self.assertIn(motif, fichier.rejets[0].motif)
        return fichier.rejets[0]

    def _ajouter_seance_resultat(self, **categories):
        document = {
            "schema_version": "2.0",
            "date_seance": "2026-08-15",
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
        chemin = self.dossier_clinique / "seance_resultat.json"
        chemin.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.catalogue = construire_catalogue_sources_patient(
            self.dossier_patient,
            self.dossier_id,
        )
        return {
            entree.categorie: entree.source_id
            for entree in self.catalogue.entrees
            if entree.date_seance == date(2026, 8, 15)
        }

    def test_validation_partielle_conserve_trois_propositions_valides(self) -> None:
        sortie = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0001",),
                    justification="Difficulte directement documentee.",
                    libelle="Difficulte fictive.",
                ),
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0003",),
                    justification="Source inadmissible pour un probleme.",
                    libelle="Probleme invalide.",
                ),
            ),
            objectifs_therapeutiques=(
                PropositionObjectifTerra(
                    operation="creation",
                    statut_epistemique="synthese_prudente",
                    source_ids=("source_0001",),
                    justification="Direction a confirmer.",
                    formulation="Clarifier une direction de changement.",
                    type_objectif="resultat",
                ),
            ),
            taches_intersession=(
                PropositionTacheTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0004",),
                    justification="Tache documentee.",
                    consigne="Tache fictive proposee.",
                    date_proposition_ou_accord=date(2026, 8, 8),
                ),
            ),
        )

        fichier = self._construire(sortie)

        self.assertEqual(len(fichier.propositions), 3)
        self.assertEqual(len(fichier.rejets), 1)
        self.assertEqual(fichier.rejets[0].position_sortie, 2)
        self.assertIn("donnees cliniques directes", fichier.rejets[0].motif)

    def test_tache_realisee_conserve_resultat_et_sources_separees(self) -> None:
        sources = self._ajouter_seance_resultat(
            comportements=[
                {
                    "contenu": "A realise la tache fictive.",
                    "contexte": "Cette semaine.",
                }
            ]
        )
        sortie = SortieTerraPropositionsV1(
            taches_intersession=(
                PropositionTacheTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0004", sources["comportements"]),
                    justification="Consigne et realisation documentees.",
                    consigne="Tache fictive proposee.",
                    date_proposition_ou_accord=date(2026, 8, 8),
                    cycle_propose="close",
                    statut_decision_propose="proposee_documentee",
                    statut_resultat_propose="realisee",
                    resultat_documente="La tache fictive a ete realisee.",
                ),
            )
        )

        contenu = self._construire(sortie).propositions[0].contenu_propose

        self.assertEqual(contenu["cycle"], "close")
        self.assertEqual(contenu["statut_decision"], "proposee_documentee")
        self.assertEqual(contenu["statut_resultat"], "realisee")
        self.assertEqual(
            contenu["resultat_documente"]["contenu"],
            "La tache fictive a ete realisee.",
        )
        self.assertNotEqual(
            contenu["consigne"]["source_ids"],
            contenu["resultat_documente"]["source_ids"],
        )

    def test_tache_partielle_conserve_resultat(self) -> None:
        sources = self._ajouter_seance_resultat(
            evitements=[
                {
                    "contenu": "A interrompu une partie de la tache fictive.",
                    "contexte": "Lors de la troisieme tentative.",
                }
            ]
        )
        sortie = SortieTerraPropositionsV1(
            taches_intersession=(
                PropositionTacheTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0004", sources["evitements"]),
                    justification="Realisation partielle documentee.",
                    consigne="Tache fictive proposee.",
                    date_proposition_ou_accord=date(2026, 8, 8),
                    cycle_propose="close",
                    statut_resultat_propose="partielle",
                    resultat_documente="La tache a ete partiellement realisee.",
                ),
            )
        )

        contenu = self._construire(sortie).propositions[0].contenu_propose

        self.assertEqual(contenu["statut_resultat"], "partielle")
        self.assertIsNotNone(contenu["resultat_documente"])

    def test_faux_resultat_sans_source_clinique_est_rejete(self) -> None:
        sortie = SortieTerraPropositionsV1(
            taches_intersession=(
                PropositionTacheTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0004",),
                    justification="Resultat non soutenu.",
                    consigne="Tache fictive proposee.",
                    date_proposition_ou_accord=date(2026, 8, 8),
                    cycle_propose="close",
                    statut_resultat_propose="realisee",
                    resultat_documente="La tache aurait ete realisee.",
                ),
            )
        )

        self._assert_rejet_unique(sortie, "source clinique directe distincte")

    def test_regroupement_multisource_exige_synthese_prudente(self) -> None:
        explicite = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0001", "source_0002"),
                    justification="Regroupement de deux donnees.",
                    libelle="Difficulte fictive regroupee.",
                ),
            )
        )
        prudente = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="synthese_prudente",
                    source_ids=("source_0001", "source_0002"),
                    justification="Regroupement prudent de deux donnees.",
                    libelle="Difficulte fictive regroupee.",
                ),
            )
        )

        self._assert_rejet_unique(explicite, "plusieurs sources")
        fichier = self._construire(prudente)
        self.assertEqual(len(fichier.propositions), 1)
        self.assertEqual(fichier.rejets, ())

    def test_observation_unique_reste_candidate_et_peut_etre_proposee(self) -> None:
        sortie = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0001",),
                    justification="Impact longitudinal explicitement documente.",
                    libelle="Difficulte unique mais importante.",
                    etat_propose="actif",
                ),
            )
        )

        contenu = self._construire(sortie).propositions[0].contenu_propose

        self.assertEqual(contenu["etat"], "candidat")

    def test_evenement_ponctuel_ne_devient_pas_actif_automatiquement(self) -> None:
        sortie = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0002",),
                    justification="Emotion isolee.",
                    libelle="Emotion fictive isolee.",
                    etat_propose="actif",
                ),
            )
        )

        contenu = self._construire(sortie).propositions[0].contenu_propose

        self.assertEqual(contenu["etat"], "candidat")

    def test_conversion_des_quatre_types(self) -> None:
        fichier = self._construire()

        self.assertEqual(len(fichier.propositions), 4)
        self.assertEqual(
            {proposition.type_objet for proposition in fichier.propositions},
            set(TypeObjetLongitudinal),
        )
        for proposition in fichier.propositions:
            self.assertEqual(proposition.statut_action.value, "proposition_systeme")
            self.assertEqual(proposition.statut_documentaire, "brouillon_genere")
            self.assertEqual(proposition.etat_revue.value, "a_revoir")
            self.assertTrue(all(source.startswith("src_") for source in proposition.source_ids))

    def test_assertion_prudente_recoit_periode_et_sources_techniques(self) -> None:
        proposition = self._construire().propositions[0]
        libelle = proposition.contenu_propose["libelle"]

        self.assertEqual(libelle["statut_epistemique"], "synthese_prudente")
        self.assertEqual(libelle["periode_couverte"]["date_debut"], "2026-08-08")
        self.assertTrue(libelle["source_ids"][0].startswith("src_"))

    def test_tache_reste_proposee_et_sans_resultat_invente(self) -> None:
        proposition = self._construire().propositions[2]
        contenu = proposition.contenu_propose

        self.assertEqual(contenu["statut_decision"], "proposee_documentee")
        self.assertEqual(contenu["statut_resultat"], "resultat_non_documente")
        self.assertIsNone(contenu["resultat_documente"])
        self.assertEqual(contenu["cycle"], "ouverte")

    def test_incertitude_reste_inconnue_et_cible_la_source_resolue(self) -> None:
        proposition = self._construire().propositions[3]
        contenu = proposition.contenu_propose

        self.assertEqual(
            contenu["contenu"]["statut_epistemique"],
            "inconnu_a_explorer",
        )
        self.assertTrue(contenu["cible"]["source_id"].startswith("src_"))

    def test_source_id_inconnu_refuse(self) -> None:
        sortie = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_9999",),
                    justification="Justification fictive.",
                    libelle="Probleme fictif.",
                ),
            )
        )

        self._assert_rejet_unique(sortie, "inconnu")

    def test_reference_obsolete_refusee_apres_terra(self) -> None:
        self.document["faits_rapportes"][0] = "Fait fictif modifie."
        self._ecrire_document()

        with self.assertRaises(ReferenceCatalogueInvalide):
            self._construire()

    def test_injection_directe_reference_technique_refusee_par_pydantic(self) -> None:
        donnees = {
            "operation": "creation",
            "statut_epistemique": "explicite",
            "source_ids": ["source_0001"],
            "justification": "Justification fictive.",
            "libelle": "Probleme fictif.",
            "document": "donnees_cliniques/seance.json",
            "json_pointer": "/faits_rapportes/0",
            "document_sha256": "a" * 64,
        }

        with self.assertRaises(ValidationError):
            PropositionProblemeTerra.model_validate(donnees)

    def test_proposition_sans_source_refusee_par_pydantic(self) -> None:
        with self.assertRaises(ValidationError):
            PropositionProblemeTerra(
                operation="creation",
                statut_epistemique="explicite",
                source_ids=(),
                justification="Justification fictive.",
                libelle="Probleme fictif.",
            )

    def test_identifiant_court_mal_forme_refuse_par_pydantic(self) -> None:
        with self.assertRaises(ValidationError):
            PropositionProblemeTerra(
                operation="creation",
                statut_epistemique="explicite",
                source_ids=("source_1",),
                justification="Justification fictive.",
                libelle="Probleme fictif.",
            )

    def test_probleme_ne_peut_pas_etre_soutenu_par_une_tache(self) -> None:
        sortie = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0004",),
                    justification="Justification fictive.",
                    libelle="Probleme fictif.",
                ),
            )
        )

        self._assert_rejet_unique(sortie, "donnees cliniques directes")

    def test_objectif_v2_ne_peut_pas_devenir_explicite(self) -> None:
        sortie = SortieTerraPropositionsV1(
            objectifs_therapeutiques=(
                PropositionObjectifTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0001",),
                    justification="Justification fictive.",
                    formulation="Objectif fictif.",
                    type_objectif="resultat",
                ),
            )
        )

        self._assert_rejet_unique(sortie, "synthese prudente")

    def test_intervention_ou_tache_seule_ne_devient_pas_objectif(self) -> None:
        sortie = SortieTerraPropositionsV1(
            objectifs_therapeutiques=(
                PropositionObjectifTerra(
                    operation="creation",
                    statut_epistemique="synthese_prudente",
                    source_ids=("source_0003", "source_0004"),
                    justification="Justification fictive.",
                    formulation="Objectif fictif probable.",
                    type_objectif="resultat",
                ),
            )
        )

        self._assert_rejet_unique(sortie, "tache seule")

    def test_tache_sans_categorie_tache_refusee(self) -> None:
        sortie = SortieTerraPropositionsV1(
            taches_intersession=(
                PropositionTacheTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0003",),
                    justification="Justification fictive.",
                    consigne="Tache fictive.",
                    date_proposition_ou_accord=date(2026, 8, 8),
                ),
            )
        )

        self._assert_rejet_unique(sortie, "source taches_interseances")

    def test_source_incertaine_ne_devient_pas_fait_explicite(self) -> None:
        sortie = SortieTerraPropositionsV1(
            elements_a_reprendre=(
                PropositionElementTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0005",),
                    justification="Justification fictive.",
                    contenu="Element fictif certain.",
                ),
            )
        )

        self._assert_rejet_unique(sortie, "source incertaine")

    def test_date_de_tache_inventee_refusee(self) -> None:
        sortie = SortieTerraPropositionsV1(
            taches_intersession=(
                PropositionTacheTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_0004",),
                    justification="Justification fictive.",
                    consigne="Tache fictive.",
                    date_proposition_ou_accord=date(2026, 8, 9),
                ),
            )
        )

        self._assert_rejet_unique(sortie, "date source")

    def test_resolution_ne_peut_pas_reposer_sur_une_synthese(self) -> None:
        sortie = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="changement_etat",
                    objet_cible_id="prb_" + "a" * 32,
                    version_objet_cible=1,
                    statut_epistemique="synthese_prudente",
                    source_ids=("source_0001",),
                    justification="La non-mention ne suffit pas a resoudre.",
                    etat_propose="resolu",
                ),
            )
        )

        self._assert_rejet_unique(sortie, "donnee explicite source")

    def test_serialisation_ne_promeut_pas_les_propositions(self) -> None:
        fichier = self._construire()
        chemin = self.racine / "propositions.json"

        enregistrer_propositions(fichier, chemin)
        recharge = charger_propositions(chemin)

        self.assertEqual(recharge, fichier)
        self.assertTrue(
            all(p.etat_revue.value == "a_revoir" for p in recharge.propositions)
        )

    def test_appel_terra_recoit_uniquement_vue_clinique_et_source_ids(self) -> None:
        reponse = SimpleNamespace(
            status="completed",
            output_parsed=self._sortie_quatre_types(),
            usage=SimpleNamespace(input_tokens=100, output_tokens=40, total_tokens=140),
        )
        client = FauxClient(reponse)

        fichier, retour = generer_propositions_longitudinales(
            client,
            self.catalogue,
            self.dossier_patient,
            cree_le=self.cree_le,
        )

        self.assertEqual(len(fichier.propositions), 4)
        self.assertIs(retour, reponse)
        parametres = client.responses.parametres
        self.assertEqual(parametres["model"], MODEL_PROPOSITIONS_LONGITUDINALES)
        self.assertEqual(
            parametres["reasoning"],
            {"effort": REASONING_EFFORT_PROPOSITIONS},
        )
        donnees_utilisateur = parametres["input"][1]["content"]
        for interdit in (
            "document_sha256",
            "element_sha256",
            "json_pointer",
            "donnees_cliniques/",
            "src_",
        ):
            self.assertNotIn(interdit, donnees_utilisateur)
        self.assertIn("source_0001", donnees_utilisateur)

    def test_reponse_incomplete_conserve_l_usage(self) -> None:
        reponse = SimpleNamespace(
            status="incomplete",
            incomplete_details="limite fictive",
            output_parsed=None,
            usage=SimpleNamespace(input_tokens=10, output_tokens=2, total_tokens=12),
        )
        client = FauxClient(reponse)

        with self.assertRaises(ReponseTerraInvalide) as capture:
            generer_propositions_longitudinales(
                client,
                self.catalogue,
                self.dossier_patient,
            )

        self.assertIs(capture.exception.reponse, reponse)
        self.assertEqual(capture.exception.reponse.usage.total_tokens, 12)

    def test_rejet_post_terra_conserve_l_usage(self) -> None:
        sortie = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="creation",
                    statut_epistemique="explicite",
                    source_ids=("source_9999",),
                    justification="Justification fictive.",
                    libelle="Probleme fictif.",
                ),
            )
        )
        reponse = SimpleNamespace(
            status="completed",
            output_parsed=sortie,
            usage=SimpleNamespace(input_tokens=20, output_tokens=5, total_tokens=25),
        )
        client = FauxClient(reponse)

        fichier, retour = generer_propositions_longitudinales(
            client,
            self.catalogue,
            self.dossier_patient,
        )

        self.assertIs(retour, reponse)
        self.assertEqual(retour.usage.total_tokens, 25)
        self.assertEqual(fichier.propositions, ())
        self.assertEqual(len(fichier.rejets), 1)

    def test_sortie_vide_valide_et_ne_modifie_aucun_registre(self) -> None:
        validation = ValidationClinique(
            validateur_id="clinicien-fictif",
            valide_le=self.cree_le,
            motif="Creation fictive validee pour le test.",
        )
        reference = self.catalogue.entrees[0].reference
        probleme = creer_objet_valide(
            TypeObjetLongitudinal.PROBLEME_SUIVI,
            {
                "etat": "actif",
                "libelle": AssertionClinique(
                    contenu="Probleme fictif valide.",
                    statut_epistemique=StatutEpistemique.EXPLICITE,
                    source_ids=(reference.id,),
                ),
                "relations": (),
            },
            validation,
            (reference.id,),
        )
        registre = RegistreLongitudinalV1(
            dossier_id_pseudonymise=self.dossier_id,
            version_registre=1,
            date_coupure=date(2026, 8, 8),
            statut_documentaire="valide_clinicien",
            references_sources=(reference,),
            problemes_suivis=(probleme,),
        )
        avant = registre.model_dump_json()

        fichier = self._construire(SortieTerraPropositionsV1(), registre)

        self.assertEqual(fichier.propositions, ())
        self.assertEqual(registre.model_dump_json(), avant)
        self.assertEqual(len(registre.problemes_suivis), 1)

    def test_modification_cible_versionnee_sans_promotion(self) -> None:
        validation = ValidationClinique(
            validateur_id="clinicien-fictif",
            valide_le=self.cree_le,
            motif="Creation fictive validee pour le test.",
        )
        reference = self.catalogue.entrees[0].reference
        probleme = creer_objet_valide(
            TypeObjetLongitudinal.PROBLEME_SUIVI,
            {
                "etat": "actif",
                "libelle": AssertionClinique(
                    contenu="Ancien libelle fictif.",
                    statut_epistemique=StatutEpistemique.EXPLICITE,
                    source_ids=(reference.id,),
                ),
                "relations": (),
            },
            validation,
            (reference.id,),
        )
        registre = RegistreLongitudinalV1(
            dossier_id_pseudonymise=self.dossier_id,
            version_registre=1,
            date_coupure=date(2026, 8, 8),
            statut_documentaire="valide_clinicien",
            references_sources=(reference,),
            problemes_suivis=(probleme,),
        )
        sortie = SortieTerraPropositionsV1(
            problemes_suivis=(
                PropositionProblemeTerra(
                    operation="modification",
                    objet_cible_id=probleme.id,
                    version_objet_cible=1,
                    statut_epistemique="explicite",
                    source_ids=("source_0001",),
                    justification="Nouveau libelle fictif explicitement documente.",
                    libelle="Nouveau libelle fictif.",
                ),
            )
        )

        fichier = self._construire(sortie, registre)

        proposition = fichier.propositions[0]
        self.assertEqual(proposition.objet_cible_id, probleme.id)
        self.assertEqual(proposition.differences[0].champ, "libelle")
        self.assertEqual(registre.problemes_suivis[0].version, 1)
        self.assertEqual(
            registre.problemes_suivis[0].libelle.contenu,
            "Ancien libelle fictif.",
        )

    def test_empreinte_change_avec_registre(self) -> None:
        sans_registre = calculer_empreinte_generation(self.catalogue, None)
        validation = ValidationClinique(
            validateur_id="clinicien-fictif",
            valide_le=self.cree_le,
            motif="Creation fictive validee pour le test.",
        )
        reference = self.catalogue.entrees[0].reference
        probleme = creer_objet_valide(
            TypeObjetLongitudinal.PROBLEME_SUIVI,
            {
                "etat": "actif",
                "libelle": AssertionClinique(
                    contenu="Probleme fictif.",
                    statut_epistemique=StatutEpistemique.EXPLICITE,
                    source_ids=(reference.id,),
                ),
                "relations": (),
            },
            validation,
            (reference.id,),
        )
        registre = RegistreLongitudinalV1(
            dossier_id_pseudonymise=self.dossier_id,
            version_registre=1,
            date_coupure=date(2026, 8, 8),
            statut_documentaire="valide_clinicien",
            references_sources=(reference,),
            problemes_suivis=(probleme,),
        )

        self.assertNotEqual(
            sans_registre,
            calculer_empreinte_generation(self.catalogue, registre),
        )


if __name__ == "__main__":
    unittest.main()
