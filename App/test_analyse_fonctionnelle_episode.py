from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import json
import unittest

from pydantic import ValidationError

from analyse_fonctionnelle_episode import (
    ElementTerraV1,
    EvolutionTemporelleTerraV1,
    HypotheseTerraV1,
    IncertitudeTerraV1,
    MomentEpisode,
    NiveauCompletude,
    SortieTerraAnalyseFonctionnelleV1,
    ValidationAnalyseEchouee,
    construire_analyse_depuis_sortie,
    generer_ou_reutiliser_analyse,
    preparer_contexte_analyse,
    rendre_analyse_clinicien,
)
from modeles_longitudinaux import RelationSupport, StatutEpistemique
from source_clinique_confirmee import (
    ServiceSourceCliniqueConfirmeeV1,
    enregistrer_provenance_json_produite,
)


class FauxResponses:
    def __init__(self, sortie) -> None:
        self.sortie = sortie
        self.appels = 0

    def parse(self, **_options):
        self.appels += 1
        return SimpleNamespace(status="completed", output_parsed=self.sortie)


class FauxClient:
    def __init__(self, sortie) -> None:
        self.responses = FauxResponses(sortie)


class TestAnalyseFonctionnelleEpisodeV1(unittest.TestCase):
    def setUp(self) -> None:
        self.temporaire = TemporaryDirectory()
        self.patient = Path(self.temporaire.name) / "P-FICTIF-AFE"
        self.transcriptions = self.patient / "transcriptions"
        self.cliniques = self.patient / "donnees_cliniques"
        self.transcriptions.mkdir(parents=True)
        self.cliniques.mkdir()
        self.principale = "2026-08-22-PF.txt"
        self.complementaire = "2026-08-29-PF.txt"
        self._creer_source(
            self.principale,
            """Seance 22-08-2026
Episode choisi : troisieme trajet en tram.
Au depart, anxiete 7/10 et pensee : si ca augmente, je vais devoir descendre.
La personne est restee dans le tram jusqu'a l'arret prevu.
A l'arrivee, anxiete 5/10. Elle rapporte que noter l'anxiete lui a permis de voir qu'elle pouvait redescendre.
Lors d'un autre trajet distinct, elle a fait demi-tour avant de monter.
La comprehension partagee retenue ensemble est que l'anxiete peut redescendre.
Le clinicien et la personne ont decide de repeter l'observation.
Il est propose d'essayer un autre trajet.
Sommeil [mot incertain : redevenu] habituel.
Dans un episode distinct, elle est sortie du magasin et rapporte : « ca m'a immediatement soulagee ».
Dans un autre episode, elle a pris son telephone. L'anxiete etait a 8/10 avant, puis a 6/10 ensuite, sans lien attribue.
Dans un autre trajet, elle a ecourte le trajet.
""",
            {
                "schema_version": "2.0",
                "date_seance": "2026-08-22",
                "faits_rapportes": [
                    "Avant le troisieme trajet, la personne attend sur le quai.",
                    "Apres avoir note l'anxiete, elle rapporte l'avoir vue redescendre.",
                    "La comprehension partagee retenue ensemble est que l'anxiete peut redescendre.",
                    "Le clinicien et la personne ont decide de repeter l'observation.",
                    "Sommeil [mot incertain : redevenu] habituel.",
                    "Un proche quitte la piece pendant l'episode.",
                    "Concernant le depart du trajet cible, le trajet a ete maintenu.",
                    "Elle rapporte : ca m'a immediatement soulagee apres etre sortie du magasin.",
                ],
                "emotions": [
                    {"contenu": "Anxiete", "contexte": "Au depart du troisieme trajet.", "intensite": "7/10"},
                    {"contenu": "Anxiete", "contexte": "A l'arrivee du troisieme trajet.", "intensite": "5/10"},
                    {"contenu": "Anxiete", "contexte": "Avant de prendre son telephone.", "intensite": "8/10"},
                    {"contenu": "Anxiete", "contexte": "Ensuite, apres avoir pris son telephone.", "intensite": "6/10"},
                ],
                "cognitions": [
                    {"contenu": "Si ca augmente, je vais devoir descendre.", "contexte": "Au depart du troisieme trajet.", "referent_contextuel": "anxiete", "referent_explicitement_identifie": True},
                    {"contenu": "Noter l'anxiete lui a permis de voir qu'elle pouvait redescendre.", "contexte": "Apres avoir note l'anxiete.", "referent_contextuel": "anxiete", "referent_explicitement_identifie": True},
                ],
                "comportements": [
                    {"contenu": "Est restee dans le tram jusqu'a l'arret prevu.", "contexte": "Troisieme trajet."},
                    {"contenu": "A fait demi-tour avant de monter.", "contexte": "Autre trajet distinct."},
                    {"contenu": "A note l'anxiete avant et apres.", "contexte": "Troisieme trajet."},
                    {"contenu": "Est sortie du magasin.", "contexte": "Episode distinct au magasin."},
                    {"contenu": "A pris son telephone.", "contexte": "Episode distinct."},
                    {"contenu": "A ecourte le trajet.", "contexte": "Autre trajet."},
                ],
                "evitements": [
                    {
                        "contenu": "A explicitement evite de monter.",
                        "contexte": "Lors d'un autre trajet distinct.",
                    },
                    {
                        "contenu": "A ecourte le trajet",
                        "contexte": "Pour eviter que l'anxiete augmente lors du troisieme trajet.",
                    },
                ],
                "interventions": [
                    "Il est propose d'essayer un autre trajet.",
                    "Le clinicien et la personne ont decide de repeter l'observation.",
                ],
                "taches_interseances": ["Essayer un autre trajet."],
                "elements_incertains": ["Sommeil [mot incertain : redevenu] habituel."],
            },
        )
        self._creer_source(
            self.complementaire,
            """Seance 29-08-2026
La personne rapporte que, depuis le trajet du 22 aout, elle a repris deux trajets.
Concernant le depart du trajet cible du 22 aout, elle dit maintenant que le trajet avait ete interrompu.
Apres avoir ecourte le trajet, elle n'a pas repris le tram pendant trois jours.
Elle rapporte qu'ecourter le trajet l'a empechee de reprendre le tram pendant trois jours.
""",
            {
                "schema_version": "2.0",
                "date_seance": "2026-08-29",
                "faits_rapportes": [
                    "Depuis le trajet du 22 aout, elle a repris deux trajets.",
                    "Concernant le depart du trajet cible du 22 aout, le trajet avait ete interrompu.",
                    "Apres avoir ecourte le trajet, elle n'a pas repris le tram pendant trois jours.",
                    "Elle rapporte qu'ecourter le trajet l'a empechee de reprendre le tram pendant trois jours.",
                ],
                "emotions": [],
                "cognitions": [],
                "comportements": [],
                "evitements": [],
                "interventions": [],
                "taches_interseances": [],
                "elements_incertains": [],
            },
        )

    def tearDown(self) -> None:
        self.temporaire.cleanup()

    def _creer_source(self, nom: str, texte: str, document: dict) -> None:
        transcription = self.transcriptions / nom
        transcription.write_text(texte, encoding="utf-8")
        json_path = self.cliniques / f"{transcription.stem}.json"
        json_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        date_seance = datetime.strptime(nom[:10], "%Y-%m-%d").date()
        enregistrer_provenance_json_produite(
            self.patient,
            self.patient.name,
            date_seance,
            transcription,
            json_path,
        )
        ServiceSourceCliniqueConfirmeeV1(
            self.patient,
            transcription,
            date_seance,
            self.patient.name,
        ).confirmer(
            clinicien_id="clinicien-fictif",
            confirmation_explicite=True,
            accepter_incertitudes=True,
            confirmee_le=datetime(2026, 8, 30, tzinfo=timezone.utc),
        )

    def contexte(self, complementaire: bool = False, episode: str | None = None):
        return preparer_contexte_analyse(
            self.patient,
            self.principale,
            episode
            or "Troisieme trajet en tram du 22 aout, du depart a l'arrivee.",
            (self.complementaire,) if complementaire else (),
        )

    def source(self, contexte, categorie: str, fragment: str) -> str:
        for entree in contexte.catalogue.entrees:
            if entree.categorie == categorie and fragment.casefold() in json.dumps(
                entree.contenu, ensure_ascii=False
            ).casefold():
                return entree.source_id
        raise AssertionError(f"Source absente : {categorie} / {fragment}")

    def element(
        self,
        contexte,
        categorie: str,
        fragment: str,
        contenu: str | None = None,
        moment: MomentEpisode = MomentEpisode.INCONNU,
        intensite: str | None = None,
    ) -> ElementTerraV1:
        return ElementTerraV1(
            contenu=contenu or fragment,
            moment=moment,
            intensite_ou_frequence=intensite,
            source_ids=(self.source(contexte, categorie, fragment),),
        )

    def sortie_base(self, contexte, **modifications):
        valeurs = {
            "libelle_clinique": "Analyse du troisieme trajet en tram",
            "description_episode": "Troisieme trajet en tram du 22 aout, du depart a l'arrivee.",
            "raison_de_selection": "Épisode explicitement choisi par le clinicien.",
            "date_episode": "2026-08-22",
            "contexte_et_antecedents": (
                self.element(
                    contexte,
                    "faits_rapportes",
                    "attend sur le quai",
                    moment=MomentEpisode.AVANT,
                ),
            ),
            "comportements": (
                self.element(
                    contexte,
                    "comportements",
                    "restee dans le tram",
                    moment=MomentEpisode.PENDANT,
                ),
            ),
            "emotions": (
                self.element(
                    contexte,
                    "emotions",
                    "Au depart",
                    contenu="Anxiete rapportee",
                    moment=MomentEpisode.DEBUT,
                    intensite="7/10",
                ),
            ),
            "cognitions_images_anticipations": (
                self.element(
                    contexte,
                    "cognitions",
                    "devoir descendre",
                    moment=MomentEpisode.DEBUT,
                ),
            ),
            "consequences_immediates": (
                self.element(
                    contexte,
                    "cognitions",
                    "pouvait redescendre",
                    moment=MomentEpisode.APRES,
                ),
            ),
        }
        valeurs.update(modifications)
        return SortieTerraAnalyseFonctionnelleV1(**valeurs)

    def construire(self, sortie, contexte=None):
        return construire_analyse_depuis_sortie(
            sortie,
            contexte or self.contexte(),
            genere_le=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
        )

    def test_01_episode_complet_antecedent_reponse_consequence(self) -> None:
        contexte = self.contexte()
        analyse = self.construire(self.sortie_base(contexte), contexte)
        self.assertEqual(analyse.niveau_completude, NiveauCompletude.CHAINE_DOCUMENTEE)
        self.assertTrue(analyse.contexte_et_antecedents)
        self.assertTrue(analyse.reponses.documentees())
        self.assertTrue(analyse.consequences_immediates)
        self.assertEqual(analyse.reponses.emotions[0].contenu, "Anxiete")
        self.assertEqual(analyse.reponses.emotions[0].intensite_ou_frequence, "7/10")

    def test_02_episode_partiel_sans_consequence(self) -> None:
        contexte = self.contexte()
        sortie = self.sortie_base(contexte, consequences_immediates=())
        analyse = self.construire(sortie, contexte)
        self.assertEqual(analyse.niveau_completude, NiveauCompletude.DESCRIPTIF)
        self.assertIn("Fonction non déterminée", rendre_analyse_clinicien(analyse))

    def test_evolution_temporelle_documentee_sans_causalite(self) -> None:
        contexte = self.contexte()
        depart = self.element(
            contexte,
            "emotions",
            "Au depart",
            moment=MomentEpisode.DEBUT,
            intensite="7/10",
        )
        trajet = self.element(
            contexte,
            "comportements",
            "restee dans le tram",
            moment=MomentEpisode.PENDANT,
        )
        arrivee = self.element(
            contexte,
            "emotions",
            "A l'arrivee",
            moment=MomentEpisode.FIN,
            intensite="5/10",
        )
        sortie = self.sortie_base(
            contexte,
            contexte_et_antecedents=(),
            comportements=(trajet,),
            emotions=(depart, arrivee),
            cognitions_images_anticipations=(),
            consequences_immediates=(),
            evolutions_temporelles_documentees=(
                EvolutionTemporelleTerraV1(
                    observations=(arrivee, trajet, depart),
                ),
            ),
        )

        analyse = self.construire(sortie, contexte)
        rendu = rendre_analyse_clinicien(analyse)

        self.assertEqual(analyse.niveau_completude, NiveauCompletude.DESCRIPTIF)
        self.assertIsNone(analyse.hypothese_fonctionnelle)
        self.assertEqual(
            [item.moment for item in analyse.evolutions_temporelles_documentees[0].observations],
            [MomentEpisode.DEBUT, MomentEpisode.PENDANT, MomentEpisode.FIN],
        )
        self.assertIn("Évolutions temporelles documentées", rendu)
        self.assertIn("7/10", rendu)
        self.assertIn("5/10", rendu)
        self.assertIn("Aucun lien causal ou fonctionnel", rendu)
        self.assertNotIn("a fait diminuer l'anxiété", rendu.casefold())

    def test_motif_explicite_evitement_est_conserve(self) -> None:
        contexte = self.contexte()
        evitement = self.element(
            contexte,
            "evitements",
            "ecourte le trajet",
            moment=MomentEpisode.PENDANT,
        )
        sortie = self.sortie_base(
            contexte,
            comportements=(),
            evitements_ou_protections_documentes=(evitement,),
            consequences_immediates=(),
        )

        analyse = self.construire(sortie, contexte)

        contenu = analyse.reponses.evitements_ou_protections_documentes[0].contenu
        self.assertIn("A ecourte le trajet", contenu)
        self.assertIn("Pour eviter que l'anxiete augmente", contenu)

    def test_evolution_completee_avec_emotion_deja_selectionnee(self) -> None:
        contexte = self.contexte()
        anxiete = self.element(
            contexte,
            "emotions",
            "Au depart",
            moment=MomentEpisode.PENDANT,
            intensite="7/10",
        )
        cognition = self.element(
            contexte,
            "cognitions",
            "devoir descendre",
            moment=MomentEpisode.PENDANT,
        )
        evitement = self.element(
            contexte,
            "evitements",
            "ecourte le trajet",
            moment=MomentEpisode.PENDANT,
        )
        sortie = self.sortie_base(
            contexte,
            contexte_et_antecedents=(),
            comportements=(),
            evitements_ou_protections_documentes=(evitement,),
            emotions=(anxiete,),
            cognitions_images_anticipations=(cognition,),
            consequences_immediates=(),
            evolutions_temporelles_documentees=(
                EvolutionTemporelleTerraV1(
                    observations=(cognition, evitement),
                ),
            ),
        )

        analyse = self.construire(sortie, contexte)
        observations = analyse.evolutions_temporelles_documentees[0].observations

        self.assertEqual(len(observations), 3)
        self.assertEqual(observations[0].contenu, "Anxiete")
        self.assertEqual(observations[0].intensite_ou_frequence, "7/10")
        self.assertIn("Pour eviter que l'anxiete augmente", observations[2].contenu)

    def test_intervention_mal_classee_en_reponse_environnement_est_ecartee(self) -> None:
        contexte = self.contexte()
        intervention = self.element(
            contexte,
            "interventions",
            "Il est propose d'essayer",
            moment=MomentEpisode.APRES,
        )
        sortie = self.sortie_base(
            contexte,
            reponses_environnement=(intervention,),
        )

        analyse = self.construire(sortie, contexte)

        self.assertEqual(analyse.reponses.reponses_environnement, ())
        self.assertNotIn(
            intervention.source_ids[0],
            {reference.id for reference in analyse.provenance.references_sources},
        )

    def test_consequence_immediate_explicitement_attribuee(self) -> None:
        contexte = self.contexte(
            episode="Sortie du magasin suivie d'un soulagement rapporte.",
        )
        sortie_magasin = self.element(
            contexte,
            "comportements",
            "sortie du magasin",
            moment=MomentEpisode.PENDANT,
        )
        soulagement = self.element(
            contexte,
            "faits_rapportes",
            "immediatement soulagee",
            moment=MomentEpisode.APRES,
        )
        sortie = SortieTerraAnalyseFonctionnelleV1(
            libelle_clinique="Analyse de la sortie du magasin",
            description_episode=contexte.episode_decrit_par_clinicien,
            raison_de_selection="Épisode explicitement choisi par le clinicien.",
            date_episode="2026-08-22",
            comportements=(sortie_magasin,),
            consequences_immediates=(soulagement,),
        )

        analyse = self.construire(sortie, contexte)

        self.assertEqual(len(analyse.consequences_immediates), 1)
        self.assertIn("soulagee", analyse.consequences_immediates[0].contenu)
        self.assertIsNone(analyse.hypothese_fonctionnelle)

    def test_temporalite_seule_ne_devient_pas_causalite(self) -> None:
        contexte = self.contexte(
            episode="Prise du telephone suivie d'une diminution de l'anxiete.",
        )
        telephone = self.element(
            contexte,
            "comportements",
            "pris son telephone",
            moment=MomentEpisode.PENDANT,
        )
        avant = self.element(
            contexte,
            "emotions",
            "Avant de prendre son telephone",
            moment=MomentEpisode.AVANT,
            intensite="8/10",
        )
        ensuite = self.element(
            contexte,
            "emotions",
            "Ensuite",
            moment=MomentEpisode.APRES,
            intensite="6/10",
        )
        sortie = SortieTerraAnalyseFonctionnelleV1(
            libelle_clinique="Analyse de la prise du telephone",
            description_episode=contexte.episode_decrit_par_clinicien,
            raison_de_selection="Épisode explicitement choisi par le clinicien.",
            date_episode="2026-08-22",
            comportements=(telephone,),
            emotions=(avant, ensuite),
            evolutions_temporelles_documentees=(
                EvolutionTemporelleTerraV1(
                    observations=(avant, telephone, ensuite),
                ),
            ),
        )

        analyse = self.construire(sortie, contexte)
        rendu = rendre_analyse_clinicien(analyse).casefold()

        self.assertTrue(analyse.evolutions_temporelles_documentees)
        self.assertFalse(analyse.consequences_immediates)
        self.assertIsNone(analyse.hypothese_fonctionnelle)
        self.assertNotIn("le telephone a diminue", rendu)
        self.assertNotIn("comportement de securite", rendu)

    def test_fait_differe_temporel_reste_separe_hypothese_maintien(self) -> None:
        contexte = self.contexte(
            complementaire=True,
            episode="Trajet ecourte puis absence de reprise pendant trois jours.",
        )
        trajet_ecourte = self.element(
            contexte,
            "comportements",
            "ecourte le trajet",
            moment=MomentEpisode.PENDANT,
        )
        non_reprise = self.element(
            contexte,
            "faits_rapportes",
            "Apres avoir ecourte",
            moment=MomentEpisode.APRES,
        )
        sortie = SortieTerraAnalyseFonctionnelleV1(
            libelle_clinique="Analyse du trajet ecourte",
            description_episode=contexte.episode_decrit_par_clinicien,
            raison_de_selection="Épisode explicitement choisi par le clinicien.",
            date_episode="2026-08-22",
            comportements=(trajet_ecourte,),
            evolutions_temporelles_documentees=(
                EvolutionTemporelleTerraV1(
                    observations=(trajet_ecourte, non_reprise),
                ),
            ),
        )

        analyse = self.construire(sortie, contexte)

        self.assertTrue(analyse.evolutions_temporelles_documentees)
        self.assertIsNone(analyse.hypothese_fonctionnelle)
        self.assertEqual(len(analyse.provenance.sources_cliniques), 2)

        sortie_invalide = sortie.model_copy(
            update={
                "evolutions_temporelles_documentees": (),
                "consequences_differees": (non_reprise,),
            }
        )
        with self.assertRaises(ValidationAnalyseEchouee):
            self.construire(sortie_invalide, contexte)

    def test_03_deux_episodes_proches_non_fusionnes(self) -> None:
        contexte = self.contexte()
        analyse = self.construire(self.sortie_base(contexte), contexte)
        contenus = " ".join(item.contenu for item in analyse.reponses.comportements)
        self.assertNotIn("demi-tour", contenus)
        self.assertIn("Troisieme trajet", analyse.description_episode)

    def test_04_comportement_possiblement_protecteur_fonction_inconnue(self) -> None:
        contexte = self.contexte()
        possible = self.element(
            contexte,
            "comportements",
            "A note l'anxiete",
            contenu="Noter l'anxiete pourrait avoir une fonction de protection, a verifier.",
        )
        analyse = self.construire(
            self.sortie_base(
                contexte,
                fonctions_evitement_ou_protection_possibles=(possible,),
            ),
            contexte,
        )
        item = analyse.reponses.fonctions_evitement_ou_protection_possibles[0]
        self.assertEqual(item.statut_epistemique, StatutEpistemique.HYPOTHESE_CLINIQUE)
        self.assertFalse(analyse.reponses.evitements_ou_protections_documentes)

    def test_05_evitement_explicitement_documente(self) -> None:
        contexte = self.contexte()
        evitement = self.element(
            contexte,
            "evitements",
            "explicitement evite",
            moment=MomentEpisode.AVANT,
        )
        analyse = self.construire(
            self.sortie_base(
                contexte,
                comportements=(
                    self.element(contexte, "comportements", "fait demi-tour"),
                ),
                evitements_ou_protections_documentes=(evitement,),
            ),
            contexte,
        )
        self.assertEqual(
            analyse.reponses.evitements_ou_protections_documentes[0].statut_epistemique,
            StatutEpistemique.EXPLICITE,
        )

    def test_06_consequence_differee_source_ulterieure_explicite(self) -> None:
        contexte = self.contexte(complementaire=True)
        differee = self.element(
            contexte,
            "faits_rapportes",
            "l'a empechee de reprendre",
            moment=MomentEpisode.APRES,
        )
        analyse = self.construire(
            self.sortie_base(contexte, consequences_differees=(differee,)),
            contexte,
        )
        self.assertTrue(analyse.consequences_differees)
        self.assertEqual(len(analyse.provenance.sources_cliniques), 2)

    def test_07_hypothese_avec_preuve_limite_alternative_et_test(self) -> None:
        contexte = self.contexte()
        preuve = self.element(
            contexte,
            "cognitions",
            "pouvait redescendre",
            moment=MomentEpisode.APRES,
        )
        hypothese = HypotheseTerraV1(
            reponse_cible="Noter l'anxiete avant et apres.",
            fonction_supposee="Pourrait faciliter l'observation de sa variation.",
            effet_immediat_pertinent="La personne rapporte avoir vu l'anxiete redescendre.",
            donnees_en_faveur=(preuve,),
            donnees_en_defaveur_ou_limites=("Un seul episode est documente.",),
            hypotheses_alternatives=("La baisse pourrait etre liee au temps ecoule.",),
            prediction_ou_question_testable="La baisse est-elle aussi observee sans notation ?",
        )
        analyse = self.construire(
            self.sortie_base(contexte, hypothese_fonctionnelle=hypothese),
            contexte,
        )
        self.assertEqual(
            analyse.niveau_completude,
            NiveauCompletude.HYPOTHESE_FONCTIONNELLE,
        )
        self.assertNotIn("confiance", analyse.model_dump_json().casefold())

    def test_08_absence_hypothese_si_non_defendable(self) -> None:
        contexte = self.contexte()
        analyse = self.construire(
            self.sortie_base(
                contexte,
                consequences_immediates=(),
                hypothese_fonctionnelle=None,
            ),
            contexte,
        )
        self.assertIsNone(analyse.hypothese_fonctionnelle)

    def test_09_marqueur_ocr_central_jamais_reconstruit(self) -> None:
        contexte = self.contexte()
        passage = "Sommeil [mot incertain : redevenu] habituel."
        sortie = self.sortie_base(
            contexte,
            incertitudes_source=(
                IncertitudeTerraV1(
                    passage_exact=passage,
                    incidence="Element ecarte de la chaine fonctionnelle.",
                ),
            ),
        )
        analyse = self.construire(sortie, contexte)
        self.assertEqual(analyse.incertitudes_source[0].passage_exact, passage)
        self.assertNotIn("Sommeil redevenu", rendre_analyse_clinicien(analyse))

    def test_sortie_incertitude_ignoree_si_aucun_passage_source_signale(self) -> None:
        contexte = self.contexte()
        source_sans_incertitude = contexte.source_principale.model_copy(
            update={"passages_signales": ()}
        )
        contexte = contexte.model_copy(
            update={"source_principale": source_sans_incertitude}
        )
        sortie = self.sortie_base(
            contexte,
            incertitudes_source=(
                IncertitudeTerraV1(
                    passage_exact="L'envie de descendre n'est pas precisee.",
                    incidence="Donnee clinique a explorer.",
                ),
            ),
        )

        analyse = self.construire(sortie, contexte)

        self.assertEqual(analyse.incertitudes_source, ())

    def test_passage_incertitude_non_identique_reste_refuse(self) -> None:
        contexte = self.contexte()
        sortie = self.sortie_base(
            contexte,
            incertitudes_source=(
                IncertitudeTerraV1(
                    passage_exact="Sommeil [mot incertain : redevenu normalement] habituel.",
                    incidence="Element ecarte de la chaine fonctionnelle.",
                ),
            ),
        )

        with self.assertRaises(ValidationAnalyseEchouee):
            self.construire(sortie, contexte)

    def test_10_contradiction_reelle_meme_moment(self) -> None:
        contexte = self.contexte(complementaire=True)
        maintenu = self.element(
            contexte,
            "faits_rapportes",
            "trajet a ete maintenu",
            moment=MomentEpisode.PENDANT,
        )
        interrompu = self.element(
            contexte,
            "faits_rapportes",
            "trajet avait ete interrompu",
            moment=MomentEpisode.PENDANT,
        )
        sortie = self.sortie_base(
            contexte,
            contradictions=(
                {
                    "moment_decrit": "Depart du trajet cible du 22 aout",
                    "formulations": (maintenu, interrompu),
                },
            ),
        )
        analyse = self.construire(sortie, contexte)
        self.assertEqual(len(analyse.contradictions), 1)
        references = {
            reference.id: reference
            for reference in analyse.provenance.references_sources
        }
        for formulation in analyse.contradictions[0].formulations:
            self.assertEqual(
                references[formulation.source_ids[0]].relation_support,
                RelationSupport.CONTRADICTOIRE,
            )

    def test_11_intensites_a_deux_moments_non_contradiction(self) -> None:
        contexte = self.contexte()
        depart = self.element(
            contexte,
            "emotions",
            "Au depart",
            contenu="Anxiete 7/10",
            moment=MomentEpisode.DEBUT,
        )
        arrivee = self.element(
            contexte,
            "emotions",
            "A l'arrivee",
            contenu="Anxiete 5/10",
            moment=MomentEpisode.FIN,
        )
        sortie = self.sortie_base(
            contexte,
            contradictions=(
                {
                    "moment_decrit": "Trajet",
                    "formulations": (depart, arrivee),
                },
            ),
        )
        with self.assertRaises(ValidationAnalyseEchouee):
            self.construire(sortie, contexte)

    def test_12_comprehension_partagee_explicitement_documentee(self) -> None:
        contexte = self.contexte()
        partagee = self.element(
            contexte,
            "faits_rapportes",
            "comprehension partagee retenue ensemble",
        )
        analyse = self.construire(
            self.sortie_base(
                contexte,
                formulation_partagee_documentee=partagee,
            ),
            contexte,
        )
        self.assertIsNotNone(analyse.formulation_partagee_documentee)

    def test_13_suggestion_intervention_ne_devient_pas_decision(self) -> None:
        contexte = self.contexte()
        suggestion = self.element(
            contexte,
            "interventions",
            "Il est propose",
        )
        sortie = self.sortie_base(
            contexte,
            decision_clinique_documentee=suggestion,
        )
        with self.assertRaises(ValidationAnalyseEchouee):
            self.construire(sortie, contexte)

    def test_14_second_lancement_idempotent_sans_appel(self) -> None:
        contexte = self.contexte()
        sortie = self.sortie_base(contexte)
        client = FauxClient(sortie)
        creations_client = 0

        def creer_client():
            nonlocal creations_client
            creations_client += 1
            return client

        premiere, _, reutilisee_1 = generer_ou_reutiliser_analyse(
            contexte,
            creer_client,
            genere_le=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
        )
        seconde, reponse_2, reutilisee_2 = generer_ou_reutiliser_analyse(
            contexte,
            creer_client,
        )
        self.assertFalse(reutilisee_1)
        self.assertTrue(reutilisee_2)
        self.assertIsNone(reponse_2)
        self.assertEqual(creations_client, 1)
        self.assertEqual(client.responses.appels, 1)
        self.assertEqual(premiere, seconde)

    def test_element_terra_refuse_plusieurs_sources_atomiques(self) -> None:
        with self.assertRaises(ValidationError):
            ElementTerraV1(
                contenu="Element fusionne interdit.",
                source_ids=("source_0001", "source_0002"),
            )

    def test_contexte_ne_peut_pas_reutiliser_un_comportement(self) -> None:
        contexte = self.contexte()
        comportement = self.element(
            contexte,
            "comportements",
            "restee dans le tram",
        )
        sortie = self.sortie_base(
            contexte,
            contexte_et_antecedents=(comportement,),
        )
        with self.assertRaises(ValidationAnalyseEchouee):
            self.construire(sortie, contexte)

    def test_emotion_ne_devient_pas_consequence_immediate(self) -> None:
        contexte = self.contexte()
        emotion = self.element(
            contexte,
            "emotions",
            "A l'arrivee",
            moment=MomentEpisode.FIN,
        )
        sortie = self.sortie_base(
            contexte,
            consequences_immediates=(emotion,),
        )
        with self.assertRaises(ValidationAnalyseEchouee):
            self.construire(sortie, contexte)

    def test_source_atomique_ne_peut_pas_etre_dupliquee_entre_rubriques(self) -> None:
        contexte = self.contexte()
        comportement = self.element(
            contexte,
            "comportements",
            "restee dans le tram",
            moment=MomentEpisode.PENDANT,
        )
        sortie = self.sortie_base(
            contexte,
            comportements=(comportement,),
            consequences_immediates=(comportement,),
        )
        with self.assertRaises(ValidationAnalyseEchouee):
            self.construire(sortie, contexte)

    def test_moment_explicite_source_prime_sur_proposition(self) -> None:
        contexte = self.contexte()
        emotion = self.element(
            contexte,
            "emotions",
            "A l'arrivee",
            moment=MomentEpisode.DEBUT,
        )
        analyse = self.construire(
            self.sortie_base(
                contexte,
                emotions=(emotion,),
            ),
            contexte,
        )
        self.assertEqual(analyse.reponses.emotions[0].moment, MomentEpisode.FIN)


if __name__ == "__main__":
    unittest.main()
