from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError

from modeles_longitudinaux import (
    AssertionClinique,
    CycleTache,
    ElementAReprendre,
    EtatElementAReprendre,
    EtatObjectif,
    EtatProbleme,
    EtatRevueProposition,
    FichierPropositionsLongitudinalesV1,
    ObjectifTherapeutique,
    PeriodeCouverte,
    ProblemeSuivi,
    PropositionMiseAJour,
    ReferenceSourceV1,
    RegistreLongitudinalV1,
    RelationSupport,
    RelationObjet,
    StatutDecisionTache,
    StatutDocumentaireValide,
    StatutEpistemique,
    StatutResultatTache,
    TacheIntersession,
    TypeObjectif,
    TypeObjetLongitudinal,
    TypeOperationProposee,
    TypeRevision,
    ValidationClinique,
    charger_propositions,
    charger_registre,
    creer_objet_valide,
    creer_reference_source_v1,
    enregistrer_propositions,
    enregistrer_registre,
    generer_identifiant_proposition,
    promouvoir_proposition_creation,
    reviser_objet,
)


HASH_DOCUMENT = "a" * 64
HASH_ELEMENT = "b" * 64
HASH_PROMPT = "c" * 64
HASH_SOURCES = "d" * 64


class TestModelesLongitudinaux(unittest.TestCase):
    def setUp(self) -> None:
        self.source = creer_reference_source_v1(
            dossier_id_pseudonymise="DOSSIER-FICTIF",
            document="donnees_cliniques/seance-fictive.json",
            document_sha256=HASH_DOCUMENT,
            date_seance=date(2026, 8, 1),
            categorie_source="faits_rapportes",
            json_pointer="/faits_rapportes/0",
            element_sha256=HASH_ELEMENT,
            relation_support=RelationSupport.DIRECT,
            extraction_schema_version="2.0",
        )
        self.validation = self.creer_validation(
            jour=2,
            motif="Validation clinique fictive.",
        )

    @staticmethod
    def creer_validation(
        *,
        jour: int,
        motif: str,
    ) -> ValidationClinique:
        return ValidationClinique(
            validateur_id="CLINICIEN-FICTIF",
            valide_le=datetime(
                2026,
                8,
                jour,
                10,
                0,
                tzinfo=timezone.utc,
            ),
            motif=motif,
        )

    def assertion_explicite(
        self,
        contenu: str,
    ) -> AssertionClinique:
        return AssertionClinique(
            contenu=contenu,
            statut_epistemique=StatutEpistemique.EXPLICITE,
            source_ids=(self.source.id,),
        )

    def assertion_prudente(
        self,
        contenu: str,
    ) -> AssertionClinique:
        return AssertionClinique(
            contenu=contenu,
            statut_epistemique=StatutEpistemique.SYNTHESE_PRUDENTE,
            source_ids=(self.source.id,),
            periode_couverte=PeriodeCouverte(
                date_debut=date(2026, 8, 1),
                date_fin=date(2026, 8, 1),
            ),
        )

    def creer_probleme(self) -> ProblemeSuivi:
        objet = creer_objet_valide(
            TypeObjetLongitudinal.PROBLEME_SUIVI,
            {
                "etat": EtatProbleme.ACTIF,
                "libelle": self.assertion_explicite(
                    "Difficulte fictive dans une situation definie."
                ),
                "description": None,
                "contexte": (),
                "impact": (),
                "priorite": None,
                "objectif_ids": (),
                "tache_ids": (),
                "relations": (),
            },
            self.validation,
            (self.source.id,),
        )
        self.assertIsInstance(objet, ProblemeSuivi)
        return objet

    def creer_objectif(
        self,
        probleme: ProblemeSuivi,
    ) -> ObjectifTherapeutique:
        objet = creer_objet_valide(
            TypeObjetLongitudinal.OBJECTIF_THERAPEUTIQUE,
            {
                "etat": EtatObjectif.ACTIF,
                "type_objectif": TypeObjectif.RESULTAT,
                "formulation": self.assertion_explicite(
                    "Pouvoir realiser une activite fictive definie."
                ),
                "probleme_ids": (probleme.id,),
                "indicateurs_atteinte": (),
                "importance": None,
                "priorite": None,
                "horizon": None,
                "relations": (),
            },
            self.validation,
            (self.source.id,),
        )
        self.assertIsInstance(objet, ObjectifTherapeutique)
        return objet

    def creer_tache(
        self,
        probleme: ProblemeSuivi,
        objectif: ObjectifTherapeutique,
    ) -> TacheIntersession:
        objet = creer_objet_valide(
            TypeObjetLongitudinal.TACHE_INTERSESSION,
            {
                "cycle": CycleTache.OUVERTE,
                "statut_decision": StatutDecisionTache.CONVENUE,
                "statut_resultat": (
                    StatutResultatTache.RESULTAT_NON_DOCUMENTE
                ),
                "consigne": self.assertion_explicite(
                    "Realiser une observation fictive entre deux seances."
                ),
                "probleme_ids": (probleme.id,),
                "objectif_ids": (objectif.id,),
                "rationale_partage": None,
                "parametres": (),
                "conditions_realisation": (),
                "date_proposition_ou_accord": date(2026, 8, 1),
                "echeance": date(2026, 8, 8),
                "resultat_documente": None,
                "apprentissages": (),
                "effets_indesirables": (),
                "obstacles": (),
                "decision_suite": None,
                "relations": (),
            },
            self.validation,
            (self.source.id,),
        )
        self.assertIsInstance(objet, TacheIntersession)
        return objet

    def creer_element(
        self,
        tache: TacheIntersession,
    ) -> ElementAReprendre:
        objet = creer_objet_valide(
            TypeObjetLongitudinal.ELEMENT_A_REPRENDRE,
            {
                "etat": EtatElementAReprendre.OUVERT,
                "contenu": self.assertion_explicite(
                    "Reprendre un point fictif explicitement differe."
                ),
                "cible": {
                    "type_cible": "tache_intersession",
                    "objet_id": tache.id,
                    "version_objet": tache.version,
                    "source_id": None,
                },
                "raison_report": None,
                "priorite": None,
                "echeance": date(2026, 8, 8),
                "relations": (),
            },
            self.validation,
            (self.source.id,),
        )
        self.assertIsInstance(objet, ElementAReprendre)
        return objet

    def creer_registre_complet(self) -> RegistreLongitudinalV1:
        probleme = self.creer_probleme()
        objectif = self.creer_objectif(probleme)
        tache = self.creer_tache(probleme, objectif)
        element = self.creer_element(tache)
        return RegistreLongitudinalV1(
            dossier_id_pseudonymise="DOSSIER-FICTIF",
            version_registre=1,
            date_coupure=date(2026, 8, 1),
            statut_documentaire=(
                StatutDocumentaireValide.VALIDE_CLINICIEN
            ),
            references_sources=(self.source,),
            problemes_suivis=(probleme,),
            objectifs_therapeutiques=(objectif,),
            taches_intersession=(tache,),
            elements_a_reprendre=(element,),
        )

    def test_creation_valide_des_quatre_objets(self) -> None:
        registre = self.creer_registre_complet()

        self.assertEqual(len(registre.problemes_suivis), 1)
        self.assertEqual(len(registre.objectifs_therapeutiques), 1)
        self.assertEqual(len(registre.taches_intersession), 1)
        self.assertEqual(len(registre.elements_a_reprendre), 1)
        for objet in registre.tous_les_objets():
            self.assertEqual(objet.version, 1)
            self.assertEqual(objet.historique[0].type_revision, TypeRevision.CREATION)

    def test_rejet_des_structures_interdites(self) -> None:
        with self.assertRaises(ValidationError):
            AssertionClinique(
                contenu="",
                statut_epistemique=StatutEpistemique.EXPLICITE,
                source_ids=(self.source.id,),
            )

        with self.assertRaises(ValidationError):
            AssertionClinique(
                contenu="Regroupement fictif.",
                statut_epistemique=StatutEpistemique.SYNTHESE_PRUDENTE,
                source_ids=(self.source.id,),
            )

        with self.assertRaises(ValueError):
            creer_objet_valide(
                TypeObjetLongitudinal.PROBLEME_SUIVI,
                {
                    "id": "prb_" + "0" * 32,
                    "etat": "actif",
                    "libelle": self.assertion_explicite("Contenu fictif."),
                },
                self.validation,
                (self.source.id,),
            )

    def test_serialisation_et_deserialisation_sans_perte(self) -> None:
        registre = self.creer_registre_complet()

        with TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "registre.json"
            enregistrer_registre(registre, chemin)
            recharge = charger_registre(chemin)

        self.assertEqual(recharge, registre)

    def test_identifiant_stable_lors_revision(self) -> None:
        probleme = self.creer_probleme()
        validation_revision = self.creer_validation(
            jour=3,
            motif="Reformulation clinique fictive validee.",
        )

        revise = reviser_objet(
            probleme,
            {
                "libelle": self.assertion_prudente(
                    "Difficulte fictive reformulee sans changer d'identite."
                )
            },
            validation_revision,
            (self.source.id,),
        )

        self.assertEqual(revise.id, probleme.id)
        self.assertEqual(revise.version, 2)
        self.assertEqual(len(revise.historique), 2)
        self.assertEqual(
            revise.historique[-1].modifications[0].champ,
            "libelle",
        )

    def test_identifiant_clinique_non_derive_du_texte(self) -> None:
        premier = self.creer_probleme()
        second = self.creer_probleme()

        self.assertEqual(premier.libelle, second.libelle)
        self.assertNotEqual(premier.id, second.id)

    def test_provenance_deterministe_et_conservee(self) -> None:
        copie = creer_reference_source_v1(
            dossier_id_pseudonymise="DOSSIER-FICTIF",
            document="donnees_cliniques/seance-fictive.json",
            document_sha256=HASH_DOCUMENT,
            date_seance=date(2026, 8, 1),
            categorie_source="faits_rapportes",
            json_pointer="/faits_rapportes/0",
            element_sha256=HASH_ELEMENT,
            relation_support=RelationSupport.DIRECT,
            extraction_schema_version="2.0",
        )
        registre = self.creer_registre_complet()

        self.assertEqual(copie.id, self.source.id)
        self.assertEqual(
            registre.problemes_suivis[0].libelle.source_ids,
            (self.source.id,),
        )

    def test_relation_contradictoire_est_conservee_sans_collision(self) -> None:
        contradictoire = creer_reference_source_v1(
            dossier_id_pseudonymise="DOSSIER-FICTIF",
            document="donnees_cliniques/seance-fictive.json",
            document_sha256=HASH_DOCUMENT,
            date_seance=date(2026, 8, 1),
            categorie_source="faits_rapportes",
            json_pointer="/faits_rapportes/0",
            element_sha256=HASH_ELEMENT,
            relation_support=RelationSupport.CONTRADICTOIRE,
            extraction_schema_version="2.0",
        )
        probleme = creer_objet_valide(
            TypeObjetLongitudinal.PROBLEME_SUIVI,
            {
                "etat": EtatProbleme.ACTIF,
                "libelle": AssertionClinique(
                    contenu="Assertion fictive avec contradiction conservee.",
                    statut_epistemique=StatutEpistemique.SYNTHESE_PRUDENTE,
                    source_ids=(self.source.id, contradictoire.id),
                    periode_couverte=PeriodeCouverte(
                        date_debut=date(2026, 8, 1),
                        date_fin=date(2026, 8, 1),
                    ),
                ),
                "relations": (),
            },
            self.validation,
            (self.source.id, contradictoire.id),
        )
        registre = RegistreLongitudinalV1(
            dossier_id_pseudonymise="DOSSIER-FICTIF",
            version_registre=1,
            date_coupure=date(2026, 8, 1),
            statut_documentaire="valide_clinicien",
            references_sources=(self.source, contradictoire),
            problemes_suivis=(probleme,),
        )

        self.assertNotEqual(self.source.id, contradictoire.id)
        self.assertEqual(
            registre.references_sources[1].relation_support,
            RelationSupport.CONTRADICTOIRE,
        )

    def test_provenance_refuse_fausse_precision_ou_pointeur_invalide(self) -> None:
        donnees = self.source.model_dump()
        donnees["document"] = "../photo/source.json"
        with self.assertRaises(ValidationError):
            ReferenceSourceV1.model_validate(donnees)

        donnees = self.source.model_dump()
        donnees["json_pointer"] = "/emotions/0"
        with self.assertRaises(ValidationError):
            ReferenceSourceV1.model_validate(donnees)

        with self.assertRaises(ValidationError):
            ReferenceSourceV1.model_validate(
                {
                    **self.source.model_dump(),
                    "region_image": [0, 0, 10, 10],
                }
            )

    def test_transition_autorisee_et_reactivation_historisee(self) -> None:
        probleme = self.creer_probleme()
        en_pause = reviser_objet(
            probleme,
            {"etat": EtatProbleme.EN_PAUSE},
            self.creer_validation(
                jour=3,
                motif="Mise en pause fictive documentee.",
            ),
            (self.source.id,),
            TypeRevision.CHANGEMENT_ETAT,
        )
        reactive = reviser_objet(
            en_pause,
            {"etat": EtatProbleme.ACTIF},
            self.creer_validation(
                jour=4,
                motif="Reactivation fictive documentee.",
            ),
            (self.source.id,),
            TypeRevision.REACTIVATION,
        )

        self.assertEqual(reactive.etat, EtatProbleme.ACTIF)
        self.assertEqual(reactive.version, 3)
        self.assertEqual(
            reactive.historique[-1].type_revision,
            TypeRevision.REACTIVATION,
        )

    def test_transition_interdite_refusee(self) -> None:
        probleme = self.creer_probleme()

        with self.assertRaises(ValueError):
            reviser_objet(
                probleme,
                {"etat": EtatProbleme.CANDIDAT},
                self.creer_validation(
                    jour=3,
                    motif="Transition fictive invalide.",
                ),
                (self.source.id,),
                TypeRevision.CHANGEMENT_ETAT,
            )

    def test_remplacement_exige_relation_correspondante(self) -> None:
        probleme = self.creer_probleme()

        with self.assertRaises(ValueError):
            reviser_objet(
                probleme,
                {"etat": EtatProbleme.REMPLACE},
                self.creer_validation(
                    jour=3,
                    motif="Remplacement fictif incomplet.",
                ),
                (self.source.id,),
                TypeRevision.REMPLACEMENT,
            )

    def test_revision_antidatee_refusee(self) -> None:
        probleme = self.creer_probleme()

        with self.assertRaises(ValidationError):
            reviser_objet(
                probleme,
                {"description": self.assertion_explicite("Ajout fictif.")},
                self.creer_validation(
                    jour=1,
                    motif="Revision fictive antidatee.",
                ),
                (self.source.id,),
            )

    def test_tache_non_realisee_exige_une_source_explicite(self) -> None:
        probleme = self.creer_probleme()
        objectif = self.creer_objectif(probleme)
        donnees = {
            "cycle": CycleTache.CLOSE,
            "statut_decision": StatutDecisionTache.CONVENUE,
            "statut_resultat": StatutResultatTache.NON_REALISEE_RAPPORTEE,
            "consigne": self.assertion_explicite("Tache fictive."),
            "probleme_ids": (probleme.id,),
            "objectif_ids": (objectif.id,),
            "date_proposition_ou_accord": date(2026, 8, 1),
            "echeance": None,
            "resultat_documente": None,
            "relations": (),
        }

        with self.assertRaises(ValidationError):
            creer_objet_valide(
                TypeObjetLongitudinal.TACHE_INTERSESSION,
                donnees,
                self.validation,
                (self.source.id,),
            )

    def test_cloture_tache_documentee(self) -> None:
        probleme = self.creer_probleme()
        objectif = self.creer_objectif(probleme)
        tache = self.creer_tache(probleme, objectif)

        close = reviser_objet(
            tache,
            {
                "cycle": CycleTache.CLOSE,
                "statut_resultat": StatutResultatTache.REALISEE,
                "resultat_documente": self.assertion_explicite(
                    "La tache fictive a ete rapportee comme realisee."
                ),
            },
            self.creer_validation(
                jour=3,
                motif="Resultat fictif explicitement documente.",
            ),
            (self.source.id,),
            TypeRevision.CHANGEMENT_ETAT,
        )

        self.assertEqual(close.cycle, CycleTache.CLOSE)
        self.assertEqual(close.statut_resultat, StatutResultatTache.REALISEE)

    def creer_proposition_probleme(self) -> PropositionMiseAJour:
        libelle = self.assertion_prudente(
            "Regroupement fictif propose comme probleme a examiner."
        )
        return PropositionMiseAJour(
            id=generer_identifiant_proposition(),
            type_objet=TypeObjetLongitudinal.PROBLEME_SUIVI,
            operation=TypeOperationProposee.CREATION,
            objet_cible_id=None,
            version_objet_cible=None,
            contenu_propose={
                "etat": "candidat",
                "libelle": libelle.model_dump(mode="json"),
                "description": None,
                "contexte": [],
                "impact": [],
                "priorite": None,
                "objectif_ids": [],
                "tache_ids": [],
                "relations": [],
            },
            differences=(
                {
                    "champ": "creation",
                    "valeur_actuelle": None,
                    "valeur_proposee": "probleme_suivi",
                },
            ),
            justification="Plusieurs donnees fictives pourraient etre regroupees.",
            source_ids=(self.source.id,),
            statuts_epistemiques=(StatutEpistemique.SYNTHESE_PRUDENTE,),
            cree_le=datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc),
            modele="modele-fictif",
            version_prompt="1.0-fictive",
            version_generateur="1.0-fictive",
            prompt_sha256=HASH_PROMPT,
            empreinte_sources_sha256=HASH_SOURCES,
        )

    def test_proposition_structurellement_separee_du_registre(self) -> None:
        proposition = self.creer_proposition_probleme()

        self.assertEqual(
            proposition.statut_action.value,
            "proposition_systeme",
        )
        self.assertEqual(proposition.statut_documentaire, "brouillon_genere")
        with self.assertRaises(ValidationError):
            ProblemeSuivi.model_validate(proposition.model_dump())
        with self.assertRaises(ValidationError):
            RegistreLongitudinalV1.model_validate(
                {
                    "dossier_id_pseudonymise": "DOSSIER-FICTIF",
                    "version_registre": 1,
                    "date_coupure": "2026-08-01",
                    "statut_documentaire": "valide_clinicien",
                    "propositions": [proposition.model_dump(mode="json")],
                }
            )

    def test_serialiser_proposition_ne_la_promeut_pas(self) -> None:
        proposition = self.creer_proposition_probleme()
        fichier = FichierPropositionsLongitudinalesV1(
            dossier_id_pseudonymise="DOSSIER-FICTIF",
            propositions=(proposition,),
        )

        with TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "propositions.json"
            enregistrer_propositions(fichier, chemin)
            recharge = charger_propositions(chemin)

        self.assertEqual(recharge, fichier)
        self.assertEqual(
            recharge.propositions[0].etat_revue,
            EtatRevueProposition.A_REVOIR,
        )

    def test_promotion_exige_une_operation_explicite_et_validation(self) -> None:
        proposition = self.creer_proposition_probleme()
        registre = RegistreLongitudinalV1(
            dossier_id_pseudonymise="DOSSIER-FICTIF",
            version_registre=1,
            date_coupure=date(2026, 8, 1),
            statut_documentaire="valide_clinicien",
            references_sources=(self.source,),
        )

        self.assertEqual(len(registre.problemes_suivis), 0)
        resultat = promouvoir_proposition_creation(
            registre,
            proposition,
            self.validation,
        )

        self.assertEqual(len(resultat.registre.problemes_suivis), 1)
        self.assertEqual(resultat.registre.version_registre, 2)
        self.assertEqual(
            resultat.proposition_revue.etat_revue,
            EtatRevueProposition.ACCEPTEE,
        )
        self.assertEqual(
            resultat.objet_cree.validation_creation,
            self.validation,
        )

    def test_promotion_refuse_source_absente(self) -> None:
        proposition = self.creer_proposition_probleme()
        registre = RegistreLongitudinalV1(
            dossier_id_pseudonymise="DOSSIER-FICTIF",
            version_registre=1,
            date_coupure=date(2026, 8, 1),
            statut_documentaire="valide_clinicien",
        )

        with self.assertRaises(ValueError):
            promouvoir_proposition_creation(
                registre,
                proposition,
                self.validation,
            )

    def test_registre_refuse_version_de_relation_inexistante(self) -> None:
        probleme = self.creer_probleme()
        objectif = self.creer_objectif(probleme)
        relation = RelationObjet(
            type_relation="issu_de",
            type_objet_cible="objectif_therapeutique",
            objet_cible_id=objectif.id,
            version_objet_cible=2,
            date_relation=date(2026, 8, 2),
            source_ids=(self.source.id,),
        )
        probleme_lie = ProblemeSuivi.model_validate(
            {
                **probleme.model_dump(),
                "relations": (relation,),
            }
        )

        with self.assertRaises(ValidationError):
            RegistreLongitudinalV1(
                dossier_id_pseudonymise="DOSSIER-FICTIF",
                version_registre=1,
                date_coupure=date(2026, 8, 1),
                statut_documentaire="valide_clinicien",
                references_sources=(self.source,),
                problemes_suivis=(probleme_lie,),
                objectifs_therapeutiques=(objectif,),
            )

    def test_statut_epistemique_conserve_sans_decision_explicite(self) -> None:
        probleme = creer_objet_valide(
            TypeObjetLongitudinal.PROBLEME_SUIVI,
            {
                "etat": EtatProbleme.ACTIF,
                "libelle": self.assertion_prudente(
                    "Probleme fictif formule comme synthese prudente."
                ),
                "description": None,
                "contexte": (),
                "impact": (),
                "priorite": None,
                "objectif_ids": (),
                "tache_ids": (),
                "relations": (),
            },
            self.validation,
            (self.source.id,),
        )
        revise = reviser_objet(
            probleme,
            {"impact": (self.assertion_explicite("Impact fictif documente."),)},
            self.creer_validation(
                jour=3,
                motif="Ajout d'un impact fictif documente.",
            ),
            (self.source.id,),
        )

        self.assertEqual(
            revise.libelle.statut_epistemique,
            StatutEpistemique.SYNTHESE_PRUDENTE,
        )


if __name__ == "__main__":
    unittest.main()
