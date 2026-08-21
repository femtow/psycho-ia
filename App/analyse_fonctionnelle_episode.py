"""Analyse fonctionnelle synchronique d'un episode clinique fictif.

Cette brique isole une seule occurrence choisie par le clinicien. Elle ne
detecte pas d'episode, ne produit pas de diagnostic et ne promeut aucun objet
dans le registre longitudinal.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Literal
import json
import os
import re
import tempfile

from pydantic import Field, JsonValue, ValidationError, field_validator, model_validator

from catalogue_sources_longitudinales import (
    CatalogueSourcesPatientV1,
    EntreeCatalogueSourceV1,
    construire_catalogue_sources_patient,
)
from modeles_longitudinaux import (
    ModeleStrict,
    ReferenceSourceV1,
    RelationSupport,
    SHA256_RE,
    StatutEpistemique,
    calculer_sha256_json_canonique,
    calculer_sha256_octets,
    creer_reference_source_v1,
)
from resolution_provenance import resoudre_reference_source_v1
from source_clinique_confirmee import (
    ProvenanceJsonCliniqueV1,
    ServiceSourceCliniqueConfirmeeV1,
    charger_provenance_json,
)


SCHEMA_ANALYSE_FONCTIONNELLE = "1.0"
VERSION_GENERATEUR_ANALYSE = "1.6"
VERSION_PROMPT_ANALYSE = "1.5"
MODEL_ANALYSE_FONCTIONNELLE = "gpt-5.6-terra"
REASONING_EFFORT_ANALYSE = "medium"
MAX_OUTPUT_TOKENS_ANALYSE = 5000
STATUT_BROUILLON = "brouillon_clinique_a_examiner"
RAISON_SELECTION_EXPLICITE = "Épisode explicitement choisi par le clinicien."
DOSSIER_DOCUMENTS_GENERES = "Documents_generes"
DOSSIER_ANALYSES = "Analyses_fonctionnelles"

SOURCE_COURTE_RE = re.compile(r"^source_[0-9]{4,}$")
MARQUEUR_INCERTITUDE_RE = re.compile(
    r"\[illisible\]|\[mot incertain[^\]]*\]",
    re.IGNORECASE,
)
MARQUEUR_CONSEQUENCE_EXPLICITE_RE = re.compile(
    r"(?:"
    r"(?:ça|cela|ca|ceci|cette action|ce comportement)\s+(?:m['’]|lui\s+|leur\s+)?a\s+"
    r"(?:(?:immédiatement|immediatement)\s+)?(?:soulag|aid|permis|rassur|provoqu|entraîn|entraine|caus)"
    r"|(?:m['’]|l['’]|lui\s+|leur\s+)a\s+(?:(?:immédiatement|immediatement)\s+)?(?:soulag|aid|permis|rassur|empêch|empech)"
    r"|(?:a\s+)?(?:provoqué|provoque|entraîné|entraine|causé|cause)"
    r"|à cause de|a cause de|grâce à|grace a"
    r"|(?:je|il|elle)\s+(?:me\s+|s['’])?(?:suis|est)\s+senti(?:e)?\s+mieux"
    r")",
    re.IGNORECASE,
)


class ErreurAnalyseFonctionnelle(Exception):
    code: ClassVar[str] = "erreur_analyse_fonctionnelle"

    def __init__(self, message: str, reponse: Any | None = None) -> None:
        super().__init__(message)
        self.reponse = reponse


class SourceEpisodeInadmissible(ErreurAnalyseFonctionnelle):
    code = "source_episode_inadmissible"


class SortieTerraAnalyseInvalide(ErreurAnalyseFonctionnelle):
    code = "sortie_terra_analyse_invalide"


class ValidationAnalyseEchouee(ErreurAnalyseFonctionnelle):
    code = "validation_analyse_echouee"


class NiveauCompletude(str, Enum):
    DESCRIPTIF = "descriptif"
    CHAINE_DOCUMENTEE = "chaine_documentee"
    HYPOTHESE_FONCTIONNELLE = "hypothese_fonctionnelle"


class MomentEpisode(str, Enum):
    AVANT = "avant"
    DEBUT = "debut"
    PENDANT = "pendant"
    FIN = "fin"
    APRES = "apres"
    INCONNU = "inconnu"


class SourceCliniqueAutoriseeV1(ModeleStrict):
    date_seance: date
    transcription: str = Field(min_length=1)
    transcription_sha256: str
    confirmation_id: str = Field(min_length=1)
    json_clinique: str = Field(min_length=1)
    json_sha256: str
    assertions_json_validees_individuellement: Literal[False] = False
    passages_signales: tuple[str, ...] = ()

    @field_validator("transcription_sha256", "json_sha256")
    @classmethod
    def verifier_empreinte(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Empreinte SHA-256 de source invalide.")
        return valeur


class ElementDocumenteV1(ModeleStrict):
    contenu: str = Field(min_length=1)
    moment: MomentEpisode = MomentEpisode.INCONNU
    intensite_ou_frequence: str | None = None
    source_ids: tuple[str, ...] = Field(min_length=1)
    statut_epistemique: Literal[StatutEpistemique.EXPLICITE] = (
        StatutEpistemique.EXPLICITE
    )


class ElementHypotheseV1(ModeleStrict):
    contenu: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    statut_epistemique: Literal[StatutEpistemique.HYPOTHESE_CLINIQUE] = (
        StatutEpistemique.HYPOTHESE_CLINIQUE
    )


class DonneeAExplorerV1(ModeleStrict):
    contenu: str = Field(min_length=1)
    raison: str = Field(min_length=1)
    source_ids: tuple[str, ...] = ()
    statut_epistemique: Literal[StatutEpistemique.INCONNU_A_EXPLORER] = (
        StatutEpistemique.INCONNU_A_EXPLORER
    )


class IncertitudeSourceV1(ModeleStrict):
    passage_exact: str = Field(min_length=1)
    incidence: str = Field(min_length=1)
    confirmation_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("passage_exact")
    @classmethod
    def conserver_marqueur(cls, valeur: str) -> str:
        if MARQUEUR_INCERTITUDE_RE.search(valeur) is None:
            raise ValueError("Une incertitude source doit conserver son marqueur exact.")
        return valeur


class ContradictionDocumenteeV1(ModeleStrict):
    moment_decrit: str = Field(min_length=1)
    formulations: tuple[ElementDocumenteV1, ...] = Field(min_length=2)


class ReponsesEpisodeV1(ModeleStrict):
    comportements: tuple[ElementDocumenteV1, ...] = ()
    evitements_ou_protections_documentes: tuple[ElementDocumenteV1, ...] = ()
    fonctions_evitement_ou_protection_possibles: tuple[ElementHypotheseV1, ...] = ()
    emotions: tuple[ElementDocumenteV1, ...] = ()
    sensations: tuple[ElementDocumenteV1, ...] = ()
    cognitions_images_anticipations: tuple[ElementDocumenteV1, ...] = ()
    reponses_environnement: tuple[ElementDocumenteV1, ...] = ()

    def documentees(self) -> tuple[ElementDocumenteV1, ...]:
        return (
            *self.comportements,
            *self.evitements_ou_protections_documentes,
            *self.emotions,
            *self.sensations,
            *self.cognitions_images_anticipations,
            *self.reponses_environnement,
        )


class EvolutionTemporelleDocumenteeV1(ModeleStrict):
    observations: tuple[ElementDocumenteV1, ...] = Field(min_length=1)
    lien_causal_etabli: Literal[False] = False

    @model_validator(mode="after")
    def verifier_observations(self) -> EvolutionTemporelleDocumenteeV1:
        source_ids = [
            source_id
            for observation in self.observations
            for source_id in observation.source_ids
        ]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError(
                "Une evolution temporelle ne doit pas repeter une source atomique."
            )
        return self


class HypotheseFonctionnelleV1(ModeleStrict):
    reponse_cible: str = Field(min_length=1)
    fonction_supposee: str = Field(min_length=1)
    effet_immediat_pertinent: str = Field(min_length=1)
    cout_ou_effet_differe_pertinent: str | None = None
    donnees_en_faveur: tuple[ElementDocumenteV1, ...] = Field(min_length=1)
    donnees_en_defaveur_ou_limites: tuple[str, ...] = Field(min_length=1)
    hypotheses_alternatives: tuple[str, ...] = Field(min_length=1)
    prediction_ou_question_testable: str = Field(min_length=1)
    statut_epistemique: Literal[StatutEpistemique.HYPOTHESE_CLINIQUE] = (
        StatutEpistemique.HYPOTHESE_CLINIQUE
    )


class ProvenanceAnalyseFonctionnelleV1(ModeleStrict):
    sources_cliniques: tuple[SourceCliniqueAutoriseeV1, ...] = Field(min_length=1)
    references_sources: tuple[ReferenceSourceV1, ...] = Field(min_length=1)
    modele: Literal[MODEL_ANALYSE_FONCTIONNELLE] = MODEL_ANALYSE_FONCTIONNELLE
    version_prompt: Literal[VERSION_PROMPT_ANALYSE] = VERSION_PROMPT_ANALYSE
    version_generateur: Literal[VERSION_GENERATEUR_ANALYSE] = (
        VERSION_GENERATEUR_ANALYSE
    )
    prompt_sha256: str
    empreinte_generation: str
    genere_le: datetime

    @field_validator("prompt_sha256", "empreinte_generation")
    @classmethod
    def verifier_sha(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Empreinte de provenance invalide.")
        return valeur

    @field_validator("genere_le")
    @classmethod
    def verifier_fuseau(cls, valeur: datetime) -> datetime:
        if valeur.tzinfo is None or valeur.utcoffset() is None:
            raise ValueError("La date de generation doit inclure un fuseau horaire.")
        return valeur


class AnalyseFonctionnelleEpisodeV1(ModeleStrict):
    schema_version: Literal[SCHEMA_ANALYSE_FONCTIONNELLE] = (
        SCHEMA_ANALYSE_FONCTIONNELLE
    )
    identifiant_analyse: str
    statut_documentaire: Literal[STATUT_BROUILLON] = STATUT_BROUILLON
    dossier_id_pseudonymise: str = Field(min_length=1)
    libelle_clinique: str = Field(min_length=1)
    description_episode: str = Field(min_length=1)
    raison_de_selection: str = Field(min_length=1)
    date_episode: date | None = None
    niveau_completude: NiveauCompletude
    contexte_et_antecedents: tuple[ElementDocumenteV1, ...] = ()
    reponses: ReponsesEpisodeV1
    evolutions_temporelles_documentees: tuple[
        EvolutionTemporelleDocumenteeV1, ...
    ] = ()
    consequences_immediates: tuple[ElementDocumenteV1, ...] = ()
    consequences_differees: tuple[ElementDocumenteV1, ...] = ()
    hypothese_fonctionnelle: HypotheseFonctionnelleV1 | None = None
    variations_exceptions_ressources: tuple[ElementDocumenteV1, ...] = ()
    contradictions: tuple[ContradictionDocumenteeV1, ...] = ()
    incertitudes_source: tuple[IncertitudeSourceV1, ...] = ()
    donnees_a_explorer: tuple[DonneeAExplorerV1, ...] = ()
    formulation_partagee_documentee: ElementDocumenteV1 | None = None
    decision_clinique_documentee: ElementDocumenteV1 | None = None
    provenance: ProvenanceAnalyseFonctionnelleV1

    @field_validator("identifiant_analyse")
    @classmethod
    def verifier_identifiant(cls, valeur: str) -> str:
        if not re.fullmatch(r"^afe_[0-9a-f]{24}$", valeur):
            raise ValueError("Identifiant d'analyse fonctionnelle invalide.")
        return valeur

    @model_validator(mode="after")
    def verifier_completude(self) -> AnalyseFonctionnelleEpisodeV1:
        if not self.reponses.documentees():
            raise ValueError("Au moins une reponse documentee est obligatoire.")
        attendu = determiner_niveau_completude(
            self.consequences_immediates,
            self.hypothese_fonctionnelle,
        )
        if self.niveau_completude is not attendu:
            raise ValueError("Le niveau de completude n'est pas deterministe.")
        items_canoniques = (
            *self.contexte_et_antecedents,
            *self.reponses.documentees(),
            *self.consequences_immediates,
            *self.consequences_differees,
            *self.variations_exceptions_ressources,
            *(
                (self.formulation_partagee_documentee,)
                if self.formulation_partagee_documentee is not None
                else ()
            ),
            *(
                (self.decision_clinique_documentee,)
                if self.decision_clinique_documentee is not None
                else ()
            ),
        )
        occurrences = Counter(
            source_id
            for item in items_canoniques
            for source_id in item.source_ids
        )
        if any(nombre > 1 for nombre in occurrences.values()):
            raise ValueError(
                "Une source atomique documentee ne doit pas etre dupliquee entre rubriques."
            )
        return self


class ElementTerraV1(ModeleStrict):
    contenu: str = Field(min_length=1)
    moment: MomentEpisode = MomentEpisode.INCONNU
    intensite_ou_frequence: str | None = None
    source_ids: tuple[str, ...] = Field(min_length=1, max_length=1)

    @field_validator("source_ids")
    @classmethod
    def verifier_sources_courtes(cls, valeurs: tuple[str, ...]) -> tuple[str, ...]:
        if any(SOURCE_COURTE_RE.fullmatch(valeur) is None for valeur in valeurs):
            raise ValueError("Identifiant court de source invalide.")
        if len(set(valeurs)) != len(valeurs):
            raise ValueError("Une source courte ne doit pas etre repetee.")
        return valeurs


class HypotheseTerraV1(ModeleStrict):
    reponse_cible: str = Field(min_length=1)
    fonction_supposee: str = Field(min_length=1)
    effet_immediat_pertinent: str = Field(min_length=1)
    cout_ou_effet_differe_pertinent: str | None = None
    donnees_en_faveur: tuple[ElementTerraV1, ...] = Field(min_length=1)
    donnees_en_defaveur_ou_limites: tuple[str, ...] = Field(min_length=1)
    hypotheses_alternatives: tuple[str, ...] = Field(min_length=1)
    prediction_ou_question_testable: str = Field(min_length=1)


class ContradictionTerraV1(ModeleStrict):
    moment_decrit: str = Field(min_length=1)
    formulations: tuple[ElementTerraV1, ...] = Field(min_length=2)


class EvolutionTemporelleTerraV1(ModeleStrict):
    observations: tuple[ElementTerraV1, ...] = Field(min_length=1)


class IncertitudeTerraV1(ModeleStrict):
    passage_exact: str = Field(min_length=1)
    incidence: str = Field(min_length=1)


class DonneeAExplorerTerraV1(ModeleStrict):
    contenu: str = Field(min_length=1)
    raison: str = Field(min_length=1)
    source_ids: tuple[str, ...] = ()

    @field_validator("source_ids")
    @classmethod
    def verifier_sources_courtes(cls, valeurs: tuple[str, ...]) -> tuple[str, ...]:
        if any(SOURCE_COURTE_RE.fullmatch(valeur) is None for valeur in valeurs):
            raise ValueError("Identifiant court de source invalide.")
        return valeurs


class SortieTerraAnalyseFonctionnelleV1(ModeleStrict):
    libelle_clinique: str = Field(min_length=1)
    description_episode: str = Field(min_length=1)
    raison_de_selection: Literal[RAISON_SELECTION_EXPLICITE] = (
        RAISON_SELECTION_EXPLICITE
    )
    date_episode: date | None = None
    contexte_et_antecedents: tuple[ElementTerraV1, ...] = ()
    comportements: tuple[ElementTerraV1, ...] = ()
    evitements_ou_protections_documentes: tuple[ElementTerraV1, ...] = ()
    fonctions_evitement_ou_protection_possibles: tuple[ElementTerraV1, ...] = ()
    emotions: tuple[ElementTerraV1, ...] = ()
    sensations: tuple[ElementTerraV1, ...] = ()
    cognitions_images_anticipations: tuple[ElementTerraV1, ...] = ()
    reponses_environnement: tuple[ElementTerraV1, ...] = ()
    evolutions_temporelles_documentees: tuple[
        EvolutionTemporelleTerraV1, ...
    ] = ()
    consequences_immediates: tuple[ElementTerraV1, ...] = ()
    consequences_differees: tuple[ElementTerraV1, ...] = ()
    hypothese_fonctionnelle: HypotheseTerraV1 | None = None
    variations_exceptions_ressources: tuple[ElementTerraV1, ...] = ()
    contradictions: tuple[ContradictionTerraV1, ...] = ()
    incertitudes_source: tuple[IncertitudeTerraV1, ...] = ()
    donnees_a_explorer: tuple[DonneeAExplorerTerraV1, ...] = ()
    formulation_partagee_documentee: ElementTerraV1 | None = None
    decision_clinique_documentee: ElementTerraV1 | None = None


class ContexteAnalyseFonctionnelleV1(ModeleStrict):
    dossier_patient: Path
    dossier_id_pseudonymise: str = Field(min_length=1)
    episode_decrit_par_clinicien: str = Field(min_length=1)
    source_principale: SourceCliniqueAutoriseeV1
    sources_complementaires: tuple[SourceCliniqueAutoriseeV1, ...] = ()
    transcriptions: tuple[str, ...] = Field(min_length=1)
    catalogue: CatalogueSourcesPatientV1
    empreinte_generation: str

    @field_validator("empreinte_generation")
    @classmethod
    def verifier_empreinte(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Empreinte de generation invalide.")
        return valeur


PROMPT_SYSTEME_ANALYSE = """\
Tu produis un unique brouillon d'analyse fonctionnelle synchronique d'un episode clinique fictif explicitement selectionne par un clinicien.

