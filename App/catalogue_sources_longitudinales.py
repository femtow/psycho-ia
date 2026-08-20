"""Catalogue deterministe des sources cliniques V2 d'un patient."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import ClassVar
import json
import re

from pydantic import Field, JsonValue, field_validator, model_validator

from modeles_longitudinaux import (
    ModeleStrict,
    ReferenceSourceV1,
    RelationSupport,
    SHA256_RE,
    calculer_sha256_json_canonique,
    calculer_sha256_octets,
    creer_reference_source_v1,
)
from resolution_provenance import (
    CATEGORIES_CLINIQUES_V2,
    DocumentCliniqueInvalide,
    ErreurResolutionProvenance,
    resoudre_reference_source_v1,
    valider_document_clinique_v2,
)


DOSSIER_DONNEES_CLINIQUES = "donnees_cliniques"
CATEGORIES_ORDONNEES = (
    "faits_rapportes",
    "emotions",
    "cognitions",
    "comportements",
    "evitements",
    "interventions",
    "taches_interseances",
    "elements_incertains",
)
SOURCE_CATALOGUE_RE = re.compile(r"^source_[0-9]{4,}$")


class ErreurCatalogueSources(Exception):
    code: ClassVar[str] = "erreur_catalogue_sources"


class DossierPatientCatalogueInvalide(ErreurCatalogueSources):
    code = "dossier_patient_catalogue_invalide"


class AucunDocumentCliniqueValide(ErreurCatalogueSources):
    code = "aucun_document_clinique_valide"


class DocumentCatalogueInvalide(ErreurCatalogueSources):
    code = "document_catalogue_invalide"


class ReferenceCatalogueInvalide(ErreurCatalogueSources):
    code = "reference_catalogue_invalide"


class SourceCatalogueInconnue(ErreurCatalogueSources):
    code = "source_catalogue_inconnue"


class EntreeCatalogueSourceV1(ModeleStrict):
    source_id: str
    date_seance: date
    categorie: str = Field(min_length=1)
    contenu: JsonValue
    reference: ReferenceSourceV1

    @field_validator("source_id")
    @classmethod
    def verifier_source_id(cls, valeur: str) -> str:
        if not SOURCE_CATALOGUE_RE.fullmatch(valeur):
            raise ValueError("Identifiant court de catalogue invalide.")
        return valeur

    @model_validator(mode="after")
    def verifier_coherence_reference(self) -> EntreeCatalogueSourceV1:
        if self.reference.date_seance != self.date_seance:
            raise ValueError("La date de catalogue differe de la reference.")
        if self.reference.categorie_source != self.categorie:
            raise ValueError("La categorie de catalogue differe de la reference.")
        return self

    def vue_terra(self) -> dict[str, JsonValue]:
        return {
            "source_id": self.source_id,
            "date_seance": self.date_seance.isoformat(),
            "categorie": self.categorie,
            "contenu": self.contenu,
        }


class CatalogueSourcesPatientV1(ModeleStrict):
    dossier_id_pseudonymise: str = Field(min_length=1)
    date_coupure: date
    entrees: tuple[EntreeCatalogueSourceV1, ...]
    empreinte_sources_sha256: str

    @field_validator("empreinte_sources_sha256")
    @classmethod
    def verifier_empreinte_sources(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Empreinte SHA-256 du catalogue invalide.")
        return valeur

    @model_validator(mode="after")
    def verifier_integrite(self) -> CatalogueSourcesPatientV1:
        source_ids = [entree.source_id for entree in self.entrees]
        reference_ids = [entree.reference.id for entree in self.entrees]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Les identifiants courts doivent etre uniques.")
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("Les references techniques doivent etre uniques.")
        for entree in self.entrees:
            if (
                entree.reference.dossier_id_pseudonymise
                != self.dossier_id_pseudonymise
            ):
                raise ValueError("Une source du catalogue appartient a un autre patient.")
            if entree.date_seance > self.date_coupure:
                raise ValueError("Une source depasse la date de coupure du catalogue.")
        return self

    def vue_terra(self) -> dict[str, JsonValue]:
        """Retourne la seule vue autorisee a sortir du catalogue interne."""

        return {
            "dossier_id_pseudonymise": self.dossier_id_pseudonymise,
            "date_coupure": self.date_coupure.isoformat(),
            "sources": [entree.vue_terra() for entree in self.entrees],
        }

    def entree_pour(self, source_id: str) -> EntreeCatalogueSourceV1:
        for entree in self.entrees:
            if entree.source_id == source_id:
                return entree
        raise SourceCatalogueInconnue(
            f"Identifiant de catalogue inconnu : {source_id}"
        )


def construire_catalogue_sources_patient(
    dossier_patient: Path,
    dossier_id_pseudonymise: str,
) -> CatalogueSourcesPatientV1:
    """Construit et resout toutes les sources avant de retourner le catalogue."""

    racine = _valider_dossier_patient(
        dossier_patient,
        dossier_id_pseudonymise,
    )
    dossier_clinique = racine / DOSSIER_DONNEES_CLINIQUES
    if not dossier_clinique.is_dir():
        raise AucunDocumentCliniqueValide(
            "Le dossier de donnees cliniques est absent."
        )

    documents = []
    for chemin in sorted(dossier_clinique.glob("*.json"), key=lambda p: p.name):
        document, contenu_brut = _lire_document_catalogue(chemin)
        try:
            date_seance = valider_document_clinique_v2(document)
        except DocumentCliniqueInvalide as erreur:
            raise DocumentCatalogueInvalide(
                f"Document clinique V2 invalide : {chemin.name}"
            ) from erreur
        documents.append((date_seance, chemin, document, contenu_brut))

    if not documents:
        raise AucunDocumentCliniqueValide(
            "Aucun JSON clinique V2 n'est disponible pour ce patient."
        )

    entrees: list[EntreeCatalogueSourceV1] = []
    for date_seance, chemin, document, contenu_brut in sorted(
        documents,
        key=lambda item: (item[0], item[1].name),
    ):
        empreinte_document = calculer_sha256_octets(contenu_brut)
        document_relatif = f"{DOSSIER_DONNEES_CLINIQUES}/{chemin.name}"
        for categorie in CATEGORIES_ORDONNEES:
            if categorie not in CATEGORIES_CLINIQUES_V2:
                raise DocumentCatalogueInvalide(
                    f"Categorie V2 non autorisee : {categorie}"
                )
            elements = document[categorie]
            for index, element in enumerate(elements):
                source_id = f"source_{len(entrees) + 1:04d}"
                reference = creer_reference_source_v1(
                    dossier_id_pseudonymise=dossier_id_pseudonymise,
                    document=document_relatif,
                    document_sha256=empreinte_document,
                    date_seance=date_seance,
                    categorie_source=categorie,
                    json_pointer=f"/{categorie}/{index}",
                    element_sha256=calculer_sha256_json_canonique(element),
                    relation_support=RelationSupport.DIRECT,
                    extraction_schema_version="2.0",
                )
                try:
                    resoudre_reference_source_v1(
                        reference,
                        racine,
                        dossier_id_pseudonymise,
                    )
                except ErreurResolutionProvenance as erreur:
                    raise ReferenceCatalogueInvalide(
                        f"Reference non resoluble pour {source_id}."
                    ) from erreur
                entrees.append(
                    EntreeCatalogueSourceV1(
                        source_id=source_id,
                        date_seance=date_seance,
                        categorie=categorie,
                        contenu=element,
                        reference=reference,
                    )
                )

    empreinte = calculer_sha256_json_canonique(
        [
            entree.reference.model_dump(mode="json")
            for entree in entrees
        ]
    )
    return CatalogueSourcesPatientV1(
        dossier_id_pseudonymise=dossier_id_pseudonymise,
        date_coupure=max(document[0] for document in documents),
        entrees=tuple(entrees),
        empreinte_sources_sha256=empreinte,
    )


def verifier_catalogue_resoluble(
    catalogue: CatalogueSourcesPatientV1,
    dossier_patient: Path,
) -> None:
    """Revalide le catalogue juste avant ou apres un appel Terra."""

    for entree in catalogue.entrees:
        try:
            resoudre_reference_source_v1(
                entree.reference,
                dossier_patient,
                catalogue.dossier_id_pseudonymise,
            )
        except ErreurResolutionProvenance as erreur:
            raise ReferenceCatalogueInvalide(
                f"Reference devenue invalide : {entree.source_id}."
            ) from erreur


def _valider_dossier_patient(
    dossier_patient: Path,
    dossier_id_pseudonymise: str,
) -> Path:
    try:
        racine = dossier_patient.resolve(strict=True)
    except (FileNotFoundError, OSError) as erreur:
        raise DossierPatientCatalogueInvalide(
            "Le dossier patient ne peut pas etre resolu."
        ) from erreur
    if not racine.is_dir() or racine.name != dossier_id_pseudonymise:
        raise DossierPatientCatalogueInvalide(
            "Le dossier patient ne correspond pas a l'identifiant attendu."
        )
    return racine


def _lire_document_catalogue(
    chemin: Path,
) -> tuple[dict[str, JsonValue], bytes]:
    try:
        contenu_brut = chemin.read_bytes()
        document = json.loads(
            contenu_brut.decode("utf-8-sig"),
            parse_constant=_refuser_constante_json,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as erreur:
        raise DocumentCatalogueInvalide(
            f"Document JSON illisible ou invalide : {chemin.name}"
        ) from erreur
    if not isinstance(document, dict):
        raise DocumentCatalogueInvalide(
            f"Le document {chemin.name} doit etre un objet JSON."
        )
    return document, contenu_brut


def _refuser_constante_json(valeur: str) -> None:
    raise ValueError(f"Constante JSON non standard interdite : {valeur}")
