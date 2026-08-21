"""Validation clinicien V1 des propositions longitudinales de creation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, ClassVar, Literal
import hashlib
import json
import os

from pydantic import Field, JsonValue, field_validator, model_validator

from modeles_longitudinaux import (
    AssertionClinique,
    FichierPropositionsLongitudinalesV1,
    ModeleStrict,
    PropositionMiseAJour,
    RegistreLongitudinalV1,
    StatutEpistemique,
    TypeObjetLongitudinal,
    TypeOperationProposee,
    ValidationClinique,
    calculer_sha256_json_canonique,
    promouvoir_proposition_creation,
)
from resolution_provenance import (
    ErreurResolutionProvenance,
    SourceResolueV1,
    resoudre_reference_source_v1,
)


SCHEMA_DECISIONS_CLINICIEN = "1.0"
CHAMP_PRINCIPAL_PAR_TYPE = {
    TypeObjetLongitudinal.PROBLEME_SUIVI: "libelle",
    TypeObjetLongitudinal.OBJECTIF_THERAPEUTIQUE: "formulation",
    TypeObjetLongitudinal.TACHE_INTERSESSION: "consigne",
    TypeObjetLongitudinal.ELEMENT_A_REPRENDRE: "contenu",
}
STATUTS_MODIFICATION_AUTORISES = {
    TypeObjetLongitudinal.PROBLEME_SUIVI: frozenset(
        {
            StatutEpistemique.EXPLICITE,
            StatutEpistemique.SYNTHESE_PRUDENTE,
        }
    ),
    TypeObjetLongitudinal.OBJECTIF_THERAPEUTIQUE: frozenset(
        {StatutEpistemique.EXPLICITE}
    ),
    TypeObjetLongitudinal.TACHE_INTERSESSION: frozenset(
        {StatutEpistemique.EXPLICITE}
    ),
    TypeObjetLongitudinal.ELEMENT_A_REPRENDRE: frozenset(
        {
            StatutEpistemique.EXPLICITE,
            StatutEpistemique.SYNTHESE_PRUDENTE,
            StatutEpistemique.INCONNU_A_EXPLORER,
        }
    ),
}


class ErreurValidationClinicien(Exception):
    code: ClassVar[str] = "erreur_validation_clinicien"


class ConfirmationClinicienManquante(ErreurValidationClinicien):
    code = "confirmation_clinicien_manquante"


class PropositionIntrouvable(ErreurValidationClinicien):
    code = "proposition_introuvable"


class PropositionObsolete(ErreurValidationClinicien):
    code = "proposition_obsolete"


class DecisionTerminaleExistante(ErreurValidationClinicien):
    code = "decision_terminale_existante"


class ModificationHorsPerimetre(ErreurValidationClinicien):
    code = "modification_hors_perimetre"


class PromotionImpossible(ErreurValidationClinicien):
    code = "promotion_impossible"


class PersistanceValidationEchouee(ErreurValidationClinicien):
    code = "persistance_validation_echouee"


class TypeDecisionClinicienV1(str, Enum):
    ACCEPTER = "accepter"
    MODIFIER_PUIS_ACCEPTER = "modifier_puis_accepter"
    REFUSER = "refuser"
    DIFFERER = "differer"


class DifferenceDecisionClinicienV1(ModeleStrict):
    champ: str = Field(min_length=1)
    avant: JsonValue
    apres: JsonValue


class DecisionClinicienPropositionV1(ModeleStrict):
    schema_version: Literal["1.0"] = SCHEMA_DECISIONS_CLINICIEN
    dossier_id_pseudonymise: str = Field(min_length=1)
    empreinte_fichier_propositions_sha256: str
    proposition_id: str
    empreinte_proposition_sha256: str
    decision: TypeDecisionClinicienV1
    decide_le: datetime
    validateur_id: str = Field(min_length=1)
    commentaire: str | None = Field(default=None, min_length=1)
    contenu_final: dict[str, JsonValue] | None = None
    statuts_epistemiques_initiaux: tuple[StatutEpistemique, ...]
    statut_epistemique_final: StatutEpistemique | None = None
    differences_clinicien: tuple[DifferenceDecisionClinicienV1, ...] = ()
    confirmation_clinique: Literal[True]
    objet_promu_id: str | None = None
    version_registre_avant: int | None = Field(default=None, ge=1)
    version_registre_apres: int | None = Field(default=None, ge=1)

    @field_validator(
        "empreinte_fichier_propositions_sha256",
        "empreinte_proposition_sha256",
    )
    @classmethod
    def verifier_empreinte(cls, valeur: str) -> str:
        if len(valeur) != 64 or any(c not in "0123456789abcdef" for c in valeur):
            raise ValueError("Empreinte SHA-256 invalide.")
        return valeur

    @field_validator("decide_le")
    @classmethod
    def verifier_date_avec_fuseau(cls, valeur: datetime) -> datetime:
        if valeur.tzinfo is None or valeur.utcoffset() is None:
            raise ValueError("La decision doit inclure un fuseau horaire.")
        return valeur

    @model_validator(mode="after")
    def verifier_coherence_decision(self) -> DecisionClinicienPropositionV1:
        promotion = self.decision in {
            TypeDecisionClinicienV1.ACCEPTER,
            TypeDecisionClinicienV1.MODIFIER_PUIS_ACCEPTER,
        }
        modification = (
            self.decision is TypeDecisionClinicienV1.MODIFIER_PUIS_ACCEPTER
        )
        if promotion:
            if (
                self.objet_promu_id is None
                or self.version_registre_avant is None
                or self.version_registre_apres is None
            ):
                raise ValueError("Une acceptation doit identifier sa promotion.")
            if self.version_registre_apres != self.version_registre_avant + 1:
                raise ValueError("Une promotion doit incrementer le registre une fois.")
        elif any(
            valeur is not None
            for valeur in (
                self.objet_promu_id,
                self.version_registre_avant,
                self.version_registre_apres,
                self.contenu_final,
                self.statut_epistemique_final,
            )
        ) or self.differences_clinicien:
            raise ValueError("Un refus ou report ne contient aucune promotion.")
        if modification:
            if (
                self.contenu_final is None
                or self.statut_epistemique_final is None
                or not self.differences_clinicien
            ):
                raise ValueError("Une modification acceptee doit conserver son avant/apres.")
        elif self.decision is TypeDecisionClinicienV1.ACCEPTER and (
            self.contenu_final is not None or self.differences_clinicien
        ):
            raise ValueError("Une acceptation simple ne modifie pas la proposition.")
        return self

    @property
    def terminale(self) -> bool:
        return self.decision is not TypeDecisionClinicienV1.DIFFERER


class FichierDecisionsClinicienV1(ModeleStrict):
    schema_version: Literal["1.0"] = SCHEMA_DECISIONS_CLINICIEN
    dossier_id_pseudonymise: str = Field(min_length=1)
    empreinte_fichier_propositions_sha256: str
    decisions: tuple[DecisionClinicienPropositionV1, ...] = ()

    @model_validator(mode="after")
    def verifier_integrite(self) -> FichierDecisionsClinicienV1:
        terminales: set[str] = set()
        for decision in self.decisions:
            if decision.dossier_id_pseudonymise != self.dossier_id_pseudonymise:
                raise ValueError("Une decision appartient a un autre patient.")
            if (
                decision.empreinte_fichier_propositions_sha256
                != self.empreinte_fichier_propositions_sha256
            ):
                raise ValueError("Une decision cible un autre fichier de propositions.")
            if decision.terminale:
                if decision.proposition_id in terminales:
                    raise ValueError("Une proposition possede plusieurs decisions terminales.")
                terminales.add(decision.proposition_id)
        return self


class SourceVisibleClinicienV1(ModeleStrict):
    date_seance: str
    categorie: str
    contenu: JsonValue


class VuePropositionClinicienV1(ModeleStrict):
    proposition_id: str
    empreinte_fichier_propositions_sha256: str
    version_registre: int = Field(ge=1)
    type_objet: TypeObjetLongitudinal
    contenu_principal: str
    statuts_epistemiques: tuple[StatutEpistemique, ...]
    statut_action: str
    justification: str
    sources: tuple[SourceVisibleClinicienV1, ...]
    decision_terminale: TypeDecisionClinicienV1 | None = None


class ResultatDecisionClinicienV1(ModeleStrict):
    proposition_originale: PropositionMiseAJour
    decision: DecisionClinicienPropositionV1
    registre: RegistreLongitudinalV1
    objet_promu_id: str | None = None


class ServiceValidationClinicienV1:
    """Service hors ligne; chaque action humaine est un appel explicite."""

    def __init__(
        self,
        dossier_patient: Path,
        chemin_propositions: Path,
        chemin_registre: Path,
        chemin_decisions: Path,
        *,
        remplacer_fichier: Callable[[Path, Path], None] = os.replace,
    ) -> None:
        self.dossier_patient = dossier_patient
        self.chemin_propositions = chemin_propositions
        self.chemin_registre = chemin_registre
        self.chemin_decisions = chemin_decisions
        self._remplacer_fichier = remplacer_fichier

    def lister_propositions(self) -> tuple[VuePropositionClinicienV1, ...]:
        contexte = self._charger_contexte()
        terminales = _index_decisions_terminales(contexte.decisions)
        vues = []
        for proposition in contexte.fichier_propositions.propositions:
            sources = self._resoudre_sources(proposition, contexte.registre)
            vues.append(
                VuePropositionClinicienV1(
                    proposition_id=proposition.id,
                    empreinte_fichier_propositions_sha256=(
                        contexte.empreinte_fichier
                    ),
                    version_registre=contexte.registre.version_registre,
                    type_objet=proposition.type_objet,
                    contenu_principal=_contenu_principal(proposition),
                    statuts_epistemiques=proposition.statuts_epistemiques,
                    statut_action=proposition.statut_action.value,
                    justification=proposition.justification,
                    sources=tuple(
                        SourceVisibleClinicienV1(
                            date_seance=source.date_seance_document.isoformat(),
                            categorie=source.categorie_source,
                            contenu=source.element,
                        )
                        for source in sources
                    ),
                    decision_terminale=(
                        terminales[proposition.id].decision
                        if proposition.id in terminales
                        else None
                    ),
                )
            )
        return tuple(vues)

    def lister_rejets_techniques(self):
        return self._charger_contexte().fichier_propositions.rejets

    def accepter(
        self,
        proposition_id: str,
        *,
        validateur_id: str,
        empreinte_fichier_affichee: str,
        version_registre_affichee: int,
        confirmation_explicite: bool,
        commentaire: str | None = None,
        decide_le: datetime | None = None,
    ) -> ResultatDecisionClinicienV1:
        if not confirmation_explicite:
            raise ConfirmationClinicienManquante(
                "L'acceptation exige une confirmation explicite du clinicien."
            )
        contexte, proposition = self._preparer_decision(
            proposition_id,
            empreinte_fichier_affichee,
            version_registre_affichee,
            revalider_sources=True,
        )
        instant = decide_le or datetime.now(timezone.utc)
        validation = ValidationClinique(
            validateur_id=validateur_id,
            valide_le=instant,
            motif=commentaire or "Acceptation explicite de la proposition systeme.",
        )
        try:
            promotion = promouvoir_proposition_creation(
                contexte.registre,
                proposition,
                validation,
            )
        except (ValueError, TypeError) as erreur:
            raise PromotionImpossible(
                "La proposition ne peut pas etre promue telle quelle."
            ) from erreur
        decision = _creer_decision_promotion(
            contexte,
            proposition,
            TypeDecisionClinicienV1.ACCEPTER,
            validation,
            promotion.objet_cree.id,
            promotion.registre.version_registre,
            commentaire=commentaire,
        )
        decisions = _ajouter_decision(contexte.decisions, decision)
        self._persister_promotion(contexte, promotion.registre, decisions)
        return ResultatDecisionClinicienV1(
            proposition_originale=proposition,
            decision=decision,
            registre=promotion.registre,
            objet_promu_id=promotion.objet_cree.id,
        )

    def modifier_puis_accepter(
        self,
        proposition_id: str,
        *,
        nouvelle_formulation: str,
        statut_epistemique_final: StatutEpistemique,
        validateur_id: str,
        empreinte_fichier_affichee: str,
        version_registre_affichee: int,
        confirmation_sources: bool,
        confirmation_statut_epistemique: bool,
        confirmation_explicite: bool,
        commentaire: str | None = None,
        decide_le: datetime | None = None,
    ) -> ResultatDecisionClinicienV1:
        if not all(
            (
                confirmation_sources,
                confirmation_statut_epistemique,
                confirmation_explicite,
            )
        ):
            raise ConfirmationClinicienManquante(
                "La modification exige les confirmations des sources, du statut et de la promotion."
            )
        contexte, proposition = self._preparer_decision(
            proposition_id,
            empreinte_fichier_affichee,
            version_registre_affichee,
            revalider_sources=True,
        )
        proposition_modifiee, differences, statut_initial = (
            _modifier_formulation_principale(
                proposition,
                nouvelle_formulation,
                statut_epistemique_final,
                contexte.registre,
            )
        )
        instant = decide_le or datetime.now(timezone.utc)
        validation = ValidationClinique(
            validateur_id=validateur_id,
            valide_le=instant,
            motif=commentaire or "Modification et acceptation explicites par le clinicien.",
        )
        try:
            promotion = promouvoir_proposition_creation(
                contexte.registre,
                proposition_modifiee,
                validation,
            )
        except (ValueError, TypeError) as erreur:
            raise PromotionImpossible(
                "La formulation modifiee ne respecte pas le contrat de l'objet."
            ) from erreur
        decision = _creer_decision_promotion(
            contexte,
            proposition,
            TypeDecisionClinicienV1.MODIFIER_PUIS_ACCEPTER,
            validation,
            promotion.objet_cree.id,
            promotion.registre.version_registre,
            commentaire=commentaire,
            contenu_final=proposition_modifiee.contenu_propose,
            statut_final=statut_epistemique_final,
            differences=differences,
            statuts_initiaux=(statut_initial,),
        )
        decisions = _ajouter_decision(contexte.decisions, decision)
        self._persister_promotion(contexte, promotion.registre, decisions)
        return ResultatDecisionClinicienV1(
            proposition_originale=proposition,
            decision=decision,
            registre=promotion.registre,
            objet_promu_id=promotion.objet_cree.id,
        )

    def refuser(
        self,
        proposition_id: str,
        *,
        validateur_id: str,
        empreinte_fichier_affichee: str,
        version_registre_affichee: int,
        confirmation_explicite: bool,
        commentaire: str | None = None,
        decide_le: datetime | None = None,
    ) -> ResultatDecisionClinicienV1:
        return self._decision_sans_promotion(
            TypeDecisionClinicienV1.REFUSER,
            proposition_id,
            validateur_id=validateur_id,
            empreinte_fichier_affichee=empreinte_fichier_affichee,
            version_registre_affichee=version_registre_affichee,
            confirmation_explicite=confirmation_explicite,
            commentaire=commentaire,
            decide_le=decide_le,
        )

    def differer(
        self,
        proposition_id: str,
        *,
        validateur_id: str,
        empreinte_fichier_affichee: str,
        version_registre_affichee: int,
        confirmation_explicite: bool,
        commentaire: str | None = None,
        decide_le: datetime | None = None,
    ) -> ResultatDecisionClinicienV1:
        return self._decision_sans_promotion(
            TypeDecisionClinicienV1.DIFFERER,
            proposition_id,
            validateur_id=validateur_id,
            empreinte_fichier_affichee=empreinte_fichier_affichee,
            version_registre_affichee=version_registre_affichee,
            confirmation_explicite=confirmation_explicite,
            commentaire=commentaire,
            decide_le=decide_le,
        )

    def _decision_sans_promotion(
        self,
        type_decision: TypeDecisionClinicienV1,
        proposition_id: str,
        *,
        validateur_id: str,
        empreinte_fichier_affichee: str,
        version_registre_affichee: int,
        confirmation_explicite: bool,
        commentaire: str | None,
        decide_le: datetime | None,
    ) -> ResultatDecisionClinicienV1:
        if not confirmation_explicite:
            raise ConfirmationClinicienManquante(
                "La decision exige une confirmation explicite du clinicien."
            )
        contexte, proposition = self._preparer_decision(
            proposition_id,
            empreinte_fichier_affichee,
            version_registre_affichee,
            revalider_sources=False,
        )
        instant = decide_le or datetime.now(timezone.utc)
        decision = DecisionClinicienPropositionV1(
            dossier_id_pseudonymise=contexte.registre.dossier_id_pseudonymise,
            empreinte_fichier_propositions_sha256=contexte.empreinte_fichier,
            proposition_id=proposition.id,
            empreinte_proposition_sha256=_empreinte_proposition(proposition),
            decision=type_decision,
            decide_le=instant,
            validateur_id=validateur_id,
            commentaire=commentaire,
            statuts_epistemiques_initiaux=proposition.statuts_epistemiques,
            confirmation_clinique=True,
        )
        decisions = _ajouter_decision(contexte.decisions, decision)
        self._persister_decisions(contexte, decisions)
        return ResultatDecisionClinicienV1(
            proposition_originale=proposition,
            decision=decision,
            registre=contexte.registre,
        )

    def _preparer_decision(
        self,
        proposition_id: str,
        empreinte_fichier_affichee: str,
        version_registre_affichee: int,
        *,
        revalider_sources: bool,
    ) -> tuple[_ContexteValidation, PropositionMiseAJour]:
        contexte = self._charger_contexte()
        if contexte.empreinte_fichier != empreinte_fichier_affichee:
            raise PropositionObsolete(
                "Le fichier de propositions a change depuis son affichage."
            )
        if contexte.registre.version_registre != version_registre_affichee:
            raise PropositionObsolete(
                "Le registre a change depuis l'affichage de la proposition."
            )
        proposition = _trouver_proposition(
            contexte.fichier_propositions,
            proposition_id,
        )
        if proposition.operation is not TypeOperationProposee.CREATION:
            raise PromotionImpossible(
                "La validation clinicien V1 ne traite que les creations."
            )
        terminale = _index_decisions_terminales(contexte.decisions).get(
            proposition.id
        )
        if terminale is not None:
            raise DecisionTerminaleExistante(
                f"La proposition possede deja une decision terminale : {terminale.decision.value}."
            )
        if revalider_sources:
            self._resoudre_sources(proposition, contexte.registre)
        return contexte, proposition

    def _charger_contexte(self) -> _ContexteValidation:
        octets_propositions = self.chemin_propositions.read_bytes()
        try:
            fichier = FichierPropositionsLongitudinalesV1.model_validate_json(
                octets_propositions
            )
            octets_registre = self.chemin_registre.read_bytes()
            registre = RegistreLongitudinalV1.model_validate_json(octets_registre)
        except Exception as erreur:
            raise PropositionObsolete(
                "Les propositions ou le registre ne peuvent plus etre revalides."
            ) from erreur
        empreinte = hashlib.sha256(octets_propositions).hexdigest()
        if (
            fichier.dossier_id_pseudonymise != registre.dossier_id_pseudonymise
            or self.dossier_patient.name != registre.dossier_id_pseudonymise
        ):
            raise PropositionObsolete(
                "Les propositions, le registre et le dossier patient divergent."
            )
        decisions, octets_decisions = _charger_decisions(
            self.chemin_decisions,
            registre.dossier_id_pseudonymise,
            empreinte,
        )
        return _ContexteValidation(
            fichier_propositions=fichier,
            registre=registre,
            decisions=decisions,
            empreinte_fichier=empreinte,
            octets_propositions=octets_propositions,
            octets_registre=octets_registre,
            octets_decisions=octets_decisions,
        )

    def _resoudre_sources(
        self,
        proposition: PropositionMiseAJour,
        registre: RegistreLongitudinalV1,
    ) -> tuple[SourceResolueV1, ...]:
        index = {reference.id: reference for reference in registre.references_sources}
        resolues = []
        for source_id in proposition.source_ids:
            reference = index.get(source_id)
            if reference is None:
                raise PropositionObsolete(
                    "Une source de la proposition est absente du registre."
                )
            try:
                resolue = resoudre_reference_source_v1(
                    reference,
                    self.dossier_patient,
                    registre.dossier_id_pseudonymise,
                )
            except ErreurResolutionProvenance as erreur:
                raise PropositionObsolete(
                    "Cette proposition doit etre regeneree ou reevaluee car sa provenance a change."
                ) from erreur
            resolues.append(resolue)
        return tuple(resolues)

    def _persister_promotion(
        self,
        contexte: _ContexteValidation,
        registre: RegistreLongitudinalV1,
        decisions: FichierDecisionsClinicienV1,
    ) -> None:
        _persister_deux_modeles(
            self.chemin_registre,
            registre,
            contexte.octets_registre,
            self.chemin_decisions,
            decisions,
            contexte.octets_decisions,
            self._remplacer_fichier,
        )

    def _persister_decisions(
        self,
        contexte: _ContexteValidation,
        decisions: FichierDecisionsClinicienV1,
    ) -> None:
        _persister_un_modele(
            self.chemin_decisions,
            decisions,
            contexte.octets_decisions,
            self._remplacer_fichier,
        )


class _ContexteValidation(ModeleStrict):
    fichier_propositions: FichierPropositionsLongitudinalesV1
    registre: RegistreLongitudinalV1
    decisions: FichierDecisionsClinicienV1
    empreinte_fichier: str
    octets_propositions: bytes
    octets_registre: bytes
    octets_decisions: bytes | None


def charger_decisions(chemin: Path) -> FichierDecisionsClinicienV1:
    return FichierDecisionsClinicienV1.model_validate_json(chemin.read_bytes())


def enregistrer_decisions(
    decisions: FichierDecisionsClinicienV1,
    chemin: Path,
) -> None:
    _persister_un_modele(chemin, decisions, _lire_si_existe(chemin), os.replace)


def _charger_decisions(
    chemin: Path,
    dossier_id: str,
    empreinte_fichier: str,
) -> tuple[FichierDecisionsClinicienV1, bytes | None]:
    octets = _lire_si_existe(chemin)
    if octets is None:
        return (
            FichierDecisionsClinicienV1(
                dossier_id_pseudonymise=dossier_id,
                empreinte_fichier_propositions_sha256=empreinte_fichier,
            ),
            None,
        )
    try:
        decisions = FichierDecisionsClinicienV1.model_validate_json(octets)
    except Exception as erreur:
        raise PropositionObsolete(
            "Le fichier des decisions clinicien est invalide."
        ) from erreur
    if (
        decisions.dossier_id_pseudonymise != dossier_id
        or decisions.empreinte_fichier_propositions_sha256 != empreinte_fichier
    ):
        raise PropositionObsolete(
            "Le fichier des decisions cible une autre version des propositions."
        )
    return decisions, octets


def _trouver_proposition(
    fichier: FichierPropositionsLongitudinalesV1,
    proposition_id: str,
) -> PropositionMiseAJour:
    for proposition in fichier.propositions:
        if proposition.id == proposition_id:
            return proposition
    raise PropositionIntrouvable(
        "La proposition demandee n'est pas disponible a la validation clinique."
    )


def _index_decisions_terminales(
    fichier: FichierDecisionsClinicienV1,
) -> dict[str, DecisionClinicienPropositionV1]:
    return {
        decision.proposition_id: decision
        for decision in fichier.decisions
        if decision.terminale
    }


def _contenu_principal(proposition: PropositionMiseAJour) -> str:
    champ = CHAMP_PRINCIPAL_PAR_TYPE[proposition.type_objet]
    assertion = proposition.contenu_propose.get(champ)
    if not isinstance(assertion, dict) or not isinstance(assertion.get("contenu"), str):
        raise PromotionImpossible(
            "Le contenu clinique principal de la proposition est invalide."
        )
    return assertion["contenu"]


def _statut_principal(proposition: PropositionMiseAJour) -> StatutEpistemique:
    champ = CHAMP_PRINCIPAL_PAR_TYPE[proposition.type_objet]
    assertion = AssertionClinique.model_validate(proposition.contenu_propose[champ])
    return assertion.statut_epistemique


def _modifier_formulation_principale(
    proposition: PropositionMiseAJour,
    nouvelle_formulation: str,
    statut_final: StatutEpistemique,
    registre: RegistreLongitudinalV1,
) -> tuple[
    PropositionMiseAJour,
    tuple[DifferenceDecisionClinicienV1, ...],
    StatutEpistemique,
]:
    if not isinstance(nouvelle_formulation, str) or not nouvelle_formulation.strip():
        raise ModificationHorsPerimetre(
            "La modification V1 exige une formulation clinique non vide."
        )
    if statut_final not in STATUTS_MODIFICATION_AUTORISES[proposition.type_objet]:
        raise ModificationHorsPerimetre(
            "Ce statut epistemique est interdit pour ce type d'objet en V1."
        )
    champ = CHAMP_PRINCIPAL_PAR_TYPE[proposition.type_objet]
    contenu = deepcopy(proposition.contenu_propose)
    try:
        assertion_initiale = AssertionClinique.model_validate(contenu[champ])
    except Exception as erreur:
        raise ModificationHorsPerimetre(
            "La proposition ne contient pas l'assertion modifiable attendue."
        ) from erreur
    dates = [
        reference.date_seance
        for reference in registre.references_sources
        if reference.id in assertion_initiale.source_ids
    ]
    periode = assertion_initiale.periode_couverte
    if statut_final is StatutEpistemique.SYNTHESE_PRUDENTE and periode is None:
        if not dates:
            raise ModificationHorsPerimetre(
                "Une synthese prudente modifiee exige des dates sources."
            )
        periode = {"date_debut": min(dates), "date_fin": max(dates)}
    assertion_finale = AssertionClinique(
        contenu=nouvelle_formulation.strip(),
        statut_epistemique=statut_final,
        source_ids=assertion_initiale.source_ids,
        periode_couverte=periode,
    )
    if assertion_finale == assertion_initiale:
        raise ModificationHorsPerimetre(
            "La modification ne change ni la formulation ni son statut."
        )
    contenu[champ] = assertion_finale.model_dump(mode="json")
    statuts = tuple(
        dict.fromkeys(
            statut_final if statut is assertion_initiale.statut_epistemique else statut
            for statut in proposition.statuts_epistemiques
        )
    )
    modifiee = PropositionMiseAJour.model_validate(
        {
            **proposition.model_dump(),
            "contenu_propose": contenu,
            "statuts_epistemiques": statuts,
        }
    )
    differences = (
        DifferenceDecisionClinicienV1(
            champ=f"{champ}.contenu",
            avant=assertion_initiale.contenu,
            apres=assertion_finale.contenu,
        ),
    )
    if statut_final is not assertion_initiale.statut_epistemique:
        differences = (
            *differences,
            DifferenceDecisionClinicienV1(
                champ=f"{champ}.statut_epistemique",
                avant=assertion_initiale.statut_epistemique.value,
                apres=statut_final.value,
            ),
        )
    return modifiee, differences, assertion_initiale.statut_epistemique


def _creer_decision_promotion(
    contexte: _ContexteValidation,
    proposition: PropositionMiseAJour,
    type_decision: TypeDecisionClinicienV1,
    validation: ValidationClinique,
    objet_id: str,
    version_registre_apres: int,
    *,
    commentaire: str | None,
    contenu_final: dict[str, JsonValue] | None = None,
    statut_final: StatutEpistemique | None = None,
    differences: tuple[DifferenceDecisionClinicienV1, ...] = (),
    statuts_initiaux: tuple[StatutEpistemique, ...] | None = None,
) -> DecisionClinicienPropositionV1:
    return DecisionClinicienPropositionV1(
        dossier_id_pseudonymise=contexte.registre.dossier_id_pseudonymise,
        empreinte_fichier_propositions_sha256=contexte.empreinte_fichier,
        proposition_id=proposition.id,
        empreinte_proposition_sha256=_empreinte_proposition(proposition),
        decision=type_decision,
        decide_le=validation.valide_le,
        validateur_id=validation.validateur_id,
        commentaire=commentaire,
        contenu_final=contenu_final,
        statuts_epistemiques_initiaux=(
            statuts_initiaux or proposition.statuts_epistemiques
        ),
        statut_epistemique_final=statut_final,
        differences_clinicien=differences,
        confirmation_clinique=True,
        objet_promu_id=objet_id,
        version_registre_avant=contexte.registre.version_registre,
        version_registre_apres=version_registre_apres,
    )


def _empreinte_proposition(proposition: PropositionMiseAJour) -> str:
    return calculer_sha256_json_canonique(proposition.model_dump(mode="json"))


def _ajouter_decision(
    fichier: FichierDecisionsClinicienV1,
    decision: DecisionClinicienPropositionV1,
) -> FichierDecisionsClinicienV1:
    return FichierDecisionsClinicienV1.model_validate(
        {
            **fichier.model_dump(),
            "decisions": (*fichier.decisions, decision),
        }
    )


def _serialiser_modele(modele: ModeleStrict) -> bytes:
    return (
        json.dumps(
            modele.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _lire_si_existe(chemin: Path) -> bytes | None:
    try:
        return chemin.read_bytes()
    except FileNotFoundError:
        return None


def _verifier_inchange(chemin: Path, attendu: bytes | None) -> None:
    if _lire_si_existe(chemin) != attendu:
        raise PropositionObsolete(
            f"Le fichier {chemin.name} a change avant la persistance."
        )


def _ecrire_temporaire(chemin: Path, contenu: bytes) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    with temporaire.open("wb") as flux:
        flux.write(contenu)
        flux.flush()
        os.fsync(flux.fileno())
    return temporaire


def _restaurer(chemin: Path, contenu: bytes | None) -> None:
    if contenu is None:
        chemin.unlink(missing_ok=True)
        return
    temporaire = _ecrire_temporaire(chemin, contenu)
    os.replace(temporaire, chemin)


def _persister_un_modele(
    chemin: Path,
    modele: ModeleStrict,
    contenu_initial: bytes | None,
    remplacer: Callable[[Path, Path], None],
) -> None:
    _verifier_inchange(chemin, contenu_initial)
    temporaire = _ecrire_temporaire(chemin, _serialiser_modele(modele))
    try:
        remplacer(temporaire, chemin)
    except Exception as erreur:
        temporaire.unlink(missing_ok=True)
        raise PersistanceValidationEchouee(
            "La decision n'a pas pu etre enregistree."
        ) from erreur


def _persister_deux_modeles(
    chemin_registre: Path,
    registre: RegistreLongitudinalV1,
    registre_initial: bytes,
    chemin_decisions: Path,
    decisions: FichierDecisionsClinicienV1,
    decisions_initiales: bytes | None,
    remplacer: Callable[[Path, Path], None],
) -> None:
    _verifier_inchange(chemin_registre, registre_initial)
    _verifier_inchange(chemin_decisions, decisions_initiales)
    temporaire_registre = _ecrire_temporaire(
        chemin_registre,
        _serialiser_modele(registre),
    )
    temporaire_decisions = _ecrire_temporaire(
        chemin_decisions,
        _serialiser_modele(decisions),
    )
    registre_remplace = False
    try:
        remplacer(temporaire_registre, chemin_registre)
        registre_remplace = True
        remplacer(temporaire_decisions, chemin_decisions)
    except Exception as erreur:
        temporaire_registre.unlink(missing_ok=True)
        temporaire_decisions.unlink(missing_ok=True)
        try:
            if registre_remplace:
                _restaurer(chemin_registre, registre_initial)
            _restaurer(chemin_decisions, decisions_initiales)
        except Exception as restauration:
            raise PersistanceValidationEchouee(
                "Echec de persistance et de restauration de la validation."
            ) from restauration
        raise PersistanceValidationEchouee(
            "La promotion a ete annulee avant toute persistance complete."
        ) from erreur
