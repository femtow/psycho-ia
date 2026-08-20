"""Generation Terra isolee de propositions longitudinales V1."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import Field, JsonValue, ValidationError, field_validator, model_validator

from catalogue_sources_longitudinales import (
    CatalogueSourcesPatientV1,
    EntreeCatalogueSourceV1,
    SOURCE_CATALOGUE_RE,
    SourceCatalogueInconnue,
    verifier_catalogue_resoluble,
)
from modeles_longitudinaux import (
    AssertionClinique,
    CycleTache,
    DifferenceProposee,
    EtatElementAReprendre,
    EtatObjectif,
    EtatProbleme,
    FichierPropositionsLongitudinalesV1,
    ModeleStrict,
    PeriodeCouverte,
    PropositionMiseAJour,
    RejetPropositionLongitudinale,
    RegistreLongitudinalV1,
    StatutDecisionTache,
    StatutEpistemique,
    StatutResultatTache,
    TypeObjetLongitudinal,
    TypeObjectif,
    TypeOperationProposee,
    calculer_sha256_json_canonique,
    generer_identifiant_proposition,
)
from resolution_provenance import (
    ErreurResolutionProvenance,
    resoudre_reference_source_v1,
)


MODEL_PROPOSITIONS_LONGITUDINALES = "gpt-5.6-terra"
REASONING_EFFORT_PROPOSITIONS = "low"
MAX_OUTPUT_TOKENS_PROPOSITIONS = 6000
VERSION_PROMPT_PROPOSITIONS = "1.1"
VERSION_GENERATEUR_PROPOSITIONS = "1.1"

OPERATIONS_AVEC_LIEN = frozenset(
    {
        TypeOperationProposee.RELATION,
        TypeOperationProposee.FUSION,
        TypeOperationProposee.REMPLACEMENT,
    }
)
CATEGORIES_PROBLEME = frozenset(
    {
        "faits_rapportes",
        "emotions",
        "cognitions",
        "comportements",
        "evitements",
    }
)
CATEGORIES_RESULTAT_TACHE = CATEGORIES_PROBLEME


PROMPT_SYSTEME_PROPOSITIONS = """\
Tu produis uniquement des propositions de mise a jour d'une memoire clinique
longitudinale de base. Tu ne conceptualises pas le cas et tu ne proposes ni
diagnostic, ni mecanisme causal, ni intervention, ni plan de traitement, ni
agenda de seance.

Autorite et provenance :
- Les seules preuves autorisees sont les entrees du catalogue JSON V2 fourni.
- Cite uniquement leurs identifiants courts source_####.
- Ne retourne jamais chemin, nom de fichier, hash, JSON Pointer, index technique
  ou ReferenceSourceV1.
- Chaque proposition doit citer au moins une source réellement pertinente.
- Une non-mention ne prouve ni absence, ni resolution, ni echec.
- Conserve les contradictions et les incertitudes; ne corrige jamais un passage
  [illisible] ou [mot incertain : ...].

Frontiere d'autorite :
- Toute sortie reste proposition_systeme et brouillon_genere.
- Ne prends aucune decision clinique et ne valide aucun objet.
- Retourne une liste vide lorsqu'aucune proposition n'est suffisamment soutenue.

Regles des objets :
- probleme_suivi : propose seulement une difficulte qui merite un suivi dans le
  temps. Justifie-le par une repetition, une persistance, un impact fonctionnel,
  une importance clinique explicite ou un lien explicite avec la demande, un
  objectif ou le traitement. Une emotion isolee, un evenement ponctuel ou un
  contenu vague ne suffit pas. Prefere l'absence de proposition si le caractere
  longitudinal n'est pas soutenu. Un regroupement de plusieurs donnees est
  synthese_prudente, meme si chaque donnee est explicite. Une formulation reprise
  directement d'une seule source peut rester explicite. Aucun diagnostic,
  priorite ou causalite inventes.
- objectif_therapeutique : le schema de seance V2 ne contient pas d'objectif
  negocie distinct. Toute direction plausible est donc seulement
  synthese_prudente et reste a confirmer. Ne transforme jamais une tache, une
  serie de taches, une intervention ou une difficulte seule en objectif.
- tache_intersession : exige au moins une source de categorie
  taches_interseances. Elle reste proposee_documentee et son resultat reste
  resultat_non_documente sauf source clinique distincte qui documente directement
  la realisation, la realisation partielle, la non-realisation ou un resultat.
  Cite alors la consigne et les sources de resultat. Une intervention possible
  n'est pas une tache et une consigne seule ne prouve jamais sa realisation.
- element_a_reprendre : seulement un sujet explicitement differe ou une
  incertitude importante a explorer. Une question generee ou un champ simplement
  manquant n'en est pas un.

Operations :
- Sans registre courant, retourne uniquement creation ou aucune proposition.
- Avec registre, creation, modification, changement_etat, relation, fusion et
  remplacement sont possibles, mais chaque cible doit reprendre exactement un
  identifiant et une version fournis.
- Ne ferme, ne resout, n'abandonne et ne remplace jamais un objet sur la seule
  base de sa non-mention.
- Ne fusionne pas des propositions par simple similarite textuelle.

Statuts epistemiques :
- N'utilise jamais hypothese_clinique dans cette brique.
- Une source elements_incertains ne peut alimenter qu'un element_a_reprendre avec
  statut inconnu_a_explorer.