REGLES ABSOLUES :
- N'analyse que l'episode decrit par le clinicien. Ne detecte, ne classe et ne fusionne aucun autre episode.
- Recopie exactement la description d'episode fournie dans description_episode et utilise exactement la raison de selection imposee par le schema.
- Les transcriptions confirmees donnent le contexte narratif. Les JSON V2 sont des extractions machine non validees assertion par assertion : chaque item doit donc rester un element documente a examiner, jamais une verite clinique certifiee.
- Utilise uniquement les source_id fournis. N'invente ni fait, ni lien temporel, ni sensation, ni emotion, ni evitement, ni consequence.
- Chaque ElementTerraV1 doit citer exactement un seul source_id atomique. Pour mobiliser plusieurs faits, produis plusieurs elements distincts ; ne regroupe jamais leurs sources dans un meme item.
- Ne reutilise jamais le meme source_id dans deux rubriques documentaires. La seule exception est evolutions_temporelles_documentees, qui est une vue derivee et peut referencer des elements deja classes dans les reponses ou les consequences.
- contexte_et_antecedents est facultatif et accepte uniquement un fait_rapporte appartenant explicitement a l'episode. Ne le remplis jamais avec un comportement, une emotion ou une cognition pour satisfaire artificiellement le schema.
- Une evolution temporelle documentee ordonne des faits explicitement dates ou situes dans l'episode. Renseigne evolutions_temporelles_documentees avec les source_id atomiques utiles, dans l'ordre temporel, sans reformuler ni expliquer leur relation.
- Une emotion observee plus tard dans l'episode reste une emotion. Elle peut participer a une evolution temporelle, mais ne devient pas une consequence du seul fait qu'elle survient ensuite.
- Reserve consequences_immediates et consequences_differees aux effets explicitement attribues dans la source a un comportement ou a un evenement. Une simple succession temporelle n'est pas une consequence.
- POST HOC n'implique jamais PROPTER HOC : n'affirme aucun effet, renforcement, maintien, habituation, apprentissage ou fonction a partir de la seule chronologie.
- Une action n'est un evitement/protection documente que si cette fonction est explicite. Sinon, place la fonction possible dans le champ d'hypothese correspondant.
- reponses_environnement accepte uniquement une reaction documentee d'une personne ou de l'environnement pendant l'episode. N'y place jamais une intervention clinique, une discussion de seance ou une tache interseance.
- Une hypothese fonctionnelle est facultative. Si elle existe, elle doit avoir une consequence pertinente, une donnee en faveur, une limite, une alternative et une prediction ou question testable.
- Ne produis aucun diagnostic, diagnostic differentiel, protocole, plan de traitement, prescription, conceptualisation globale, score de confiance ou recommandation d'intervention.
- Une consequence differee ne peut provenir que d'une source complementaire explicitement fournie ou d'un passage explicite de la source principale.
- Ne transforme jamais une non-mention en absence, resolution, succes ou echec.
- Ne reconstruis jamais [illisible] ou [mot incertain : ...]. Copie le passage exact dans incertitudes_source et exclue-le des faits s'il est central.
- Si passages_signales est vide pour toutes les sources, incertitudes_source doit etre vide. Une lacune clinique appartient a donnees_a_explorer, jamais a incertitudes_source.
- Deux intensites a deux moments ou episodes differents ne sont pas une contradiction. Une contradiction exige deux formulations incompatibles portant sur le meme moment decrit.
- Une suggestion d'intervention ne constitue jamais une decision clinique. Renseigne decision_clinique_documentee uniquement si une decision ou un accord est explicitement documente.
- Renseigne formulation_partagee_documentee uniquement si la comprehension partagee est explicite.
- Laisse les champs vides quand les donnees manquent. La fidelite prime sur la completude.
- Vise un contenu clinique qui donnera un rendu bref, environ 250 a 500 mots quand les donnees le permettent.
"""


def determiner_niveau_completude(
    consequences_immediates: tuple[ElementDocumenteV1, ...],
    hypothese: HypotheseFonctionnelleV1 | None,
) -> NiveauCompletude:
    if hypothese is not None:
        if not consequences_immediates:
            raise ValidationAnalyseEchouee(
                "Une hypothese fonctionnelle exige une consequence immediate."
            )
        return NiveauCompletude.HYPOTHESE_FONCTIONNELLE
    if consequences_immediates:
        return NiveauCompletude.CHAINE_DOCUMENTEE
    return NiveauCompletude.DESCRIPTIF


def preparer_contexte_analyse(
    dossier_patient: Path,
    nom_transcription_principale: str,
    episode_decrit_par_clinicien: str,
    noms_transcriptions_complementaires: tuple[str, ...] = (),
) -> ContexteAnalyseFonctionnelleV1:
    """Verifie les seules sources choisies, sans appel API et sans ecriture."""

    racine = dossier_patient.resolve(strict=True)
    dossier_id = racine.name
    if not episode_decrit_par_clinicien.strip():
        raise SourceEpisodeInadmissible("La description de l'episode est obligatoire.")
    noms = (nom_transcription_principale, *noms_transcriptions_complementaires)
    if len(set(noms)) != len(noms):
        raise SourceEpisodeInadmissible("Une transcription ne peut etre selectionnee deux fois.")

    sources = []
    textes = []
    documents_autorises = set()
    for nom in noms:
        source, texte = _charger_source_confirmee(racine, dossier_id, nom)
        sources.append(source)
        textes.append(texte)
        documents_autorises.add(source.json_clinique)

    catalogue_complet = construire_catalogue_sources_patient(racine, dossier_id)
    entrees = tuple(
        entree
        for entree in catalogue_complet.entrees
        if entree.reference.document in documents_autorises
    )
    if not entrees:
        raise SourceEpisodeInadmissible("Les JSON selectionnes ne contiennent aucune source atomique.")
    catalogue = CatalogueSourcesPatientV1(
        dossier_id_pseudonymise=dossier_id,
        date_coupure=max(source.date_seance for source in sources),
        entrees=entrees,
        empreinte_sources_sha256=calculer_sha256_json_canonique(
            [entree.reference.model_dump(mode="json") for entree in entrees]
        ),
    )
    empreinte = _calculer_empreinte_generation(
        dossier_id,
        episode_decrit_par_clinicien,
        tuple(sources),
        catalogue,
    )
    return ContexteAnalyseFonctionnelleV1(
        dossier_patient=racine,
        dossier_id_pseudonymise=dossier_id,
        episode_decrit_par_clinicien=episode_decrit_par_clinicien,
        source_principale=sources[0],
        sources_complementaires=tuple(sources[1:]),
        transcriptions=tuple(textes),
        catalogue=catalogue,
        empreinte_generation=empreinte,
    )


def _charger_source_confirmee(
    racine: Path,
    dossier_id: str,
    nom_transcription: str,
) -> tuple[SourceCliniqueAutoriseeV1, str]:
    transcription = _trouver_transcription(racine, nom_transcription)
    try:
        date_seance = date.fromisoformat(transcription.stem[:10])
    except ValueError as erreur:
        raise SourceEpisodeInadmissible("La transcription n'a pas de date ISO valide.") from erreur
    service = ServiceSourceCliniqueConfirmeeV1(
        racine,
        transcription,
        date_seance,
        dossier_id,
    )
    etat = service.verifier_autorite()
    if not etat.est_confirmee or not etat.json_clinique_lie or etat.confirmation_id is None:
        raise SourceEpisodeInadmissible(
            f"La source {nom_transcription} n'est pas confirmee et liee a son JSON courant."
        )
    provenance = charger_provenance_json(service.chemin_provenance_json)
    _verifier_provenance_courante(racine, provenance, etat.confirmation_id)
    return (
        SourceCliniqueAutoriseeV1(
            date_seance=date_seance,
            transcription=provenance.transcription,
            transcription_sha256=provenance.transcription_sha256,
            confirmation_id=etat.confirmation_id,
            json_clinique=provenance.json_clinique,
            json_sha256=provenance.json_sha256,
            assertions_json_validees_individuellement=(
                provenance.assertions_json_validees_individuellement
            ),
            passages_signales=etat.passages_signales,
        ),
        service.lire_transcription(),
    )


def _verifier_provenance_courante(
    racine: Path,
    provenance: ProvenanceJsonCliniqueV1,
    confirmation_id: str,
) -> None:
    transcription = racine / Path(provenance.transcription)
    json_clinique = racine / Path(provenance.json_clinique)
    if provenance.confirmation_id != confirmation_id:
        raise SourceEpisodeInadmissible("Le JSON ne pointe pas vers la confirmation courante.")
    if calculer_sha256_octets(transcription.read_bytes()) != provenance.transcription_sha256:
        raise SourceEpisodeInadmissible("L'empreinte de transcription n'est plus courante.")
    if calculer_sha256_octets(json_clinique.read_bytes()) != provenance.json_sha256:
        raise SourceEpisodeInadmissible("L'empreinte du JSON n'est plus courante.")


def _trouver_transcription(racine: Path, nom: str) -> Path:
    if Path(nom).name != nom:
        raise SourceEpisodeInadmissible("Le nom de transcription ne doit pas contenir de chemin.")
    for dossier in ("Transcriptions", "transcriptions"):
        chemin = racine / dossier / nom
        if chemin.is_file():
            return chemin
    raise SourceEpisodeInadmissible(f"Transcription introuvable : {nom}")


def _calculer_empreinte_generation(
    dossier_id: str,
    episode: str,
    sources: tuple[SourceCliniqueAutoriseeV1, ...],
    catalogue: CatalogueSourcesPatientV1,
) -> str:
    return calculer_sha256_json_canonique(
        {
            "schema": SCHEMA_ANALYSE_FONCTIONNELLE,
            "generateur": VERSION_GENERATEUR_ANALYSE,
            "prompt": VERSION_PROMPT_ANALYSE,
            "prompt_sha256": calculer_sha256_json_canonique(PROMPT_SYSTEME_ANALYSE),
            "modele": MODEL_ANALYSE_FONCTIONNELLE,
            "dossier_id": dossier_id,
            "episode_decrit_par_clinicien": episode,
            "sources": [source.model_dump(mode="json") for source in sources],
            "catalogue": catalogue.empreinte_sources_sha256,
        }
    )


def construire_prompt_utilisateur(contexte: ContexteAnalyseFonctionnelleV1) -> str:
    sources = []
    autorisees = (contexte.source_principale, *contexte.sources_complementaires)
    for position, (source, texte) in enumerate(zip(autorisees, contexte.transcriptions)):
        sources.append(
            {
                "role": "principale" if position == 0 else "complementaire_explicitement_selectionnee",
                "date_seance": source.date_seance.isoformat(),
                "confirmation_id": source.confirmation_id,
                "transcription_confirmee": texte,
                "passages_signales": list(source.passages_signales),
                "json_assertions_validees_individuellement": False,
            }
        )
    charge = {
        "episode_explicitement_selectionne_par_le_clinicien": (
            contexte.episode_decrit_par_clinicien
        ),
        "sources_cliniques": sources,
        "catalogue_json_v2_machine": contexte.catalogue.vue_terra(),
    }
    return json.dumps(charge, ensure_ascii=False, sort_keys=True, indent=2)


def generer_analyse_fonctionnelle(
    client: Any,
    contexte: ContexteAnalyseFonctionnelleV1,
    genere_le: datetime | None = None,
) -> tuple[AnalyseFonctionnelleEpisodeV1, Any]:
    """Appelle Terra une fois puis applique les controles post-generation."""

    reponse = client.responses.parse(
        model=MODEL_ANALYSE_FONCTIONNELLE,
        reasoning={"effort": REASONING_EFFORT_ANALYSE},
        store=False,
        max_output_tokens=MAX_OUTPUT_TOKENS_ANALYSE,
        input=[
            {"role": "system", "content": PROMPT_SYSTEME_ANALYSE},
            {"role": "user", "content": construire_prompt_utilisateur(contexte)},
        ],
        text_format=SortieTerraAnalyseFonctionnelleV1,
    )
    if getattr(reponse, "status", None) == "incomplete":
        raise SortieTerraAnalyseInvalide("Reponse Terra incomplete.", reponse)
    sortie = getattr(reponse, "output_parsed", None)
    if sortie is None:
        raise SortieTerraAnalyseInvalide("Terra n'a pas retourne de sortie structuree.", reponse)
    try:
        analyse = construire_analyse_depuis_sortie(
            SortieTerraAnalyseFonctionnelleV1.model_validate(sortie),
            contexte,
            genere_le=genere_le,
        )
    except ErreurAnalyseFonctionnelle as erreur:
        erreur.reponse = reponse
        raise
    except Exception as erreur:
        raise ValidationAnalyseEchouee(
            "La validation deterministe post-Terra a echoue.", reponse
        ) from erreur
    return analyse, reponse


def construire_analyse_depuis_sortie(
    sortie: SortieTerraAnalyseFonctionnelleV1,
    contexte: ContexteAnalyseFonctionnelleV1,
    genere_le: datetime | None = None,
) -> AnalyseFonctionnelleEpisodeV1:
    if sortie.description_episode != contexte.episode_decrit_par_clinicien:
        raise ValidationAnalyseEchouee(
            "La description de l'episode doit rester exactement celle du clinicien."
        )
    index = {entree.source_id: entree for entree in contexte.catalogue.entrees}
    principale = contexte.source_principale.json_clinique
    complementaires = {
        source.json_clinique for source in contexte.sources_complementaires
    }
    references: dict[str, ReferenceSourceV1] = {}

    def documents(
        items: tuple[ElementTerraV1, ...],
        categories: set[str],
        *,
        complement_autorise: bool = False,
        contexte_champ: str,
        relation_support: RelationSupport = RelationSupport.DIRECT,
    ) -> tuple[ElementDocumenteV1, ...]:
        resultat = []
        for item in items:
            if len(item.source_ids) != 1:
                raise ValidationAnalyseEchouee(
                    f"Un element documente de {contexte_champ} doit citer une seule source atomique."
                )
            entrees = _resoudre_items(
                item,
                index,
                contexte,
                categories,
                principale,
                complementaires if complement_autorise else set(),
                contexte_champ,
            )
            references_items = tuple(
                _reference_avec_relation(entree.reference, relation_support)
                for entree in entrees
            )
            for reference in references_items:
                references[reference.id] = reference
            resultat.append(
                ElementDocumenteV1(
                    contenu=_contenu_clinique_source(entrees[0]),
                    moment=_moment_documente_source(entrees[0], item.moment),
                    intensite_ou_frequence=_intensite_source(entrees[0]),
                    source_ids=tuple(reference.id for reference in references_items),
                )
            )
        return tuple(resultat)

    contexte_items = documents(
        sortie.contexte_et_antecedents,
        {"faits_rapportes"},
        contexte_champ="contexte_et_antecedents",
    )
    comportements = documents(
        sortie.comportements,
        {"comportements"},
        contexte_champ="comportements",
    )
    evitements = documents(
        sortie.evitements_ou_protections_documentes,
        {"evitements"},
        contexte_champ="evitements_documentes",
    )
    emotions = documents(
        sortie.emotions,
        {"emotions"},
        contexte_champ="emotions",
    )
    sensations = documents(
        sortie.sensations,
        {"faits_rapportes"},
        contexte_champ="sensations",
    )
    cognitions = documents(
        sortie.cognitions_images_anticipations,
        {"cognitions"},
        contexte_champ="cognitions",
    )
    environnement_candidats = tuple(
        item
        for item in sortie.reponses_environnement
        if (
            (entree := index.get(item.source_ids[0])) is None
            or entree.categorie not in {"interventions", "taches_interseances"}
        )
    )
    environnement = documents(
        environnement_candidats,
        {"faits_rapportes"},
        contexte_champ="reponses_environnement",
    )
    observations_evolutions = []
    for evolution in sortie.evolutions_temporelles_documentees:
        observations = documents(
            evolution.observations,
            {"faits_rapportes", "emotions", "cognitions", "comportements", "evitements"},
            complement_autorise=True,
            contexte_champ="evolutions_temporelles_documentees",
        )
        observations_evolutions.append(observations)
    if observations_evolutions:
        sources_deja_reprises = {
            source_id
            for observations in observations_evolutions
            for observation in observations
            for source_id in observation.source_ids
        }
        reponses_temporelles = (
            *comportements,
            *evitements,
            *emotions,
            *sensations,
            *cognitions,
            *environnement,
        )
        manquantes = tuple(
            reponse
            for reponse in reponses_temporelles
            if reponse.moment is not MomentEpisode.INCONNU
            and not sources_deja_reprises.intersection(reponse.source_ids)
        )
        observations_evolutions[0] = (
            *manquantes,
            *observations_evolutions[0],
        )
    evolutions = tuple(
        EvolutionTemporelleDocumenteeV1(
            observations=_ordonner_observations_temporelles(observations),
        )
        for observations in observations_evolutions
    )
    immediates = documents(
        sortie.consequences_immediates,
        {"faits_rapportes", "cognitions", "comportements"},
        contexte_champ="consequences_immediates",
    )
    differees = documents(
        sortie.consequences_differees,
        {"faits_rapportes", "emotions", "cognitions", "comportements", "evitements"},
        complement_autorise=True,
        contexte_champ="consequences_differees",
    )
    _verifier_consequences_explicitement_attribuees(
        immediates,
        index,
        "immediate",
    )
    _verifier_consequences_explicitement_attribuees(
        differees,
        index,
        "differee",
    )
    variations = documents(
        sortie.variations_exceptions_ressources,
        {"faits_rapportes", "emotions", "cognitions", "comportements", "evitements"},
        complement_autorise=True,
        contexte_champ="variations",
    )

    hypotheses_protection = []
    for item in sortie.fonctions_evitement_ou_protection_possibles:
        entrees = _resoudre_items(
            item,
            index,
            contexte,
            {"comportements", "evitements", "faits_rapportes"},
            principale,
            set(),
            "fonction_possible",
        )
        for entree in entrees:
            references[entree.reference.id] = entree.reference
        hypotheses_protection.append(
            ElementHypotheseV1(
                contenu=item.contenu,
                source_ids=tuple(entree.reference.id for entree in entrees),
            )
        )

    hypothese = None
    if sortie.hypothese_fonctionnelle is not None:
        preuves = documents(
            sortie.hypothese_fonctionnelle.donnees_en_faveur,
            {"faits_rapportes", "emotions", "cognitions", "comportements", "evitements"},
            complement_autorise=True,
            contexte_champ="donnees_en_faveur",
        )
        hypothese = HypotheseFonctionnelleV1(
            reponse_cible=sortie.hypothese_fonctionnelle.reponse_cible,
            fonction_supposee=sortie.hypothese_fonctionnelle.fonction_supposee,
            effet_immediat_pertinent=(
                sortie.hypothese_fonctionnelle.effet_immediat_pertinent
            ),
            cout_ou_effet_differe_pertinent=(
                sortie.hypothese_fonctionnelle.cout_ou_effet_differe_pertinent
            ),
            donnees_en_faveur=preuves,
            donnees_en_defaveur_ou_limites=(
                sortie.hypothese_fonctionnelle.donnees_en_defaveur_ou_limites
            ),
            hypotheses_alternatives=(
                sortie.hypothese_fonctionnelle.hypotheses_alternatives
            ),
            prediction_ou_question_testable=(
                sortie.hypothese_fonctionnelle.prediction_ou_question_testable
            ),
        )

    contradictions = []
    for contradiction in sortie.contradictions:
        formulations = documents(
            contradiction.formulations,
            {"faits_rapportes", "emotions", "cognitions", "comportements", "evitements"},
            complement_autorise=True,
            contexte_champ="contradiction",
            relation_support=RelationSupport.CONTRADICTOIRE,
        )
        _verifier_contradiction(
            contradiction.moment_decrit,
            formulations,
            references,
        )
        contradictions.append(
            ContradictionDocumenteeV1(
                moment_decrit=contradiction.moment_decrit,
                formulations=formulations,
            )
        )

    incertitudes = _construire_incertitudes(sortie, contexte)
    donnees_a_explorer = []
    for donnee in sortie.donnees_a_explorer:
        source_ids = []
        if donnee.source_ids:
            item = ElementTerraV1(
                contenu=donnee.contenu,
                source_ids=donnee.source_ids,
            )
            entrees = _resoudre_items(
                item,
                index,
                contexte,
                {"faits_rapportes", "emotions", "cognitions", "comportements", "evitements", "elements_incertains"},
                principale,
                complementaires,
                "donnees_a_explorer",
            )
            for entree in entrees:
                references[entree.reference.id] = entree.reference
            source_ids = [entree.reference.id for entree in entrees]
        donnees_a_explorer.append(
            DonneeAExplorerV1(
                contenu=donnee.contenu,
                raison=donnee.raison,
                source_ids=tuple(source_ids),
            )
        )
    partagee = None
    if sortie.formulation_partagee_documentee is not None:
        partagee = documents(
            (sortie.formulation_partagee_documentee,),
            {"faits_rapportes", "cognitions", "interventions"},
            contexte_champ="formulation_partagee",
        )[0]
        _exiger_marqueur_explicite(
            _texte_sources_referencees(partagee.source_ids, index),
            ("accord", "convenu", "retenu ensemble", "compréhension partagée", "comprehension partagee"),
            "La comprehension partagee n'est pas explicitement documentee.",
        )
    decision = None
    if sortie.decision_clinique_documentee is not None:
        decision = documents(
            (sortie.decision_clinique_documentee,),
            {"faits_rapportes", "interventions", "taches_interseances"},
            contexte_champ="decision_clinique",
        )[0]
        _exiger_marqueur_explicite(
            _texte_sources_referencees(decision.source_ids, index),
            ("décidé", "decide", "convenu", "accord", "retenu"),
            "Une suggestion ou une tache ne suffit pas a documenter une decision.",
        )

    _interdire_contenu_hors_perimetre(sortie)
    if not references:
        raise ValidationAnalyseEchouee("Aucune provenance atomique n'a ete conservee.")
    instant = genere_le or datetime.now(timezone.utc)
    provenance = ProvenanceAnalyseFonctionnelleV1(
        sources_cliniques=(
            contexte.source_principale,
            *contexte.sources_complementaires,
        ),
        references_sources=tuple(
            references[identifiant] for identifiant in sorted(references)
        ),
        prompt_sha256=calculer_sha256_json_canonique(PROMPT_SYSTEME_ANALYSE),
        empreinte_generation=contexte.empreinte_generation,
        genere_le=instant,
    )
    reponses = ReponsesEpisodeV1(
        comportements=comportements,
        evitements_ou_protections_documentes=evitements,
        fonctions_evitement_ou_protection_possibles=tuple(hypotheses_protection),
        emotions=emotions,
        sensations=sensations,
        cognitions_images_anticipations=cognitions,
        reponses_environnement=environnement,
    )
    try:
        return AnalyseFonctionnelleEpisodeV1(
            identifiant_analyse=f"afe_{contexte.empreinte_generation[:24]}",
            dossier_id_pseudonymise=contexte.dossier_id_pseudonymise,
            libelle_clinique=sortie.libelle_clinique,
            description_episode=sortie.description_episode,
            raison_de_selection=RAISON_SELECTION_EXPLICITE,
            date_episode=sortie.date_episode,
            niveau_completude=determiner_niveau_completude(immediates, hypothese),
            contexte_et_antecedents=contexte_items,
            reponses=reponses,
            evolutions_temporelles_documentees=evolutions,
            consequences_immediates=immediates,
            consequences_differees=differees,
            hypothese_fonctionnelle=hypothese,
            variations_exceptions_ressources=variations,
            contradictions=tuple(contradictions),
            incertitudes_source=incertitudes,
            donnees_a_explorer=tuple(donnees_a_explorer),
            formulation_partagee_documentee=partagee,
            decision_clinique_documentee=decision,
            provenance=provenance,
        )
    except ValidationError as erreur:
        message = erreur.errors()[0].get("ctx", {}).get("error")
        raise ValidationAnalyseEchouee(
            str(message) if message else "La validation finale de l'analyse a echoue."
        ) from erreur


def _resoudre_items(
    item: ElementTerraV1,
    index: dict[str, EntreeCatalogueSourceV1],
    contexte: ContexteAnalyseFonctionnelleV1,
    categories: set[str],
    document_principal: str,
    documents_complementaires: set[str],
    nom_champ: str,
) -> tuple[EntreeCatalogueSourceV1, ...]:
    resultat = []
    documents_admis = {document_principal, *documents_complementaires}
    for source_id in item.source_ids:
        entree = index.get(source_id)
        if entree is None:
            raise ValidationAnalyseEchouee(f"Source inconnue dans {nom_champ} : {source_id}")
        if entree.categorie not in categories:
            raise ValidationAnalyseEchouee(
                f"Categorie {entree.categorie} interdite dans {nom_champ}."
            )
        if entree.reference.document not in documents_admis:
            raise ValidationAnalyseEchouee(
                f"Une source non selectionnee est utilisee dans {nom_champ}."
            )
        if _contient_marqueur(entree.contenu):
            raise ValidationAnalyseEchouee(
                "Un passage OCR incertain ne peut pas devenir un fait ou une hypothese."
            )
        resoudre_reference_source_v1(
            entree.reference,
            contexte.dossier_patient,
            contexte.dossier_id_pseudonymise,
        )
        resultat.append(entree)
    return tuple(resultat)


def _contient_marqueur(valeur: JsonValue) -> bool:
    return MARQUEUR_INCERTITUDE_RE.search(
        json.dumps(valeur, ensure_ascii=False)
    ) is not None


def _reference_avec_relation(
    reference: ReferenceSourceV1,
    relation_support: RelationSupport,
) -> ReferenceSourceV1:
    if reference.relation_support is relation_support:
        return reference
    return creer_reference_source_v1(
        dossier_id_pseudonymise=reference.dossier_id_pseudonymise,
        document=reference.document,
        document_sha256=reference.document_sha256,
        date_seance=reference.date_seance,
        categorie_source=reference.categorie_source,
        json_pointer=reference.json_pointer,
        element_sha256=reference.element_sha256,
        relation_support=relation_support,
        extraction_schema_version=reference.extraction_schema_version,
    )


def _contenu_clinique_source(entree: EntreeCatalogueSourceV1) -> str:
    if isinstance(entree.contenu, str):
        return entree.contenu
    if isinstance(entree.contenu, dict):
        contenu = entree.contenu.get("contenu")
        if isinstance(contenu, str) and contenu.strip():
            contexte = entree.contenu.get("contexte")
            if (
                entree.categorie == "evitements"
                and isinstance(contexte, str)
                and contexte.strip()
                and contexte.casefold() not in contenu.casefold()
            ):
                return f"{contenu.rstrip('.')} — {contexte.strip()}"
            return contenu
    raise ValidationAnalyseEchouee(
        "L'element JSON ne contient pas de formulation clinique exploitable."
    )


def _intensite_source(entree: EntreeCatalogueSourceV1) -> str | None:
    if isinstance(entree.contenu, dict):
        intensite = entree.contenu.get("intensite")
        if isinstance(intensite, str) and intensite.strip():
            return intensite
    return None


def _moment_documente_source(
    entree: EntreeCatalogueSourceV1,
    moment_propose: MomentEpisode,
) -> MomentEpisode:
    fragments = []
    if isinstance(entree.contenu, str):
        fragments.append(entree.contenu)
    elif isinstance(entree.contenu, dict):
        fragments.extend(
            valeur
            for cle in ("contenu", "contexte")
            if isinstance((valeur := entree.contenu.get(cle)), str)
        )
    texte = " ".join(fragments).casefold()
    if "à l'arrivée" in texte or "a l'arrivee" in texte:
        return MomentEpisode.FIN
    if "au départ" in texte or "au depart" in texte:
        return MomentEpisode.DEBUT
    if "après" in texte or "apres" in texte:
        return MomentEpisode.APRES
    if "avant" in texte:
        return MomentEpisode.AVANT
    if "pendant" in texte or "lors " in texte:
        return MomentEpisode.PENDANT
    return moment_propose


def _ordonner_observations_temporelles(
    observations: tuple[ElementDocumenteV1, ...],
) -> tuple[ElementDocumenteV1, ...]:
    ordre = {
        MomentEpisode.AVANT: 0,
        MomentEpisode.DEBUT: 1,
        MomentEpisode.PENDANT: 2,
        MomentEpisode.FIN: 3,
        MomentEpisode.APRES: 4,
        MomentEpisode.INCONNU: 5,
    }
    return tuple(sorted(observations, key=lambda item: ordre[item.moment]))


def _verifier_consequences_explicitement_attribuees(
    consequences: tuple[ElementDocumenteV1, ...],
    index: dict[str, EntreeCatalogueSourceV1],
    temporalite: str,
) -> None:
    for consequence in consequences:
        texte = _texte_sources_referencees(consequence.source_ids, index)
        if MARQUEUR_CONSEQUENCE_EXPLICITE_RE.search(texte) is None:
            raise ValidationAnalyseEchouee(
                "Une consequence "
                f"{temporalite} doit etre explicitement attribuee dans la source. "
                "Une succession temporelle doit rester une evolution documentee."
            )


def _construire_incertitudes(
    sortie: SortieTerraAnalyseFonctionnelleV1,
    contexte: ContexteAnalyseFonctionnelleV1,
) -> tuple[IncertitudeSourceV1, ...]:
    autorisees = {
        passage: source.confirmation_id
        for source in (
            contexte.source_principale,
            *contexte.sources_complementaires,
        )
        for passage in source.passages_signales
    }
    if not autorisees:
        return ()
    resultat = []
    for incertitude in sortie.incertitudes_source:
        confirmation_id = autorisees.get(incertitude.passage_exact)
        if confirmation_id is None:
            raise ValidationAnalyseEchouee(
                "L'incertitude ne reproduit pas exactement un passage source signale."
            )
        resultat.append(
            IncertitudeSourceV1(
                passage_exact=incertitude.passage_exact,
                incidence=incertitude.incidence,
                confirmation_ids=(confirmation_id,),
            )
        )
    return tuple(resultat)


def _verifier_contradiction(
    moment_decrit: str,
    formulations: tuple[ElementDocumenteV1, ...],
    references: dict[str, ReferenceSourceV1],
) -> None:
    moments = {element.moment for element in formulations}
    if len(moments) != 1:
        raise ValidationAnalyseEchouee(
            "Des formulations situees a des moments differents ne sont pas une contradiction."
        )
    dates = {
        references[source_id].date_seance
        for element in formulations
        for source_id in element.source_ids
        if source_id in references
    }
    if len(dates) < 2:
        raise ValidationAnalyseEchouee(
            "Une contradiction V1 doit etre documentee par au moins deux sources datees."
        )
    if not moment_decrit.strip():
        raise ValidationAnalyseEchouee("Le moment contradictoire doit etre explicite.")


def _exiger_marqueur_explicite(
    texte: str,
    marqueurs: tuple[str, ...],
    message: str,
) -> None:
    normalise = texte.casefold()
    if not any(marqueur.casefold() in normalise for marqueur in marqueurs):
        raise ValidationAnalyseEchouee(message)


def _texte_sources_referencees(
    reference_ids: tuple[str, ...],
    index: dict[str, EntreeCatalogueSourceV1],
) -> str:
    contenus = [
        json.dumps(entree.contenu, ensure_ascii=False)
        for entree in index.values()
        if entree.reference.id in reference_ids
    ]
    if len(contenus) != len(reference_ids):
        raise ValidationAnalyseEchouee("Une source finale ne peut pas etre relue.")
    return " ".join(contenus)


def _interdire_contenu_hors_perimetre(
    sortie: SortieTerraAnalyseFonctionnelleV1,
) -> None:
    texte = json.dumps(sortie.model_dump(mode="json"), ensure_ascii=False).casefold()
    interdits = ("diagnostic", "dsm-", "cim-", "plan de traitement", "protocole thérapeutique")
    if any(terme in texte for terme in interdits):
        raise ValidationAnalyseEchouee("La sortie depasse le perimetre clinique V1.")


def chemins_sortie_analyse(
    contexte: ContexteAnalyseFonctionnelleV1,
) -> tuple[Path, Path]:
    dossier = (
        contexte.dossier_patient
        / DOSSIER_DOCUMENTS_GENERES
        / DOSSIER_ANALYSES
    )
    base = f"analyse_{contexte.source_principale.date_seance.isoformat()}_{contexte.empreinte_generation[:12]}"
    return dossier / f"{base}.json", dossier / f"{base}.md"


def charger_analyse_en_cache(
    contexte: ContexteAnalyseFonctionnelleV1,
) -> AnalyseFonctionnelleEpisodeV1 | None:
    chemin_json, _ = chemins_sortie_analyse(contexte)
    if not chemin_json.is_file():
        return None
    analyse = AnalyseFonctionnelleEpisodeV1.model_validate_json(
        chemin_json.read_bytes()
    )
    if analyse.provenance.empreinte_generation != contexte.empreinte_generation:
        return None
    if (
        analyse.dossier_id_pseudonymise != contexte.dossier_id_pseudonymise
        or analyse.identifiant_analyse
        != f"afe_{contexte.empreinte_generation[:24]}"
    ):
        raise ValidationAnalyseEchouee(
            "Le cache courant ne correspond pas au patient ou a l'identifiant attendu."
        )
    documents_autorises = {
        source.json_clinique
        for source in (
            contexte.source_principale,
            *contexte.sources_complementaires,
        )
    }
    for reference in analyse.provenance.references_sources:
        if reference.document not in documents_autorises:
            raise ValidationAnalyseEchouee(
                "Le cache contient une source qui n'a pas ete selectionnee."
            )
        resoudre_reference_source_v1(
            reference,
            contexte.dossier_patient,
            contexte.dossier_id_pseudonymise,
        )
    return analyse


def enregistrer_analyse(
    analyse: AnalyseFonctionnelleEpisodeV1,
    contexte: ContexteAnalyseFonctionnelleV1,
) -> tuple[Path, Path]:
    if analyse.provenance.empreinte_generation != contexte.empreinte_generation:
        raise ValidationAnalyseEchouee("L'analyse ne correspond pas au contexte courant.")
    chemin_json, chemin_markdown = chemins_sortie_analyse(contexte)
    _ecrire_atomique(
        chemin_json,
        (analyse.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )
    _ecrire_atomique(
        chemin_markdown,
        rendre_analyse_clinicien(analyse).encode("utf-8"),
    )
    return chemin_json, chemin_markdown


def generer_ou_reutiliser_analyse(
    contexte: ContexteAnalyseFonctionnelleV1,
    client_factory: Any,
    genere_le: datetime | None = None,
) -> tuple[AnalyseFonctionnelleEpisodeV1, Any | None, bool]:
    """N'instancie aucun client et ne fait aucun appel si le cache est courant."""

    cache = charger_analyse_en_cache(contexte)
    if cache is not None:
        return cache, None, True
    client = client_factory()
    analyse, reponse = generer_analyse_fonctionnelle(
        client,
        contexte,
        genere_le=genere_le,
    )
    enregistrer_analyse(analyse, contexte)
    return analyse, reponse, False


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


