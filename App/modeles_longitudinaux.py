"""Contrats deterministes du registre clinique longitudinal V1.

Les identifiants des objets cliniques sont aleatoires a la creation puis
conserves lors des revisions. Les identifiants de provenance sont, eux,
deterministes pour une version de source, un pointeur et une relation donnes.
Ce module ne depend ni du pipeline principal ni d'un modele de langage.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, ClassVar, Literal
from uuid import uuid4
import hashlib
import json
import re

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)


SCHEMA_REGISTRE_LONGITUDINAL = "1.0"
SCHEMA_PROPOSITIONS_LONGITUDINALES = "1.0"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_ID_RE = re.compile(r"^src_[0-9a-f]{24}$")


def calculer_sha256_octets(contenu: bytes) -> str:
    """Calcule l'empreinte d'un document a partir de ses octets exacts."""

    return hashlib.sha256(contenu).hexdigest()


def serialiser_json_canonique(valeur: JsonValue) -> bytes:
    """Serialise une valeur JSON selon l'unique convention V1 d'empreinte."""

    return json.dumps(
        valeur,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def calculer_sha256_json_canonique(valeur: JsonValue) -> str:
    """Calcule l'empreinte stable d'une valeur JSON decodee."""

    return calculer_sha256_octets(serialiser_json_canonique(valeur))


class ModeleStrict(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class StatutEpistemique(str, Enum):
    EXPLICITE = "explicite"
    SYNTHESE_PRUDENTE = "synthese_prudente"
    HYPOTHESE_CLINIQUE = "hypothese_clinique"
    INCONNU_A_EXPLORER = "inconnu_a_explorer"


class StatutAction(str, Enum):
    PROPOSITION_SYSTEME = "proposition_systeme"
    OPTION_CLINICIEN = "option_clinicien"
    DECISION_CLINICIEN = "decision_clinicien"
    DECISION_CONJOINTE = "decision_conjointe"
    REALISE = "realise"
    ABANDONNE_OU_MODIFIE = "abandonne_ou_modifie"


class StatutDocumentaireValide(str, Enum):
    VALIDE_CLINICIEN = "valide_clinicien"
    PROMU_DOSSIER = "promu_dossier"


class RelationSupport(str, Enum):
    DIRECT = "direct"
    SYNTHETIQUE = "synthetique"
    CONTRADICTOIRE = "contradictoire"
    CONTEXTUEL = "contextuel"


class TypeObjetLongitudinal(str, Enum):
    PROBLEME_SUIVI = "probleme_suivi"
    OBJECTIF_THERAPEUTIQUE = "objectif_therapeutique"
    TACHE_INTERSESSION = "tache_intersession"
    ELEMENT_A_REPRENDRE = "element_a_reprendre"


class TypeOperationProposee(str, Enum):
    CREATION = "creation"
    MODIFICATION = "modification"
    CHANGEMENT_ETAT = "changement_etat"
    RELATION = "relation"
    FUSION = "fusion"
    REMPLACEMENT = "remplacement"


class EtatRevueProposition(str, Enum):
    A_REVOIR = "a_revoir"
    ACCEPTEE = "acceptee"
    CORRIGEE = "corrigee"
    REJETEE = "rejetee"


class TypeRevision(str, Enum):
    CREATION = "creation"
    MODIFICATION = "modification"
    CHANGEMENT_ETAT = "changement_etat"
    REACTIVATION = "reactivation"
    REMPLACEMENT = "remplacement"
    FUSION = "fusion"


class TypeRelationObjet(str, Enum):
    REMPLACE_PAR = "remplace_par"
    FUSIONNE_DANS = "fusionne_dans"
    ISSU_DE = "issu_de"


class TypeObjectif(str, Enum):
    RESULTAT = "resultat"
    PROCESSUS = "processus"
    COMPETENCE = "competence"


class EtatProbleme(str, Enum):
    CANDIDAT = "candidat"
    ACTIF = "actif"
    EN_PAUSE = "en_pause"
    RESOLU = "resolu"
    ABANDONNE = "abandonne"
    REMPLACE = "remplace"


class EtatObjectif(str, Enum):
    CANDIDAT = "candidat"
    ACTIF = "actif"
    EN_PAUSE = "en_pause"
    ATTEINT = "atteint"
    ABANDONNE = "abandonne"
    REMPLACE = "remplace"


class CycleTache(str, Enum):
    OUVERTE = "ouverte"
    CLOSE = "close"


class StatutDecisionTache(str, Enum):
    PROPOSEE_DOCUMENTEE = "proposee_documentee"
    CONVENUE = "convenue"
    ABANDONNEE_OU_MODIFIEE = "abandonnee_ou_modifiee"


class StatutResultatTache(str, Enum):
    RESULTAT_NON_DOCUMENTE = "resultat_non_documente"
    PARTIELLE = "partielle"
    REALISEE = "realisee"
    NON_REALISEE_RAPPORTEE = "non_realisee_rapportee"
    ADAPTEE = "adaptee"
    REPORTEE = "reportee"
    ARRETEE = "arretee"


class EtatElementAReprendre(str, Enum):
    CANDIDAT = "candidat"
    OUVERT = "ouvert"
    PLANIFIE = "planifie"
    RESOLU = "resolu"
    ABANDONNE = "abandonne"
    REMPLACE = "remplace"


class ValidationClinique(ModeleStrict):
    validateur_id: str = Field(min_length=1)
    valide_le: datetime
    motif: str = Field(min_length=1)

    @field_validator("valide_le")
    @classmethod
    def verifier_date_avec_fuseau(
        cls,
        valeur: datetime,
    ) -> datetime:
        if valeur.tzinfo is None or valeur.utcoffset() is None:
            raise ValueError(
                "La date de validation doit inclure un fuseau horaire."
            )
        return valeur


class PeriodeCouverte(ModeleStrict):
    date_debut: date
    date_fin: date

    @model_validator(mode="after")
    def verifier_ordre(self) -> PeriodeCouverte:
        if self.date_fin < self.date_debut:
            raise ValueError(
                "La fin de la periode ne peut pas preceder son debut."
            )
        return self


class ReferenceSourceV1(ModeleStrict):
    id: str
    dossier_id_pseudonymise: str = Field(min_length=1)
    type_document: Literal["json_clinique_v2"]
    document: str = Field(min_length=1)
    document_sha256: str
    date_seance: date
    categorie_source: str = Field(min_length=1)
    json_pointer: str = Field(min_length=1)
    element_sha256: str
    relation_support: RelationSupport
    extraction_schema_version: str = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def verifier_id_source(cls, valeur: str) -> str:
        if not SOURCE_ID_RE.fullmatch(valeur):
            raise ValueError("Identifiant de source V1 invalide.")
        return valeur

    @field_validator("document_sha256", "element_sha256")
    @classmethod
    def verifier_sha256(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Une empreinte SHA-256 doit contenir 64 hexadecimaux.")
        return valeur

    @field_validator("document")
    @classmethod
    def verifier_chemin_relatif(cls, valeur: str) -> str:
        if "\\" in valeur:
            raise ValueError("Le chemin de source doit utiliser des barres obliques.")
        chemin_posix = PurePosixPath(valeur)
        chemin_windows = PureWindowsPath(valeur)
        if (
            chemin_posix.is_absolute()
            or chemin_windows.is_absolute()
            or ".." in chemin_posix.parts
        ):
            raise ValueError("Le chemin de source doit rester relatif au dossier patient.")
        return valeur

    @field_validator("json_pointer")
    @classmethod
    def verifier_json_pointer(cls, valeur: str) -> str:
        if not valeur.startswith("/"):
            raise ValueError("Le pointeur JSON doit commencer par '/'.")
        if re.search(r"~(?![01])", valeur):
            raise ValueError("Le pointeur JSON contient un echappement invalide.")
        return valeur

    @model_validator(mode="after")
    def verifier_categorie_dans_pointeur(self) -> ReferenceSourceV1:
        premier_segment = self.json_pointer.split("/", 2)[1]
        premier_segment = premier_segment.replace("~1", "/").replace("~0", "~")
        if premier_segment != self.categorie_source:
            raise ValueError(
                "La categorie source doit correspondre au premier segment du pointeur JSON."
            )
        return self


class AssertionClinique(ModeleStrict):
    contenu: str = Field(min_length=1)
    statut_epistemique: StatutEpistemique
    source_ids: tuple[str, ...] = Field(min_length=1)
    periode_couverte: PeriodeCouverte | None = None

    @field_validator("source_ids")
    @classmethod
    def verifier_sources_uniques(
        cls,
        valeurs: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(set(valeurs)) != len(valeurs):
            raise ValueError("Une assertion ne doit pas dupliquer une source.")
        for valeur in valeurs:
            if not SOURCE_ID_RE.fullmatch(valeur):
                raise ValueError("Identifiant de source invalide dans l'assertion.")
        return valeurs

    @model_validator(mode="after")
    def verifier_periode_synthese(self) -> AssertionClinique:
        if (
            self.statut_epistemique is StatutEpistemique.SYNTHESE_PRUDENTE
            and self.periode_couverte is None
        ):
            raise ValueError(
                "Une synthese prudente doit indiquer la periode couverte."
            )
        return self


class ModificationChamp(ModeleStrict):
    champ: str = Field(min_length=1)
    avant: JsonValue | None
    apres: JsonValue | None


class RevisionLongitudinale(ModeleStrict):
    version: int = Field(ge=1)
    version_precedente: int | None
    type_revision: TypeRevision
    date_revision: datetime
    validation: ValidationClinique
    source_ids: tuple[str, ...] = Field(min_length=1)
    modifications: tuple[ModificationChamp, ...] = Field(min_length=1)

    @field_validator("date_revision")
    @classmethod
    def verifier_date_revision(
        cls,
        valeur: datetime,
    ) -> datetime:
        if valeur.tzinfo is None or valeur.utcoffset() is None:
            raise ValueError("La date de revision doit inclure un fuseau horaire.")
        return valeur

    @model_validator(mode="after")
    def verifier_version(self) -> RevisionLongitudinale:
        if self.version == 1:
            if self.version_precedente is not None:
                raise ValueError("La version initiale ne remplace aucune version.")
            if self.type_revision is not TypeRevision.CREATION:
                raise ValueError("La version initiale doit etre une creation.")
        elif self.version_precedente != self.version - 1:
            raise ValueError("Une revision doit suivre exactement la version precedente.")
        if self.date_revision != self.validation.valide_le:
            raise ValueError("La date de revision doit etre celle de la validation.")
        return self


class RelationObjet(ModeleStrict):
    type_relation: TypeRelationObjet
    type_objet_cible: TypeObjetLongitudinal
    objet_cible_id: str = Field(min_length=1)
    version_objet_cible: int = Field(ge=1)
    date_relation: date
    source_ids: tuple[str, ...] = Field(min_length=1)


class ObjetLongitudinalBase(ModeleStrict):
    PREFIXE_ID: ClassVar[str]

    id: str
    version: int = Field(ge=1)
    statut_documentaire: StatutDocumentaireValide
    validation_creation: ValidationClinique
    relations: tuple[RelationObjet, ...] = ()
    historique: tuple[RevisionLongitudinale, ...] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def verifier_identifiant(cls, valeur: str) -> str:
        motif = rf"^{re.escape(cls.PREFIXE_ID)}_[0-9a-f]{{32}}$"
        if not re.fullmatch(motif, valeur):
            raise ValueError(
                f"Identifiant invalide pour un objet {cls.PREFIXE_ID}."
            )
        return valeur

    @model_validator(mode="after")
    def verifier_historique(self) -> ObjetLongitudinalBase:
        if self.historique[0].type_revision is not TypeRevision.CREATION:
            raise ValueError("L'historique doit commencer par une creation.")
        if self.historique[0].validation != self.validation_creation:
            raise ValueError("La validation initiale doit correspondre a la creation.")
        version_attendue = 1
        date_precedente: datetime | None = None
        for revision in self.historique:
            if revision.version != version_attendue:
                raise ValueError("Les versions de l'historique doivent etre continues.")
            if (
                date_precedente is not None
                and revision.date_revision < date_precedente
            ):
                raise ValueError("Les revisions doivent rester chronologiques.")
            date_precedente = revision.date_revision
            version_attendue += 1
        if self.historique[-1].version != self.version:
            raise ValueError("La version courante doit etre la derniere revision.")
        return self


class ProblemeSuivi(ObjetLongitudinalBase):
    PREFIXE_ID: ClassVar[str] = "prb"

    type_objet: Literal["probleme_suivi"] = "probleme_suivi"
    etat: EtatProbleme
    libelle: AssertionClinique
    description: AssertionClinique | None = None
    contexte: tuple[AssertionClinique, ...] = ()
    impact: tuple[AssertionClinique, ...] = ()
    priorite: AssertionClinique | None = None
    objectif_ids: tuple[str, ...] = ()
    tache_ids: tuple[str, ...] = ()


class ObjectifTherapeutique(ObjetLongitudinalBase):
    PREFIXE_ID: ClassVar[str] = "obj"

    type_objet: Literal["objectif_therapeutique"] = "objectif_therapeutique"
    etat: EtatObjectif
    type_objectif: TypeObjectif
    formulation: AssertionClinique
    probleme_ids: tuple[str, ...] = Field(min_length=1)
    indicateurs_atteinte: tuple[AssertionClinique, ...] = ()
    importance: AssertionClinique | None = None
    priorite: AssertionClinique | None = None
    horizon: AssertionClinique | None = None

    @model_validator(mode="after")
    def verifier_formulation_explicite(self) -> ObjectifTherapeutique:
        if self.formulation.statut_epistemique is not StatutEpistemique.EXPLICITE:
            raise ValueError(
                "La formulation d'un objectif valide doit etre explicite."
            )
        return self


class TacheIntersession(ObjetLongitudinalBase):
    PREFIXE_ID: ClassVar[str] = "tch"

    type_objet: Literal["tache_intersession"] = "tache_intersession"
    cycle: CycleTache
    statut_decision: StatutDecisionTache
    statut_resultat: StatutResultatTache
    consigne: AssertionClinique
    probleme_ids: tuple[str, ...] = ()
    objectif_ids: tuple[str, ...] = ()
    rationale_partage: AssertionClinique | None = None
    parametres: tuple[AssertionClinique, ...] = ()
    conditions_realisation: tuple[AssertionClinique, ...] = ()
    date_proposition_ou_accord: date
    echeance: date | None = None
    resultat_documente: AssertionClinique | None = None
    apprentissages: tuple[AssertionClinique, ...] = ()
    effets_indesirables: tuple[AssertionClinique, ...] = ()
    obstacles: tuple[AssertionClinique, ...] = ()
    decision_suite: AssertionClinique | None = None

    @model_validator(mode="after")
    def verifier_resultat(self) -> TacheIntersession:
        non_documente = (
            self.statut_resultat
            is StatutResultatTache.RESULTAT_NON_DOCUMENTE
        )
        if non_documente and self.resultat_documente is not None:
            raise ValueError(
                "Une tache au resultat non documente ne peut pas contenir de resultat."
            )
        if not non_documente and self.resultat_documente is None:
            raise ValueError(
                "Un statut de resultat documente exige une assertion source."
            )
        if self.cycle is CycleTache.CLOSE and non_documente:
            raise ValueError(
                "Une tache ne peut pas etre close sans resultat ou decision documente."
            )
        if self.echeance is not None and self.echeance < self.date_proposition_ou_accord:
            raise ValueError("L'echeance ne peut pas preceder la proposition ou l'accord.")
        return self


class CibleElementAReprendre(ModeleStrict):
    type_cible: Literal[
        "probleme_suivi",
        "objectif_therapeutique",
        "tache_intersession",
        "source",
    ]
    objet_id: str | None = None
    version_objet: int | None = Field(default=None, ge=1)
    source_id: str | None = None

    @model_validator(mode="after")
    def verifier_cible(self) -> CibleElementAReprendre:
        if self.type_cible == "source":
            if self.source_id is None or self.objet_id is not None:
                raise ValueError("Une cible source doit uniquement fournir source_id.")
            if self.version_objet is not None:
                raise ValueError("Une source n'a pas de version d'objet longitudinal.")
        else:
            if self.objet_id is None or self.version_objet is None:
                raise ValueError("Une cible objet doit fournir son id et sa version.")
            if self.source_id is not None:
                raise ValueError("Une cible objet ne doit pas fournir source_id.")
        return self


class ElementAReprendre(ObjetLongitudinalBase):
    PREFIXE_ID: ClassVar[str] = "rep"

    type_objet: Literal["element_a_reprendre"] = "element_a_reprendre"
    etat: EtatElementAReprendre
    contenu: AssertionClinique
    cible: CibleElementAReprendre | None = None
    raison_report: AssertionClinique | None = None
    priorite: AssertionClinique | None = None
    echeance: date | None = None


ObjetLongitudinal = (
    ProblemeSuivi
    | ObjectifTherapeutique
    | TacheIntersession
    | ElementAReprendre
)


class DifferenceProposee(ModeleStrict):
    champ: str = Field(min_length=1)
    valeur_actuelle: JsonValue | None
    valeur_proposee: JsonValue | None


class PropositionMiseAJour(ModeleStrict):
    id: str
    type_objet: TypeObjetLongitudinal
    operation: TypeOperationProposee
    objet_cible_id: str | None = None
    version_objet_cible: int | None = Field(default=None, ge=1)
    contenu_propose: dict[str, JsonValue]
    differences: tuple[DifferenceProposee, ...] = Field(min_length=1)
    justification: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    statuts_epistemiques: tuple[StatutEpistemique, ...] = Field(min_length=1)
    statut_action: Literal[StatutAction.PROPOSITION_SYSTEME] = (
        StatutAction.PROPOSITION_SYSTEME
    )
    statut_documentaire: Literal["brouillon_genere"] = "brouillon_genere"
    etat_revue: EtatRevueProposition = EtatRevueProposition.A_REVOIR
    decision_revue: ValidationClinique | None = None
    cree_le: datetime
    modele: str = Field(min_length=1)
    version_prompt: str = Field(min_length=1)
    version_generateur: str = Field(min_length=1)
    prompt_sha256: str
    empreinte_sources_sha256: str

    @field_validator("id")
    @classmethod
    def verifier_id_proposition(cls, valeur: str) -> str:
        if not re.fullmatch(r"^prop_[0-9a-f]{32}$", valeur):
            raise ValueError("Identifiant de proposition invalide.")
        return valeur

    @field_validator("prompt_sha256", "empreinte_sources_sha256")
    @classmethod
    def verifier_empreinte(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Empreinte SHA-256 invalide.")
        return valeur

    @field_validator("cree_le")
    @classmethod
    def verifier_creation_avec_fuseau(cls, valeur: datetime) -> datetime:
        if valeur.tzinfo is None or valeur.utcoffset() is None:
            raise ValueError("La date de creation doit inclure un fuseau horaire.")
        return valeur

    @model_validator(mode="after")
    def verifier_cible_et_revue(self) -> PropositionMiseAJour:
        if self.operation is TypeOperationProposee.CREATION:
            if self.objet_cible_id is not None or self.version_objet_cible is not None:
                raise ValueError("Une creation ne cible aucun objet existant.")
        elif self.objet_cible_id is None or self.version_objet_cible is None:
            raise ValueError("Une mise a jour doit cibler un objet et sa version.")
        if self.etat_revue is EtatRevueProposition.A_REVOIR:
            if self.decision_revue is not None:
                raise ValueError("Une proposition a revoir ne porte pas de decision.")
        elif self.decision_revue is None:
            raise ValueError("Une proposition revue doit conserver la decision explicite.")
        return self


class RegistreLongitudinalV1(ModeleStrict):
    schema_version: Literal["1.0"] = SCHEMA_REGISTRE_LONGITUDINAL
    dossier_id_pseudonymise: str = Field(min_length=1)
    version_registre: int = Field(ge=1)
    date_coupure: date
    statut_documentaire: StatutDocumentaireValide
    references_sources: tuple[ReferenceSourceV1, ...] = ()
    problemes_suivis: tuple[ProblemeSuivi, ...] = ()
    objectifs_therapeutiques: tuple[ObjectifTherapeutique, ...] = ()
    taches_intersession: tuple[TacheIntersession, ...] = ()
    elements_a_reprendre: tuple[ElementAReprendre, ...] = ()

    @model_validator(mode="after")
    def verifier_integrite(self) -> RegistreLongitudinalV1:
        references = {reference.id: reference for reference in self.references_sources}
        if len(references) != len(self.references_sources):
            raise ValueError("Les identifiants de source doivent etre uniques.")
        for reference in self.references_sources:
            if reference.dossier_id_pseudonymise != self.dossier_id_pseudonymise:
                raise ValueError("Une source appartient a un autre dossier pseudonymise.")
            if reference.date_seance > self.date_coupure:
                raise ValueError("Une source depasse la date de coupure du registre.")

        objets = self.tous_les_objets()
        index_objets = {objet.id: objet for objet in objets}
        if len(index_objets) != len(objets):
            raise ValueError("Les identifiants des objets doivent etre uniques.")

        ids_sources_connus = set(references)
        for objet in objets:
            ids_utilises = _collecter_source_ids(objet)
            inconnus = ids_utilises - ids_sources_connus
            if inconnus:
                raise ValueError(
                    "L'objet reference des sources absentes du catalogue : "
                    + ", ".join(sorted(inconnus))
                )
            for relation in objet.relations:
                cible = index_objets.get(relation.objet_cible_id)
                if cible is None:
                    raise ValueError("Une relation cible un objet absent du registre.")
                if cible.type_objet != relation.type_objet_cible.value:
                    raise ValueError("Une relation declare un type de cible incorrect.")
                if relation.version_objet_cible > cible.version:
                    raise ValueError("Une relation cible une version d'objet inexistante.")

        problemes = {objet.id for objet in self.problemes_suivis}
        objectifs = {objet.id for objet in self.objectifs_therapeutiques}
        taches = {objet.id for objet in self.taches_intersession}
        for probleme in self.problemes_suivis:
            _verifier_ids_existent(probleme.objectif_ids, objectifs, "objectif")
            _verifier_ids_existent(probleme.tache_ids, taches, "tache")
        for objectif in self.objectifs_therapeutiques:
            _verifier_ids_existent(objectif.probleme_ids, problemes, "probleme")
        for tache in self.taches_intersession:
            _verifier_ids_existent(tache.probleme_ids, problemes, "probleme")
            _verifier_ids_existent(tache.objectif_ids, objectifs, "objectif")
        for element in self.elements_a_reprendre:
            if element.cible is None:
                continue
            cible = element.cible
            if cible.type_cible == "source":
                if cible.source_id not in references:
                    raise ValueError("Un element a reprendre cible une source absente.")
            else:
                objet_cible = index_objets.get(cible.objet_id)
                if objet_cible is None:
                    raise ValueError("Un element a reprendre cible un objet absent.")
                if objet_cible.type_objet != cible.type_cible:
                    raise ValueError("Un element a reprendre declare un type de cible incorrect.")
                if cible.version_objet > objet_cible.version:
                    raise ValueError(
                        "Un element a reprendre cible une version inexistante."
                    )
        return self

    def tous_les_objets(self) -> tuple[ObjetLongitudinal, ...]:
        return (
            *self.problemes_suivis,
            *self.objectifs_therapeutiques,
            *self.taches_intersession,
            *self.elements_a_reprendre,
        )


class FichierPropositionsLongitudinalesV1(ModeleStrict):
    schema_version: Literal["1.0"] = SCHEMA_PROPOSITIONS_LONGITUDINALES
    dossier_id_pseudonymise: str = Field(min_length=1)
    statut_documentaire: Literal["brouillon_genere"] = "brouillon_genere"
    propositions: tuple[PropositionMiseAJour, ...]


class ResultatPromotionCreation(ModeleStrict):
    proposition_revue: PropositionMiseAJour
    objet_cree: ObjetLongitudinal
    registre: RegistreLongitudinalV1


TRANSITIONS_PROBLEME = {
    EtatProbleme.CANDIDAT: {
        EtatProbleme.ACTIF,
        EtatProbleme.ABANDONNE,
        EtatProbleme.REMPLACE,
    },
    EtatProbleme.ACTIF: {
        EtatProbleme.EN_PAUSE,
        EtatProbleme.RESOLU,
        EtatProbleme.ABANDONNE,
        EtatProbleme.REMPLACE,
    },
    EtatProbleme.EN_PAUSE: {
        EtatProbleme.ACTIF,
        EtatProbleme.RESOLU,
        EtatProbleme.ABANDONNE,
        EtatProbleme.REMPLACE,
    },
    EtatProbleme.RESOLU: {
        EtatProbleme.ACTIF,
        EtatProbleme.REMPLACE,
    },
    EtatProbleme.ABANDONNE: set(),
    EtatProbleme.REMPLACE: set(),
}

TRANSITIONS_OBJECTIF = {
    EtatObjectif.CANDIDAT: {
        EtatObjectif.ACTIF,
        EtatObjectif.ABANDONNE,
        EtatObjectif.REMPLACE,
    },
    EtatObjectif.ACTIF: {
        EtatObjectif.EN_PAUSE,
        EtatObjectif.ATTEINT,
        EtatObjectif.ABANDONNE,
        EtatObjectif.REMPLACE,
    },
    EtatObjectif.EN_PAUSE: {
        EtatObjectif.ACTIF,
        EtatObjectif.ATTEINT,
        EtatObjectif.ABANDONNE,
        EtatObjectif.REMPLACE,
    },
    EtatObjectif.ATTEINT: {
        EtatObjectif.ACTIF,
        EtatObjectif.REMPLACE,
    },
    EtatObjectif.ABANDONNE: set(),
    EtatObjectif.REMPLACE: set(),
}

TRANSITIONS_ELEMENT = {
    EtatElementAReprendre.CANDIDAT: {
        EtatElementAReprendre.OUVERT,
        EtatElementAReprendre.ABANDONNE,
        EtatElementAReprendre.REMPLACE,
    },
    EtatElementAReprendre.OUVERT: {
        EtatElementAReprendre.PLANIFIE,
        EtatElementAReprendre.RESOLU,
        EtatElementAReprendre.ABANDONNE,
        EtatElementAReprendre.REMPLACE,
    },
    EtatElementAReprendre.PLANIFIE: {
        EtatElementAReprendre.OUVERT,
        EtatElementAReprendre.RESOLU,
        EtatElementAReprendre.ABANDONNE,
        EtatElementAReprendre.REMPLACE,
    },
    EtatElementAReprendre.RESOLU: {
        EtatElementAReprendre.OUVERT,
        EtatElementAReprendre.REMPLACE,
    },
    EtatElementAReprendre.ABANDONNE: set(),
    EtatElementAReprendre.REMPLACE: set(),
}


def generer_identifiant_objet(
    type_objet: TypeObjetLongitudinal,
) -> str:
    prefixes = {
        TypeObjetLongitudinal.PROBLEME_SUIVI: "prb",
        TypeObjetLongitudinal.OBJECTIF_THERAPEUTIQUE: "obj",
        TypeObjetLongitudinal.TACHE_INTERSESSION: "tch",
        TypeObjetLongitudinal.ELEMENT_A_REPRENDRE: "rep",
    }
    return f"{prefixes[type_objet]}_{uuid4().hex}"


def generer_identifiant_proposition() -> str:
    return f"prop_{uuid4().hex}"


def creer_reference_source_v1(
    *,
    dossier_id_pseudonymise: str,
    document: str,
    document_sha256: str,
    date_seance: date,
    categorie_source: str,
    json_pointer: str,
    element_sha256: str,
    relation_support: RelationSupport,
    extraction_schema_version: str,
) -> ReferenceSourceV1:
    identite = {
        "dossier_id_pseudonymise": dossier_id_pseudonymise,
        "document": document,
        "document_sha256": document_sha256,
        "json_pointer": json_pointer,
        "element_sha256": element_sha256,
        "relation_support": relation_support.value,
        "extraction_schema_version": extraction_schema_version,
    }
    empreinte = calculer_sha256_json_canonique(identite)
    return ReferenceSourceV1(
        id=f"src_{empreinte[:24]}",
        dossier_id_pseudonymise=dossier_id_pseudonymise,
        type_document="json_clinique_v2",
        document=document,
        document_sha256=document_sha256,
        date_seance=date_seance,
        categorie_source=categorie_source,
        json_pointer=json_pointer,
        element_sha256=element_sha256,
        relation_support=relation_support,
        extraction_schema_version=extraction_schema_version,
    )


def creer_objet_valide(
    type_objet: TypeObjetLongitudinal,
    donnees: dict[str, Any],
    validation: ValidationClinique,
    source_ids: tuple[str, ...],
) -> ObjetLongitudinal:
    if not source_ids:
        raise ValueError("La creation validee exige au moins une source.")
    champs_reserves = {
        "id",
        "version",
        "type_objet",
        "statut_documentaire",
        "validation_creation",
        "historique",
    }
    interdits = champs_reserves.intersection(donnees)
    if interdits:
        raise ValueError(
            "Les donnees cliniques ne peuvent pas fixer les champs d'autorite : "
            + ", ".join(sorted(interdits))
        )
    classes = {
        TypeObjetLongitudinal.PROBLEME_SUIVI: ProblemeSuivi,
        TypeObjetLongitudinal.OBJECTIF_THERAPEUTIQUE: ObjectifTherapeutique,
        TypeObjetLongitudinal.TACHE_INTERSESSION: TacheIntersession,
        TypeObjetLongitudinal.ELEMENT_A_REPRENDRE: ElementAReprendre,
    }
    revision = RevisionLongitudinale(
        version=1,
        version_precedente=None,
        type_revision=TypeRevision.CREATION,
        date_revision=validation.valide_le,
        validation=validation,
        source_ids=source_ids,
        modifications=(
            ModificationChamp(
                champ="creation",
                avant=None,
                apres=_normaliser_json(donnees),
            ),
        ),
    )
    classe = classes[type_objet]
    return classe.model_validate(
        {
            **donnees,
            "id": generer_identifiant_objet(type_objet),
            "version": 1,
            "statut_documentaire": "valide_clinicien",
            "validation_creation": validation,
            "historique": (revision,),
        }
    )


def reviser_objet(
    objet: ObjetLongitudinal,
    changements: dict[str, Any],
    validation: ValidationClinique,
    source_ids: tuple[str, ...],
    type_revision: TypeRevision = TypeRevision.MODIFICATION,
) -> ObjetLongitudinal:
    if not changements:
        raise ValueError("Une revision doit modifier au moins un champ.")
    if not source_ids:
        raise ValueError("Une revision validee exige au moins une source.")
    champs_interdits = {
        "id",
        "version",
        "type_objet",
        "statut_documentaire",
        "validation_creation",
        "historique",
    }
    interdits = champs_interdits.intersection(changements)
    if interdits:
        raise ValueError(
            "Une revision ne peut pas modifier les champs d'autorite : "
            + ", ".join(sorted(interdits))
        )
    inconnus = set(changements) - set(type(objet).model_fields)
    if inconnus:
        raise ValueError("Champs de revision inconnus : " + ", ".join(sorted(inconnus)))

    _verifier_transition(objet, changements, type_revision)
    modifications = tuple(
        ModificationChamp(
            champ=champ,
            avant=_normaliser_json(getattr(objet, champ)),
            apres=_normaliser_json(valeur),
        )
        for champ, valeur in changements.items()
        if _normaliser_json(getattr(objet, champ)) != _normaliser_json(valeur)
    )
    if not modifications:
        raise ValueError("La revision ne change aucune valeur.")

    nouvelle_version = objet.version + 1
    revision = RevisionLongitudinale(
        version=nouvelle_version,
        version_precedente=objet.version,
        type_revision=type_revision,
        date_revision=validation.valide_le,
        validation=validation,
        source_ids=source_ids,
        modifications=modifications,
    )
    contenu = objet.model_dump()
    contenu.update(changements)
    contenu["version"] = nouvelle_version
    contenu["historique"] = (*objet.historique, revision)
    return type(objet).model_validate(contenu)


def promouvoir_proposition_creation(
    registre: RegistreLongitudinalV1,
    proposition: PropositionMiseAJour,
    validation: ValidationClinique,
) -> ResultatPromotionCreation:
    if proposition.operation is not TypeOperationProposee.CREATION:
        raise ValueError("Cette operation explicite ne promeut que les creations.")
    if proposition.etat_revue is not EtatRevueProposition.A_REVOIR:
        raise ValueError("La proposition a deja fait l'objet d'une revue.")
    sources_connues = {source.id for source in registre.references_sources}
    inconnues = set(proposition.source_ids) - sources_connues
    if inconnues:
        raise ValueError("La proposition reference une source absente du registre.")

    objet = creer_objet_valide(
        proposition.type_objet,
        dict(proposition.contenu_propose),
        validation,
        proposition.source_ids,
    )
    champs = {
        TypeObjetLongitudinal.PROBLEME_SUIVI: "problemes_suivis",
        TypeObjetLongitudinal.OBJECTIF_THERAPEUTIQUE: "objectifs_therapeutiques",
        TypeObjetLongitudinal.TACHE_INTERSESSION: "taches_intersession",
        TypeObjetLongitudinal.ELEMENT_A_REPRENDRE: "elements_a_reprendre",
    }
    champ_registre = champs[proposition.type_objet]
    contenu_registre = registre.model_dump()
    contenu_registre["version_registre"] = registre.version_registre + 1
    contenu_registre[champ_registre] = (
        *getattr(registre, champ_registre),
        objet,
    )
    registre_mis_a_jour = RegistreLongitudinalV1.model_validate(contenu_registre)
    proposition_revue = PropositionMiseAJour.model_validate(
        {
            **proposition.model_dump(),
            "etat_revue": EtatRevueProposition.ACCEPTEE,
            "decision_revue": validation,
        }
    )
    return ResultatPromotionCreation(
        proposition_revue=proposition_revue,
        objet_cree=objet,
        registre=registre_mis_a_jour,
    )


def enregistrer_registre(
    registre: RegistreLongitudinalV1,
    chemin: Path,
) -> None:
    _enregistrer_modele_json(registre, chemin)


def charger_registre(chemin: Path) -> RegistreLongitudinalV1:
    return RegistreLongitudinalV1.model_validate_json(
        chemin.read_text(encoding="utf-8")
    )


def enregistrer_propositions(
    propositions: FichierPropositionsLongitudinalesV1,
    chemin: Path,
) -> None:
    _enregistrer_modele_json(propositions, chemin)


def charger_propositions(
    chemin: Path,
) -> FichierPropositionsLongitudinalesV1:
    return FichierPropositionsLongitudinalesV1.model_validate_json(
        chemin.read_text(encoding="utf-8")
    )


def _enregistrer_modele_json(modele: BaseModel, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(
        json.dumps(
            modele.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporaire.replace(chemin)


def _normaliser_json(valeur: Any) -> JsonValue | None:
    if valeur is None:
        return None
    if isinstance(valeur, BaseModel):
        return valeur.model_dump(mode="json")
    if isinstance(valeur, Enum):
        return valeur.value
    if isinstance(valeur, (date, datetime)):
        return valeur.isoformat()
    if isinstance(valeur, dict):
        return {str(cle): _normaliser_json(item) for cle, item in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_normaliser_json(item) for item in valeur]
    if isinstance(valeur, (str, int, float, bool)):
        return valeur
    raise TypeError(f"Valeur non serialisable dans une revision : {type(valeur).__name__}")


def _collecter_source_ids(valeur: Any) -> set[str]:
    trouves: set[str] = set()
    if isinstance(valeur, BaseModel):
        for nom, champ in valeur:
            if nom == "source_ids":
                trouves.update(champ)
            elif nom == "source_id" and champ is not None:
                trouves.add(champ)
            else:
                trouves.update(_collecter_source_ids(champ))
    elif isinstance(valeur, dict):
        for champ in valeur.values():
            trouves.update(_collecter_source_ids(champ))
    elif isinstance(valeur, (list, tuple)):
        for champ in valeur:
            trouves.update(_collecter_source_ids(champ))
    return trouves


def _verifier_ids_existent(
    ids: tuple[str, ...],
    ids_connus: set[str],
    libelle: str,
) -> None:
    inconnus = set(ids) - ids_connus
    if inconnus:
        raise ValueError(
            f"Reference vers un {libelle} absent : " + ", ".join(sorted(inconnus))
        )


def _verifier_transition(
    objet: ObjetLongitudinal,
    changements: dict[str, Any],
    type_revision: TypeRevision,
) -> None:
    champ_etat = "cycle" if isinstance(objet, TacheIntersession) else "etat"
    if (
        type_revision
        in {
            TypeRevision.CHANGEMENT_ETAT,
            TypeRevision.REACTIVATION,
            TypeRevision.REMPLACEMENT,
            TypeRevision.FUSION,
        }
        and champ_etat not in changements
    ):
        raise ValueError("Ce type de revision exige un changement d'etat explicite.")
    if type_revision in {TypeRevision.REMPLACEMENT, TypeRevision.FUSION}:
        if type_revision is TypeRevision.FUSION and not isinstance(
            objet,
            ProblemeSuivi,
        ):
            raise ValueError("La fusion V1 est reservee aux problemes suivis.")
        relations = tuple(changements.get("relations", ()))
        type_relation_attendu = (
            TypeRelationObjet.REMPLACE_PAR
            if type_revision is TypeRevision.REMPLACEMENT
            else TypeRelationObjet.FUSIONNE_DANS
        )
        if not any(
            (
                relation.type_relation
                if isinstance(relation, RelationObjet)
                else TypeRelationObjet(relation["type_relation"])
            )
            is type_relation_attendu
            for relation in relations
        ):
            raise ValueError(
                "Un remplacement ou une fusion exige la relation correspondante."
            )

    if isinstance(objet, ProblemeSuivi) and "etat" in changements:
        nouvel_etat = EtatProbleme(changements["etat"])
        _verifier_transition_dans_table(objet.etat, nouvel_etat, TRANSITIONS_PROBLEME)
        _verifier_type_transition(objet.etat, nouvel_etat, type_revision)
    elif isinstance(objet, ObjectifTherapeutique) and "etat" in changements:
        nouvel_etat = EtatObjectif(changements["etat"])
        _verifier_transition_dans_table(objet.etat, nouvel_etat, TRANSITIONS_OBJECTIF)
        _verifier_type_transition(objet.etat, nouvel_etat, type_revision)
    elif isinstance(objet, ElementAReprendre) and "etat" in changements:
        nouvel_etat = EtatElementAReprendre(changements["etat"])
        _verifier_transition_dans_table(objet.etat, nouvel_etat, TRANSITIONS_ELEMENT)
        _verifier_type_transition(objet.etat, nouvel_etat, type_revision)
    elif isinstance(objet, TacheIntersession) and "cycle" in changements:
        nouveau_cycle = CycleTache(changements["cycle"])
        if nouveau_cycle is objet.cycle:
            raise ValueError("Le cycle de la tache est deja dans cet etat.")
        if (
            objet.cycle is CycleTache.CLOSE
            and nouveau_cycle is CycleTache.OUVERTE
            and type_revision is not TypeRevision.REACTIVATION
        ):
            raise ValueError("La reouverture d'une tache exige une reactivation explicite.")
        if (
            objet.cycle is CycleTache.OUVERTE
            and nouveau_cycle is CycleTache.CLOSE
            and type_revision is not TypeRevision.CHANGEMENT_ETAT
        ):
            raise ValueError("La cloture d'une tache exige un changement d'etat explicite.")


def _verifier_transition_dans_table(
    etat_actuel: Enum,
    nouvel_etat: Enum,
    table: dict[Enum, set[Enum]],
) -> None:
    if nouvel_etat not in table[etat_actuel]:
        raise ValueError(
            f"Transition interdite : {etat_actuel.value} -> {nouvel_etat.value}."
        )


def _verifier_type_transition(
    etat_actuel: Enum,
    nouvel_etat: Enum,
    type_revision: TypeRevision,
) -> None:
    valeurs_reactivation = {"actif", "ouvert"}
    est_reactivation = (
        nouvel_etat.value in valeurs_reactivation
        and etat_actuel.value in {"en_pause", "resolu", "atteint", "planifie"}
    )
    if est_reactivation and type_revision is not TypeRevision.REACTIVATION:
        raise ValueError("Cette transition exige une reactivation explicite.")
    if est_reactivation:
        return
    if nouvel_etat.value == "remplace":
        if type_revision not in {
            TypeRevision.REMPLACEMENT,
            TypeRevision.FUSION,
        }:
            raise ValueError(
                "L'etat remplace exige une revision de remplacement ou de fusion."
            )
        return
    if type_revision is not TypeRevision.CHANGEMENT_ETAT:
        raise ValueError("Un changement d'etat exige un type de revision explicite.")