- Une tache documentee est explicite.
- Un objectif propose depuis ce schema est synthese_prudente.

Respecte exactement le schema structure de sortie. N'ajoute aucun champ.
"""


class ErreurGenerationPropositions(Exception):
    code: ClassVar[str] = "erreur_generation_propositions"

    def __init__(self, message: str, reponse: Any | None = None) -> None:
        super().__init__(message)
        self.reponse = reponse


class ReponseTerraInvalide(ErreurGenerationPropositions):
    code = "reponse_terra_invalide"


class ValidationPostTerraEchouee(ErreurGenerationPropositions):
    code = "validation_post_terra_echouee"


class RegistreGenerationIncoherent(ErreurGenerationPropositions):
    code = "registre_generation_incoherent"


class PropositionTerraBase(ModeleStrict):
    operation: TypeOperationProposee
    objet_cible_id: str | None = None
    version_objet_cible: int | None = Field(default=None, ge=1)
    objet_lie_id: str | None = None
    version_objet_lie: int | None = Field(default=None, ge=1)
    type_objet_lie: TypeObjetLongitudinal | None = None
    statut_epistemique: StatutEpistemique
    source_ids: tuple[str, ...] = Field(min_length=1)
    justification: str = Field(min_length=1)

    @field_validator("source_ids")
    @classmethod
    def verifier_sources_courtes(
        cls,
        valeurs: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(valeurs) != len(set(valeurs)):
            raise ValueError("Une proposition ne doit pas dupliquer une source.")
        for valeur in valeurs:
            if not SOURCE_CATALOGUE_RE.fullmatch(valeur):
                raise ValueError("Identifiant court de source invalide.")
        return valeurs

    @model_validator(mode="after")
    def verifier_operation(self) -> PropositionTerraBase:
        cible_complete = (
            self.objet_cible_id is not None
            and self.version_objet_cible is not None
        )
        lien_complet = (
            self.objet_lie_id is not None
            and self.version_objet_lie is not None
            and self.type_objet_lie is not None
        )
        if self.operation is TypeOperationProposee.CREATION:
            if cible_complete or lien_complet:
                raise ValueError("Une creation ne cible ni ne lie un objet existant.")
            if any(
                valeur is not None
                for valeur in (
                    self.objet_cible_id,
                    self.version_objet_cible,
                    self.objet_lie_id,
                    self.version_objet_lie,
                    self.type_objet_lie,
                )
            ):
                raise ValueError("Une creation contient une cible incomplete.")
            return self
        if not cible_complete:
            raise ValueError("Une operation de mise a jour exige une cible complete.")
        if self.operation in OPERATIONS_AVEC_LIEN:
            if not lien_complet:
                raise ValueError("Cette operation exige un objet lie complet.")
        elif any(
            valeur is not None
            for valeur in (
                self.objet_lie_id,
                self.version_objet_lie,
                self.type_objet_lie,
            )
        ):
            raise ValueError("Cette operation n'autorise pas d'objet lie.")
        return self


class PropositionProblemeTerra(PropositionTerraBase):
    type_objet: Literal["probleme_suivi"] = "probleme_suivi"
    libelle: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    etat_propose: EtatProbleme | None = None

    @model_validator(mode="after")
    def verifier_contenu_probleme(self) -> PropositionProblemeTerra:
        if self.operation is TypeOperationProposee.CREATION and self.libelle is None:
            raise ValueError("Une creation de probleme exige un libelle.")
        if self.operation is TypeOperationProposee.MODIFICATION and not (
            self.libelle or self.description
        ):
            raise ValueError("Une modification de probleme exige un contenu.")
        if (
            self.operation is TypeOperationProposee.CHANGEMENT_ETAT
            and self.etat_propose is None
        ):
            raise ValueError("Un changement d'etat exige le nouvel etat.")
        return self


class PropositionObjectifTerra(PropositionTerraBase):
    type_objet: Literal["objectif_therapeutique"] = "objectif_therapeutique"
    formulation: str | None = Field(default=None, min_length=1)
    type_objectif: TypeObjectif | None = None
    probleme_ids: tuple[str, ...] = ()
    etat_propose: EtatObjectif | None = None

    @model_validator(mode="after")
    def verifier_contenu_objectif(self) -> PropositionObjectifTerra:
        if self.operation is TypeOperationProposee.CREATION and (
            self.formulation is None or self.type_objectif is None
        ):
            raise ValueError(
                "Une creation d'objectif exige formulation et type."
            )
        if self.operation is TypeOperationProposee.MODIFICATION and not (
            self.formulation or self.type_objectif
        ):
            raise ValueError("Une modification d'objectif exige un contenu.")
        if (
            self.operation is TypeOperationProposee.CHANGEMENT_ETAT
            and self.etat_propose is None
        ):
            raise ValueError("Un changement d'etat exige le nouvel etat.")
        return self


class PropositionTacheTerra(PropositionTerraBase):
    type_objet: Literal["tache_intersession"] = "tache_intersession"
    consigne: str | None = Field(default=None, min_length=1)
    probleme_ids: tuple[str, ...] = ()
    objectif_ids: tuple[str, ...] = ()
    date_proposition_ou_accord: date | None = None
    cycle_propose: CycleTache | None = None
    statut_decision_propose: StatutDecisionTache | None = None
    statut_resultat_propose: StatutResultatTache | None = None
    resultat_documente: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def verifier_contenu_tache(self) -> PropositionTacheTerra:
        if self.operation is TypeOperationProposee.CREATION and (
            self.consigne is None or self.date_proposition_ou_accord is None
        ):
            raise ValueError("Une creation de tache exige consigne et date.")
        if self.operation is TypeOperationProposee.MODIFICATION and not (
            self.consigne or self.date_proposition_ou_accord
        ):
            raise ValueError("Une modification de tache exige un contenu.")
        if self.operation is TypeOperationProposee.CHANGEMENT_ETAT and not any(
            valeur is not None
            for valeur in (
                self.cycle_propose,
                self.statut_decision_propose,
                self.statut_resultat_propose,
                self.resultat_documente,
            )
        ):
            raise ValueError("Un changement de tache exige un statut ou resultat.")
        return self


class PropositionElementTerra(PropositionTerraBase):
    type_objet: Literal["element_a_reprendre"] = "element_a_reprendre"
    contenu: str | None = Field(default=None, min_length=1)
    raison_report: str | None = Field(default=None, min_length=1)
    source_cible_id: str | None = None
    etat_propose: EtatElementAReprendre | None = None

    @model_validator(mode="after")
    def verifier_contenu_element(self) -> PropositionElementTerra:
        if self.operation is TypeOperationProposee.CREATION and self.contenu is None:
            raise ValueError("Une creation d'element exige un contenu.")
        if self.operation is TypeOperationProposee.MODIFICATION and not (
            self.contenu or self.raison_report
        ):
            raise ValueError("Une modification d'element exige un contenu.")
        if (
            self.operation is TypeOperationProposee.CHANGEMENT_ETAT
            and self.etat_propose is None
        ):
            raise ValueError("Un changement d'etat exige le nouvel etat.")
        if self.source_cible_id is not None and (
            self.source_cible_id not in self.source_ids
        ):
            raise ValueError("La source cible doit aussi soutenir la proposition.")
        return self


PropositionTerra = (
    PropositionProblemeTerra
    | PropositionObjectifTerra
    | PropositionTacheTerra
    | PropositionElementTerra
)


class SortieTerraPropositionsV1(ModeleStrict):
    problemes_suivis: tuple[PropositionProblemeTerra, ...] = ()
    objectifs_therapeutiques: tuple[PropositionObjectifTerra, ...] = ()
    taches_intersession: tuple[PropositionTacheTerra, ...] = ()
    elements_a_reprendre: tuple[PropositionElementTerra, ...] = ()

    def toutes_les_propositions(self) -> tuple[PropositionTerra, ...]:
        return (
            *self.problemes_suivis,
            *self.objectifs_therapeutiques,
            *self.taches_intersession,
            *self.elements_a_reprendre,
        )


def generer_propositions_longitudinales(
    client: Any,
    catalogue: CatalogueSourcesPatientV1,
    dossier_patient: Path,
    registre: RegistreLongitudinalV1 | None = None,
    cree_le: datetime | None = None,
) -> tuple[FichierPropositionsLongitudinalesV1, Any]:
    """Appelle Terra puis applique tous les controles deterministes."""

    verifier_catalogue_resoluble(catalogue, dossier_patient)
    _verifier_registre(registre, catalogue)
    prompt_utilisateur = _construire_prompt_utilisateur(catalogue, registre)
    reponse = client.responses.parse(
        model=MODEL_PROPOSITIONS_LONGITUDINALES,
        reasoning={"effort": REASONING_EFFORT_PROPOSITIONS},
        store=False,
        max_output_tokens=MAX_OUTPUT_TOKENS_PROPOSITIONS,
        input=[
            {"role": "system", "content": PROMPT_SYSTEME_PROPOSITIONS},
            {"role": "user", "content": prompt_utilisateur},
        ],
        text_format=SortieTerraPropositionsV1,
    )
    if getattr(reponse, "status", None) == "incomplete":
        details = getattr(reponse, "incomplete_details", None)
        raise ReponseTerraInvalide(
            f"Reponse Terra incomplete. Details : {details}",
            reponse,
        )
    sortie = getattr(reponse, "output_parsed", None)
    if sortie is None:
        raise ReponseTerraInvalide(
            "Terra n'a pas retourne de sortie structuree valide.",
            reponse,
        )
    try:
        fichier = construire_fichier_propositions(
            sortie,
            catalogue,
            dossier_patient,
            registre=registre,
            cree_le=cree_le,
        )
    except ErreurGenerationPropositions as erreur:
        erreur.reponse = reponse
        raise
    except Exception as erreur:
        raise ValidationPostTerraEchouee(
            "La validation deterministe post-Terra a echoue.",
            reponse,
        ) from erreur
    return fichier, reponse


def construire_fichier_propositions(
    sortie: SortieTerraPropositionsV1,
    catalogue: CatalogueSourcesPatientV1,
    dossier_patient: Path,
    registre: RegistreLongitudinalV1 | None = None,
    cree_le: datetime | None = None,
) -> FichierPropositionsLongitudinalesV1:
    """Convertit les identifiants courts en provenances resolues."""

    verifier_catalogue_resoluble(catalogue, dossier_patient)
    _verifier_registre(registre, catalogue)
    empreinte_registre_avant = _empreinte_registre(registre)
    date_creation = cree_le or datetime.now(timezone.utc)
    if date_creation.tzinfo is None or date_creation.utcoffset() is None:
        raise ValidationPostTerraEchouee(
            "La date de generation doit inclure un fuseau horaire."
        )
    index_registre = _index_objets_registre(registre)
    empreinte_generation = calculer_empreinte_generation(catalogue, registre)
    prompt_sha256 = calculer_sha256_json_canonique(PROMPT_SYSTEME_PROPOSITIONS)

    propositions = []
    rejets = []
    for position, brute_initiale in enumerate(
        sortie.toutes_les_propositions(),
        start=1,
    ):
        try:
            brute = type(brute_initiale).model_validate(
                brute_initiale.model_dump(mode="python")
            )
            entrees = _resoudre_sources_proposition(
                brute,
                catalogue,
                dossier_patient,
            )
            _verifier_regles_cliniques(brute, entrees)
            cible = _verifier_cibles_registre(brute, index_registre, registre)
            contenu = _construire_contenu_propose(
                brute,
                entrees,
                index_registre,
            )
            differences = _construire_differences(brute, contenu, cible)
            propositions.append(
                PropositionMiseAJour(
                    id=generer_identifiant_proposition(),
                    type_objet=brute.type_objet,
                    operation=brute.operation,
                    objet_cible_id=brute.objet_cible_id,
                    version_objet_cible=brute.version_objet_cible,
                    contenu_propose=contenu,
                    differences=differences,
                    justification=brute.justification,
                    source_ids=tuple(entree.reference.id for entree in entrees),
                    statuts_epistemiques=(brute.statut_epistemique,),
                    cree_le=date_creation,
                    modele=MODEL_PROPOSITIONS_LONGITUDINALES,
                    version_prompt=VERSION_PROMPT_PROPOSITIONS,
                    version_generateur=VERSION_GENERATEUR_PROPOSITIONS,
                    prompt_sha256=prompt_sha256,
                    empreinte_sources_sha256=empreinte_generation,
                )
            )
        except ValidationPostTerraEchouee as erreur:
            rejets.append(
                _creer_rejet_proposition(position, brute_initiale, erreur)
            )
        except ValidationError:
            rejets.append(
                _creer_rejet_proposition(
                    position,
                    brute_initiale,
                    ValidationPostTerraEchouee(
                        "La proposition ne respecte pas le schema deterministe."
                    ),
                )
            )

    if _empreinte_registre(registre) != empreinte_registre_avant:
        raise RegistreGenerationIncoherent(
            "Le registre a ete modifie pendant la generation."
        )
    return FichierPropositionsLongitudinalesV1(
        dossier_id_pseudonymise=catalogue.dossier_id_pseudonymise,
        propositions=tuple(propositions),
        rejets=tuple(rejets),
    )


def _creer_rejet_proposition(
    position: int,
    brute: PropositionTerra,
    erreur: ValidationPostTerraEchouee,
) -> RejetPropositionLongitudinale:
    return RejetPropositionLongitudinale(
        position_sortie=position,
        type_objet=brute.type_objet,
        operation=brute.operation,
        contenu_principal=_contenu_principal(brute),
        source_ids_courts=brute.source_ids,
        code=erreur.code,
        motif=str(erreur),
    )


def calculer_empreinte_generation(
    catalogue: CatalogueSourcesPatientV1,
    registre: RegistreLongitudinalV1 | None,
) -> str:
    return calculer_sha256_json_canonique(
        {
            "schema_propositions": "1.1",
            "version_generateur": VERSION_GENERATEUR_PROPOSITIONS,
            "version_prompt": VERSION_PROMPT_PROPOSITIONS,
            "modele": MODEL_PROPOSITIONS_LONGITUDINALES,
            "prompt_sha256": calculer_sha256_json_canonique(
                PROMPT_SYSTEME_PROPOSITIONS
            ),
            "catalogue_sources_sha256": catalogue.empreinte_sources_sha256,
            "registre_depart": (
                registre.model_dump(mode="json") if registre is not None else None
            ),
        }
    )


def _construire_prompt_utilisateur(
    catalogue: CatalogueSourcesPatientV1,
    registre: RegistreLongitudinalV1 | None,
) -> str:
    donnees = {
        "catalogue_clinique": catalogue.vue_terra(),
        "registre_courant": _vue_registre_terra(registre),
    }
    return (
        "Voici les seules donnees autorisees. Le champ registre_courant vaut "
        "null lorsqu'aucun registre valide n'existe.\n\n"
        + calculer_json_prompt(donnees)
    )


def calculer_json_prompt(valeur: JsonValue) -> str:
    import json

    return json.dumps(
        valeur,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    )


def _vue_registre_terra(
    registre: RegistreLongitudinalV1 | None,
) -> JsonValue:
    if registre is None:
        return None

    def assertion(valeur: AssertionClinique | None) -> JsonValue:
        if valeur is None:
            return None
        return {
            "contenu": valeur.contenu,
            "statut_epistemique": valeur.statut_epistemique.value,
            "periode_couverte": (
                valeur.periode_couverte.model_dump(mode="json")
                if valeur.periode_couverte
                else None
            ),
        }

    return {
        "dossier_id_pseudonymise": registre.dossier_id_pseudonymise,
        "version_registre": registre.version_registre,
        "date_coupure": registre.date_coupure.isoformat(),
        "problemes_suivis": [
            {
                "id": objet.id,
                "version": objet.version,
                "etat": objet.etat.value,
                "libelle": assertion(objet.libelle),
                "description": assertion(objet.description),
            }
            for objet in registre.problemes_suivis
        ],
        "objectifs_therapeutiques": [
            {
                "id": objet.id,
                "version": objet.version,
                "etat": objet.etat.value,
                "type_objectif": objet.type_objectif.value,
                "formulation": assertion(objet.formulation),
                "probleme_ids": list(objet.probleme_ids),
            }
            for objet in registre.objectifs_therapeutiques
        ],
        "taches_intersession": [
            {
                "id": objet.id,
                "version": objet.version,
                "cycle": objet.cycle.value,
                "statut_decision": objet.statut_decision.value,
                "statut_resultat": objet.statut_resultat.value,
                "consigne": assertion(objet.consigne),
                "probleme_ids": list(objet.probleme_ids),
                "objectif_ids": list(objet.objectif_ids),
            }
            for objet in registre.taches_intersession
        ],
        "elements_a_reprendre": [
            {
                "id": objet.id,
                "version": objet.version,
                "etat": objet.etat.value,
                "contenu": assertion(objet.contenu),
            }
            for objet in registre.elements_a_reprendre
        ],
    }


def _resoudre_sources_proposition(
    brute: PropositionTerra,
    catalogue: CatalogueSourcesPatientV1,
    dossier_patient: Path,
) -> tuple[EntreeCatalogueSourceV1, ...]:
    entrees = []
    for source_id in brute.source_ids:
        try:
            entree = catalogue.entree_pour(source_id)
        except SourceCatalogueInconnue as erreur:
            raise ValidationPostTerraEchouee(str(erreur)) from erreur
        if (
            entree.reference.dossier_id_pseudonymise
            != catalogue.dossier_id_pseudonymise
        ):
            raise ValidationPostTerraEchouee(
                "Une source Terra appartient a un autre patient."
            )
        try:
            resoudre_reference_source_v1(
                entree.reference,
                dossier_patient,
                catalogue.dossier_id_pseudonymise,
            )
        except ErreurResolutionProvenance as erreur:
            raise ValidationPostTerraEchouee(
                f"Source Terra non resoluble : {source_id}"
            ) from erreur
        entrees.append(entree)
    return tuple(entrees)


def _verifier_regles_cliniques(
    brute: PropositionTerra,
    entrees: tuple[EntreeCatalogueSourceV1, ...],
) -> None:
    categories = {entree.categorie for entree in entrees}
    if "elements_incertains" in categories:
        if not isinstance(brute, PropositionElementTerra) or (
            brute.statut_epistemique
            is not StatutEpistemique.INCONNU_A_EXPLORER
        ):
            raise ValidationPostTerraEchouee(
                "Une source incertaine ne peut devenir un fait certain."
            )
    if isinstance(brute, PropositionProblemeTerra):
        if not categories.issubset(CATEGORIES_PROBLEME):
            raise ValidationPostTerraEchouee(
                "Un probleme doit etre soutenu par des donnees cliniques directes."
            )
        if (
            len(entrees) > 1
            and brute.statut_epistemique is StatutEpistemique.EXPLICITE
        ):
            raise ValidationPostTerraEchouee(
                "Un regroupement de plusieurs sources doit rester une synthese prudente."
            )
        if brute.statut_epistemique not in {
            StatutEpistemique.EXPLICITE,
            StatutEpistemique.SYNTHESE_PRUDENTE,
        }:
            raise ValidationPostTerraEchouee(
                "Statut epistemique interdit pour un probleme."
            )
    elif isinstance(brute, PropositionObjectifTerra):
        if brute.statut_epistemique is not StatutEpistemique.SYNTHESE_PRUDENTE:
            raise ValidationPostTerraEchouee(
                "Un objectif issu du schema V2 doit rester une synthese prudente."
            )
        if not categories.intersection(CATEGORIES_PROBLEME):
            raise ValidationPostTerraEchouee(
                "Une intervention ou tache seule ne peut devenir un objectif."
            )
    elif isinstance(brute, PropositionTacheTerra):
        entrees_consigne = tuple(
            entree
            for entree in entrees
            if entree.categorie == "taches_interseances"
        )
        if not entrees_consigne:
            raise ValidationPostTerraEchouee(
                "Une tache exige une source taches_interseances."
            )
        if brute.statut_epistemique is not StatutEpistemique.EXPLICITE:
            raise ValidationPostTerraEchouee(
                "Une tache documentee doit rester explicite."
            )
        dates_sources = {entree.date_seance for entree in entrees_consigne}
        if (
            brute.date_proposition_ou_accord is not None
            and brute.date_proposition_ou_accord not in dates_sources
        ):
            raise ValidationPostTerraEchouee(
                "La date de proposition de tache n'est pas une date source."
            )
        if (
            brute.operation is TypeOperationProposee.CREATION
            and brute.statut_decision_propose
            not in {None, StatutDecisionTache.PROPOSEE_DOCUMENTEE}
        ):
            raise ValidationPostTerraEchouee(
                "Une creation de tache V2 reste proposee_documentee."
            )
        _verifier_sources_resultat_tache(brute, entrees)
    elif isinstance(brute, PropositionElementTerra):
        autorises = {
            StatutEpistemique.EXPLICITE,
            StatutEpistemique.SYNTHESE_PRUDENTE,
            StatutEpistemique.INCONNU_A_EXPLORER,
        }
        if brute.statut_epistemique not in autorises:
            raise ValidationPostTerraEchouee(
                "Statut epistemique interdit pour un element a reprendre."
            )
    if brute.statut_epistemique is StatutEpistemique.HYPOTHESE_CLINIQUE:
        raise ValidationPostTerraEchouee(
            "Les hypotheses cliniques sont hors perimetre de cette brique."
        )
    _verifier_transition_sensible(brute, categories)


def _verifier_sources_resultat_tache(
    brute: PropositionTacheTerra,
    entrees: tuple[EntreeCatalogueSourceV1, ...],
) -> None:
    statut = brute.statut_resultat_propose
    resultat_documente = brute.resultat_documente
    resultat_atteste = statut not in {
        None,
        StatutResultatTache.RESULTAT_NON_DOCUMENTE,
    }
    entrees_resultat = tuple(
        entree
        for entree in entrees
        if entree.categorie in CATEGORIES_RESULTAT_TACHE
    )

    if statut is StatutResultatTache.RESULTAT_NON_DOCUMENTE:
        if resultat_documente is not None:
            raise ValidationPostTerraEchouee(
                "Un resultat non documente ne peut contenir de resultat."
            )
    elif resultat_atteste and resultat_documente is None:
        raise ValidationPostTerraEchouee(
            "Un statut de resultat exige un resultat documente."
        )
    elif statut is None and resultat_documente is not None:
        raise ValidationPostTerraEchouee(
            "Un resultat documente exige un statut de resultat."
        )

    if (resultat_atteste or resultat_documente is not None) and not entrees_resultat:
        raise ValidationPostTerraEchouee(
            "Un resultat de tache exige une source clinique directe distincte de la consigne."
        )
    if (
        brute.cycle_propose is CycleTache.CLOSE
        and not resultat_atteste
    ):
        raise ValidationPostTerraEchouee(
            "Une tache ne peut etre close sans resultat documente."
        )


def _verifier_transition_sensible(
    brute: PropositionTerra,
    categories: set[str],
) -> None:
    """Exige une trace explicite pour toute fermeture ou decision sensible."""

    if brute.operation is not TypeOperationProposee.CHANGEMENT_ETAT:
        return
    terminal = False
    if isinstance(brute, PropositionProblemeTerra):
        terminal = brute.etat_propose in {
            EtatProbleme.RESOLU,
            EtatProbleme.ABANDONNE,
            EtatProbleme.REMPLACE,
        }
    elif isinstance(brute, PropositionObjectifTerra):
        terminal = brute.etat_propose in {
            EtatObjectif.ATTEINT,
            EtatObjectif.ABANDONNE,
            EtatObjectif.REMPLACE,
        }
    elif isinstance(brute, PropositionElementTerra):
        terminal = brute.etat_propose in {
            EtatElementAReprendre.RESOLU,
            EtatElementAReprendre.ABANDONNE,
            EtatElementAReprendre.REMPLACE,
        }
    elif isinstance(brute, PropositionTacheTerra):
        terminal = (
            brute.cycle_propose is CycleTache.CLOSE
            or brute.statut_resultat_propose
            not in {None, StatutResultatTache.RESULTAT_NON_DOCUMENTE}
        )
        if (
            brute.statut_decision_propose is StatutDecisionTache.CONVENUE
            and "faits_rapportes" not in categories
        ):
            raise ValidationPostTerraEchouee(
                "Une tache ne peut devenir convenue sans accord explicite source."
            )
    if terminal and (
        brute.statut_epistemique is not StatutEpistemique.EXPLICITE
        or not categories.intersection({"faits_rapportes", "comportements"})
    ):
        raise ValidationPostTerraEchouee(
            "Une fermeture ou resolution exige une donnee explicite source."
        )


def _verifier_cibles_registre(
    brute: PropositionTerra,
    index_registre: dict[str, Any],
    registre: RegistreLongitudinalV1 | None,
) -> Any | None:
    if brute.operation is TypeOperationProposee.CREATION:
        return None
    if registre is None:
        raise ValidationPostTerraEchouee(
            "Une mise a jour est impossible sans registre courant."
        )
    cible = index_registre.get(brute.objet_cible_id)
    if cible is None:
        raise ValidationPostTerraEchouee("Objet cible absent du registre.")
    if cible.version != brute.version_objet_cible:
        raise ValidationPostTerraEchouee("Version de cible obsolete ou inconnue.")
    if cible.type_objet != brute.type_objet:
        raise ValidationPostTerraEchouee("Type de l'objet cible incoherent.")
    if brute.operation in OPERATIONS_AVEC_LIEN:
        lie = index_registre.get(brute.objet_lie_id)
        if lie is None or lie.version != brute.version_objet_lie:
            raise ValidationPostTerraEchouee("Objet lie absent ou de version invalide.")
        if lie.type_objet != brute.type_objet_lie.value:
            raise ValidationPostTerraEchouee("Type de l'objet lie incoherent.")
        if brute.operation in {
            TypeOperationProposee.FUSION,
            TypeOperationProposee.REMPLACEMENT,
        } and lie.type_objet != cible.type_objet:
            raise ValidationPostTerraEchouee(
                "Fusion et remplacement exigent deux objets de meme type."
            )
    return cible


def _construire_contenu_propose(
    brute: PropositionTerra,
    entrees: tuple[EntreeCatalogueSourceV1, ...],
    index_registre: dict[str, Any],
) -> dict[str, JsonValue]:
    source_ids = tuple(entree.reference.id for entree in entrees)
    assertion = _creer_assertion(
        _contenu_principal(brute),
        brute.statut_epistemique,
        source_ids,
        entrees,
    )
    if brute.operation in OPERATIONS_AVEC_LIEN:
        return {
            "operation_relationnelle": brute.operation.value,
            "objet_lie_id": brute.objet_lie_id,
            "version_objet_lie": brute.version_objet_lie,
            "type_objet_lie": brute.type_objet_lie.value,
        }

    if isinstance(brute, PropositionProblemeTerra):
        if brute.operation is TypeOperationProposee.CHANGEMENT_ETAT:
            return {"etat": brute.etat_propose.value}
        contenu: dict[str, JsonValue] = {}
        if brute.libelle is not None:
            contenu["libelle"] = assertion.model_dump(mode="json")
        if brute.description is not None:
            contenu["description"] = _creer_assertion(
                brute.description,
                brute.statut_epistemique,
                source_ids,
                entrees,
            ).model_dump(mode="json")
        if brute.operation is TypeOperationProposee.CREATION:
            return {
                "etat": "candidat",
                "libelle": contenu["libelle"],
                "description": contenu.get("description"),
                "contexte": [],
                "impact": [],
                "priorite": None,
                "objectif_ids": [],
                "tache_ids": [],
                "relations": [],
            }
        return contenu

    if isinstance(brute, PropositionObjectifTerra):
        _verifier_ids_objets(brute.probleme_ids, index_registre, "probleme_suivi")
        if brute.operation is TypeOperationProposee.CHANGEMENT_ETAT:
            return {"etat": brute.etat_propose.value}
        contenu = {}
        if brute.formulation is not None:
            contenu["formulation"] = assertion.model_dump(mode="json")
        if brute.type_objectif is not None:
            contenu["type_objectif"] = brute.type_objectif.value
        if brute.probleme_ids:
            contenu["probleme_ids"] = list(brute.probleme_ids)
        if brute.operation is TypeOperationProposee.CREATION:
            return {
                "etat": "candidat",
                "type_objectif": contenu["type_objectif"],
                "formulation": contenu["formulation"],
                "probleme_ids": list(brute.probleme_ids),
                "indicateurs_atteinte": [],
                "importance": None,
                "priorite": None,
                "horizon": None,
                "relations": [],
            }
        return contenu

    if isinstance(brute, PropositionTacheTerra):
        _verifier_ids_objets(brute.probleme_ids, index_registre, "probleme_suivi")
        _verifier_ids_objets(
            brute.objectif_ids,
            index_registre,
            "objectif_therapeutique",
        )
        entrees_consigne = tuple(
            entree
            for entree in entrees
            if entree.categorie == "taches_interseances"
        )
        entrees_resultat = tuple(
            entree
            for entree in entrees
            if entree.categorie in CATEGORIES_RESULTAT_TACHE
        )
        source_ids_consigne = tuple(
            entree.reference.id for entree in entrees_consigne
        )
        source_ids_resultat = tuple(
            entree.reference.id for entree in entrees_resultat
        )
        if brute.operation is TypeOperationProposee.CHANGEMENT_ETAT:
            contenu = {}
            if brute.cycle_propose is not None:
                contenu["cycle"] = brute.cycle_propose.value
            if brute.statut_decision_propose is not None:
                contenu["statut_decision"] = brute.statut_decision_propose.value
            if brute.statut_resultat_propose is not None:
                contenu["statut_resultat"] = brute.statut_resultat_propose.value
            if brute.resultat_documente is not None:
                contenu["resultat_documente"] = _creer_assertion(
                    brute.resultat_documente,
                    StatutEpistemique.EXPLICITE,
                    source_ids_resultat,
                    entrees_resultat,
                ).model_dump(mode="json")
            _verifier_coherence_resultat_tache(contenu)
            return contenu
        contenu = {}
        if brute.consigne is not None:
            contenu["consigne"] = _creer_assertion(
                brute.consigne,
                StatutEpistemique.EXPLICITE,
                source_ids_consigne,
                entrees_consigne,
            ).model_dump(mode="json")
        if brute.date_proposition_ou_accord is not None:
            contenu["date_proposition_ou_accord"] = (
                brute.date_proposition_ou_accord.isoformat()
            )
        if brute.operation is TypeOperationProposee.CREATION:
            statut_resultat = (
                brute.statut_resultat_propose
                or StatutResultatTache.RESULTAT_NON_DOCUMENTE
            )
            resultat_documente = None
            if brute.resultat_documente is not None:
                resultat_documente = _creer_assertion(
                    brute.resultat_documente,
                    StatutEpistemique.EXPLICITE,
                    source_ids_resultat,
                    entrees_resultat,
                ).model_dump(mode="json")
            creation = {
                "cycle": (
                    brute.cycle_propose or CycleTache.OUVERTE
                ).value,
                "statut_decision": "proposee_documentee",
                "statut_resultat": statut_resultat.value,
                "consigne": contenu["consigne"],
                "probleme_ids": list(brute.probleme_ids),
                "objectif_ids": list(brute.objectif_ids),
                "rationale_partage": None,
                "parametres": [],
                "conditions_realisation": [],
                "date_proposition_ou_accord": contenu[
                    "date_proposition_ou_accord"
                ],
                "echeance": None,
                "resultat_documente": resultat_documente,
                "apprentissages": [],
                "effets_indesirables": [],
                "obstacles": [],
                "decision_suite": None,
                "relations": [],
            }
            _verifier_coherence_resultat_tache(creation)
            return creation
        return contenu

    if isinstance(brute, PropositionElementTerra):
        if brute.operation is TypeOperationProposee.CHANGEMENT_ETAT:
            return {"etat": brute.etat_propose.value}
        contenu = {}
        if brute.contenu is not None:
            contenu["contenu"] = assertion.model_dump(mode="json")
        if brute.raison_report is not None:
            contenu["raison_report"] = _creer_assertion(
                brute.raison_report,
                brute.statut_epistemique,
                source_ids,
                entrees,
            ).model_dump(mode="json")
        if brute.operation is TypeOperationProposee.CREATION:
            source_cible = brute.source_cible_id
            if source_cible is None and (
                brute.statut_epistemique is StatutEpistemique.INCONNU_A_EXPLORER
            ):
                source_cible = brute.source_ids[0]
            cible = None
            if source_cible is not None:
                reference = next(
                    entree.reference
                    for entree in entrees
                    if entree.source_id == source_cible
                )
                cible = {
                    "type_cible": "source",
                    "objet_id": None,
                    "version_objet": None,
                    "source_id": reference.id,
                }
            return {
                "etat": "candidat",
                "contenu": contenu["contenu"],
                "cible": cible,
                "raison_report": contenu.get("raison_report"),
                "priorite": None,
                "echeance": None,
                "relations": [],
            }
        return contenu
    raise ValidationPostTerraEchouee("Type de proposition Terra inconnu.")


def _contenu_principal(brute: PropositionTerra) -> str:
    if isinstance(brute, PropositionProblemeTerra):
        return brute.libelle or brute.description or brute.justification
    if isinstance(brute, PropositionObjectifTerra):
        return brute.formulation or brute.justification
    if isinstance(brute, PropositionTacheTerra):
        return brute.consigne or brute.resultat_documente or brute.justification
    if isinstance(brute, PropositionElementTerra):
        return brute.contenu or brute.raison_report or brute.justification
    raise ValidationPostTerraEchouee("Type de contenu Terra inconnu.")


def _creer_assertion(
    contenu: str,
    statut: StatutEpistemique,
    source_ids: tuple[str, ...],
    entrees: tuple[EntreeCatalogueSourceV1, ...],
) -> AssertionClinique:
    periode = None
    if statut is StatutEpistemique.SYNTHESE_PRUDENTE:
        dates = [entree.date_seance for entree in entrees]
        periode = PeriodeCouverte(
            date_debut=min(dates),
            date_fin=max(dates),
        )
    return AssertionClinique(
        contenu=contenu,
        statut_epistemique=statut,
        source_ids=source_ids,
        periode_couverte=periode,
    )


def _construire_differences(
    brute: PropositionTerra,
    contenu: dict[str, JsonValue],
    cible: Any | None,
) -> tuple[DifferenceProposee, ...]:
    if brute.operation is TypeOperationProposee.CREATION:
        return (
            DifferenceProposee(
                champ="creation",
                valeur_actuelle=None,
                valeur_proposee=contenu,
            ),
        )
    actuel = cible.model_dump(mode="json")
    return tuple(
        DifferenceProposee(
            champ=champ,
            valeur_actuelle=actuel.get(champ),
            valeur_proposee=valeur,
        )
        for champ, valeur in contenu.items()
    )


def _verifier_ids_objets(
    ids: tuple[str, ...],
    index_registre: dict[str, Any],
    type_attendu: str,
) -> None:
    for identifiant in ids:
        objet = index_registre.get(identifiant)
        if objet is None or objet.type_objet != type_attendu:
            raise ValidationPostTerraEchouee(
                f"Lien vers objet longitudinal inconnu : {identifiant}"
            )


def _verifier_coherence_resultat_tache(
    contenu: dict[str, JsonValue],
) -> None:
    statut = contenu.get("statut_resultat")
    resultat = contenu.get("resultat_documente")
    if statut is None:
        return
    if statut == "resultat_non_documente" and resultat is not None:
        raise ValidationPostTerraEchouee(
            "Un resultat non documente ne peut contenir de resultat."
        )
    if statut != "resultat_non_documente" and resultat is None:
        raise ValidationPostTerraEchouee(
            "Un statut de resultat exige une assertion documentee."
        )


def _verifier_registre(
    registre: RegistreLongitudinalV1 | None,
    catalogue: CatalogueSourcesPatientV1,
) -> None:
    if registre is None:
        return
    if registre.dossier_id_pseudonymise != catalogue.dossier_id_pseudonymise:
        raise RegistreGenerationIncoherent(
            "Le registre et le catalogue appartiennent a des patients differents."
        )
    if registre.date_coupure > catalogue.date_coupure:
        raise RegistreGenerationIncoherent(
            "Le registre depasse la date de coupure du catalogue."
        )


def _index_objets_registre(
    registre: RegistreLongitudinalV1 | None,
) -> dict[str, Any]:
    if registre is None:
        return {}
    return {objet.id: objet for objet in registre.tous_les_objets()}


def _empreinte_registre(
    registre: RegistreLongitudinalV1 | None,
) -> str | None:
    if registre is None:
        return None
    return calculer_sha256_json_canonique(registre.model_dump(mode="json"))