def rendre_analyse_clinicien(analyse: AnalyseFonctionnelleEpisodeV1) -> str:
    """Rendu stable, clinique et depourvu de metadonnees techniques."""

    lignes = [
        f"# {analyse.libelle_clinique}",
        "",
        "**Brouillon clinique à examiner.** Les éléments ci-dessous sont documentés dans des sources confirmées, mais les assertions du JSON machine n'ont pas été validées individuellement.",
        "",
        f"**Épisode ciblé :** {analyse.description_episode}",
        f"**Raison de l'analyse :** {analyse.raison_de_selection}",
    ]
    if analyse.date_episode is not None:
        lignes.append(f"**Date de l'épisode :** {analyse.date_episode.strftime('%d/%m/%Y')}")
    if analyse.niveau_completude is NiveauCompletude.DESCRIPTIF:
        lignes.append("**Portée :** description partielle, sans chaîne fonctionnelle établie.")
    lignes.extend(["", "## Contexte et antécédents"])
    if analyse.contexte_et_antecedents:
        _ajouter_items(lignes, analyse.contexte_et_antecedents)
    else:
        lignes.append(
            "- Aucun contexte ou antécédent additionnel documenté pour cet épisode."
        )
    lignes.extend(["", "## Réponses pendant l'épisode"])
    sections = (
        ("Comportements", analyse.reponses.comportements),
        ("Évitements ou protections explicitement documentés", analyse.reponses.evitements_ou_protections_documentes),
        ("Émotions", analyse.reponses.emotions),
        ("Sensations", analyse.reponses.sensations),
        ("Cognitions, images et anticipations", analyse.reponses.cognitions_images_anticipations),
        ("Réponses de l'environnement", analyse.reponses.reponses_environnement),
    )
    for titre, items in sections:
        if items:
            lignes.extend([f"", f"### {titre}"])
            _ajouter_items(lignes, items)
    if analyse.reponses.fonctions_evitement_ou_protection_possibles:
        lignes.extend(["", "### Fonctions d'évitement ou de protection possibles"])
        for item in analyse.reponses.fonctions_evitement_ou_protection_possibles:
            lignes.append(f"- Hypothèse : {item.contenu}")
    if analyse.evolutions_temporelles_documentees:
        lignes.extend(["", "## Évolutions temporelles documentées"])
        for evolution in analyse.evolutions_temporelles_documentees:
            sequence = " ; ".join(
                _formater_observation_temporelle(observation)
                for observation in evolution.observations
            )
            lignes.append(f"- {sequence}.")
        lignes.append(
            "- Aucun lien causal ou fonctionnel n'est établi par cette succession temporelle."
        )
    lignes.extend(["", "## Conséquences explicitement documentées"])
    if analyse.consequences_immediates:
        lignes.append("### Immédiates")
        _ajouter_items(lignes, analyse.consequences_immediates)
    else:
        lignes.append(
            "- Aucune conséquence causale ou subjective explicitement attribuée à un comportement n'est documentée."
        )
    if analyse.consequences_differees:
        lignes.extend(["", "### Différées explicitement attribuées"])
        _ajouter_items(lignes, analyse.consequences_differees)
    lignes.extend(["", "## Synthèse fonctionnelle actuelle"])
    if analyse.hypothese_fonctionnelle is None:
        lignes.append("Fonction non déterminée avec les données disponibles.")
    else:
        hypothese = analyse.hypothese_fonctionnelle
        lignes.extend(
            [
                f"- **Réponse cible :** {hypothese.reponse_cible}",
                f"- **Hypothèse de fonction :** {hypothese.fonction_supposee}",
                f"- **Effet immédiat pertinent :** {hypothese.effet_immediat_pertinent}",
            ]
        )
        if hypothese.cout_ou_effet_differe_pertinent:
            lignes.append(
                f"- **Coût ou effet différé pertinent :** {hypothese.cout_ou_effet_differe_pertinent}",
            )
        lignes.extend(
            [
                f"- **Données en faveur :** {'; '.join(item.contenu for item in hypothese.donnees_en_faveur)}",
                f"- **Limites :** {'; '.join(hypothese.donnees_en_defaveur_ou_limites)}",
                f"- **Alternative(s) :** {'; '.join(hypothese.hypotheses_alternatives)}",
                f"- **À tester :** {hypothese.prediction_ou_question_testable}",
            ]
        )
    if analyse.variations_exceptions_ressources:
        lignes.extend(["", "## Variations, exceptions et ressources"])
        _ajouter_items(lignes, analyse.variations_exceptions_ressources)
    if analyse.contradictions or analyse.incertitudes_source or analyse.donnees_a_explorer:
        lignes.extend(["", "## Contradictions, incertitudes et données à explorer"])
        for contradiction in analyse.contradictions:
            lignes.append(f"- Contradiction au même moment ({contradiction.moment_decrit}) : " + " / ".join(item.contenu for item in contradiction.formulations))
        for incertitude in analyse.incertitudes_source:
            lignes.append(f"- Source incertaine : {incertitude.passage_exact} ({incertitude.incidence})")
        for donnee in analyse.donnees_a_explorer:
            lignes.append(f"- À explorer : {donnee.contenu} ({donnee.raison})")
    if analyse.formulation_partagee_documentee is not None or analyse.decision_clinique_documentee is not None:
        lignes.extend(["", "## Compréhension partagée et suite documentée"])
        if analyse.formulation_partagee_documentee is not None:
            lignes.append(f"- {analyse.formulation_partagee_documentee.contenu}")
        if analyse.decision_clinique_documentee is not None:
            lignes.append(f"- Décision documentée : {analyse.decision_clinique_documentee.contenu}")
    return "\n".join(lignes).rstrip() + "\n"


def _ajouter_items(lignes: list[str], items: tuple[ElementDocumenteV1, ...]) -> None:
    for item in items:
        precision = []
        if item.moment is not MomentEpisode.INCONNU:
            precision.append(
                {
                    MomentEpisode.AVANT: "avant",
                    MomentEpisode.DEBUT: "début",
                    MomentEpisode.PENDANT: "pendant",
                    MomentEpisode.FIN: "fin",
                    MomentEpisode.APRES: "après",
                }[item.moment]
            )
        if item.intensite_ou_frequence:
            precision.append(item.intensite_ou_frequence)
        suffixe = f" ({', '.join(precision)})" if precision else ""
        lignes.append(f"- {item.contenu}{suffixe}")


def _formater_observation_temporelle(item: ElementDocumenteV1) -> str:
    moment = {
        MomentEpisode.AVANT: "Avant",
        MomentEpisode.DEBUT: "Au début",
        MomentEpisode.PENDANT: "Pendant",
        MomentEpisode.FIN: "À la fin",
        MomentEpisode.APRES: "Après",
        MomentEpisode.INCONNU: "Moment non précisé",
    }[item.moment]
    intensite = (
        f" ({item.intensite_ou_frequence})"
        if item.intensite_ou_frequence
        else ""
    )
    return f"{moment} : {item.contenu.rstrip('.')}" + intensite
