"""Resolution sure d'une ReferenceSourceV1 contre un JSON clinique V2."""

from __future__ import annotations

from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import ClassVar, Literal
import json
import re

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from modeles_longitudinaux import (
    ModeleStrict,
    ReferenceSourceV1,
    RelationSupport,
    calculer_sha256_json_canonique,
    calculer_sha256_octets,
)


DOSSIER_SOURCES_CLINIQUES = "donnees_cliniques"
SCHEMA_CLINIQUE_V2 = "2.0"


class ErreurResolutionProvenance(Exception):
    code: ClassVar[str] = "erreur_resolution_provenance"


class SourceAbsente(ErreurResolutionProvenance):
    code = "source_absente"


class PatientIncoherent(ErreurResolutionProvenance):
    code = "patient_incoherent"


class CheminSourceInterdit(ErreurResolutionProvenance):
    code = "chemin_source_interdit"


class DocumentCliniqueInvalide(ErreurResolutionProvenance):
    code = "document_clinique_invalide"


class SchemaCliniqueIncompatible(ErreurResolutionProvenance):
    code = "schema_clinique_incompatible"


class PointeurSourceInvalide(ErreurResolutionProvenance):
    code = "pointeur_source_invalide"


class ElementSourceIntrouvable(ErreurResolutionProvenance):
    code = "element_source_introuvable"


class CategorieSourceIntrouvable(ElementSourceIntrouvable):
    code = "categorie_source_introuvable"


class IndexSourceHorsLimites(ElementSourceIntrouvable):
    code = "index_source_hors_limites"


class EmpreinteDocumentIncorrecte(ErreurResolutionProvenance):
    code = "empreinte_document_incorrecte"


class EmpreinteElementIncorrecte(ErreurResolutionProvenance):
    code = "empreinte_element_incorrecte"


class _ModeleDocumentV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _ElementContextualiseV2(_ModeleDocumentV2):
    contenu: str
    contexte: str | None


class _EmotionContextualiseeV2(_ModeleDocumentV2):
    contenu: str
    contexte: str | None
    intensite: str | None


class _CognitionContextualiseeV2(_ModeleDocumentV2):
    contenu: str
    contexte: str | None
    referent_contextuel: str | None
    referent_explicitement_identifie: bool | None


class _DocumentCliniqueV2(_ModeleDocumentV2):
    schema_version: Literal["2.0"]
    date_seance: date | None
    faits_rapportes: list[str]
    emotions: list[_EmotionContextualiseeV2]
    cognitions: list[_CognitionContextualiseeV2]
    comportements: list[_ElementContextualiseV2]
    evitements: list[_ElementContextualiseV2]
    interventions: list[str]
    taches_interseances: list[str]
    elements_incertains: list[str]


CATEGORIES_CLINIQUES_V2 = frozenset(
    {
        "faits_rapportes",
        "emotions",
        "cognitions",
        "comportements",
        "evitements",
        "interventions",
        "taches_interseances",
        "elements_incertains",
    }
)


class SourceResolueV1(ModeleStrict):
    reference_id: str
    dossier_id_pseudonymise: str
    document: str
    schema_version_document: Literal["2.0"]
    date_seance_document: date
    categorie_source: str
    json_pointer: str
    element: JsonValue
    document_sha256: str
    element_sha256: str
    relation_support: RelationSupport


def resoudre_reference_source_v1(
    reference: ReferenceSourceV1,
    dossier_patient: Path,
    dossier_id_attendu: str,
) -> SourceResolueV1:
    """Valide et resout exactement une reference, sans aucune reparation."""

    if reference.dossier_id_pseudonymise != dossier_id_attendu:
        raise PatientIncoherent(
            "L'identifiant de la reference ne correspond pas au patient attendu."
        )

    racine_patient = _resoudre_racine_patient(
        dossier_patient,
        dossier_id_attendu,
    )
    chemin_source = _resoudre_chemin_source(
        reference.document,
        racine_patient,
    )
    contenu_brut = _lire_document(chemin_source)
    document = _decoder_document_json(contenu_brut)
    document_valide = _valider_document_clinique(
        document,
        reference,
    )

    empreinte_document = calculer_sha256_octets(contenu_brut)
    if empreinte_document != reference.document_sha256:
        raise EmpreinteDocumentIncorrecte(
            "L'empreinte du document clinique ne correspond plus a la reference."
        )

    element = _resoudre_pointeur_element(document, reference)
    empreinte_element = calculer_sha256_json_canonique(element)
    if empreinte_element != reference.element_sha256:
        raise EmpreinteElementIncorrecte(
            "L'empreinte de l'element clinique ne correspond plus a la reference."
        )

    if document_valide.date_seance is None:
        raise DocumentCliniqueInvalide(
            "Le document clinique resolu ne contient pas de date de seance."
        )

    return SourceResolueV1(
        reference_id=reference.id,
        dossier_id_pseudonymise=reference.dossier_id_pseudonymise,
        document=reference.document,
        schema_version_document=document_valide.schema_version,
        date_seance_document=document_valide.date_seance,
        categorie_source=reference.categorie_source,
        json_pointer=reference.json_pointer,
        element=element,
        document_sha256=empreinte_document,
        element_sha256=empreinte_element,
        relation_support=reference.relation_support,
    )


def _resoudre_racine_patient(
    dossier_patient: Path,
    dossier_id_attendu: str,
) -> Path:
    try:
        racine = dossier_patient.resolve(strict=True)
    except FileNotFoundError as erreur:
        raise SourceAbsente("Le dossier patient autorise est absent.") from erreur
    except OSError as erreur:
        raise CheminSourceInterdit(
            "Le dossier patient autorise ne peut pas etre resolu."
        ) from erreur

    if not racine.is_dir():
        raise SourceAbsente("Le chemin patient autorise n'est pas un dossier.")
    if racine.name != dossier_id_attendu:
        raise PatientIncoherent(
            "Le dossier patient fourni ne correspond pas a l'identifiant attendu."
        )
    return racine


def _resoudre_chemin_source(
    document: str,
    racine_patient: Path,
) -> Path:
    chemin_posix = PurePosixPath(document)
    chemin_windows = PureWindowsPath(document)
    if chemin_posix.is_absolute() or chemin_windows.is_absolute():
        raise CheminSourceInterdit("Un chemin source absolu est interdit.")
    if "\\" in document:
        raise CheminSourceInterdit(
            "Le chemin source doit utiliser uniquement des barres obliques."
        )

    segments = document.split("/")
    if (
        not segments
        or segments[0] != DOSSIER_SOURCES_CLINIQUES
        or len(segments) < 2
    ):
        raise CheminSourceInterdit(
            "La source doit appartenir au dossier donnees_cliniques autorise."
        )
    if any(segment in {"", ".", ".."} for segment in segments):
        raise CheminSourceInterdit(
            "Le chemin source contient un segment de normalisation interdit."
        )

    dossier_clinique = (racine_patient / DOSSIER_SOURCES_CLINIQUES).resolve(
        strict=False
    )
    candidat = racine_patient.joinpath(*segments)
    try:
        chemin_resolu = candidat.resolve(strict=True)
    except FileNotFoundError as erreur:
        raise SourceAbsente("Le fichier clinique reference est absent.") from erreur
    except OSError as erreur:
        raise CheminSourceInterdit(
            "Le chemin du fichier clinique ne peut pas etre resolu."
        ) from erreur

    if not _est_dans_perimetre(chemin_resolu, racine_patient):
        raise CheminSourceInterdit("Le chemin resolu sort du dossier patient.")
    if not _est_dans_perimetre(chemin_resolu, dossier_clinique):
        raise CheminSourceInterdit(
            "Le chemin resolu sort du dossier de donnees cliniques."
        )
    if not chemin_resolu.is_file():
        raise SourceAbsente("La source clinique referencee n'est pas un fichier.")
    return chemin_resolu


def _est_dans_perimetre(chemin: Path, racine: Path) -> bool:
    try:
        chemin.relative_to(racine)
    except ValueError:
        return False
    return True


def _lire_document(chemin: Path) -> bytes:
    try:
        return chemin.read_bytes()
    except FileNotFoundError as erreur:
        raise SourceAbsente("Le fichier clinique reference est absent.") from erreur
    except OSError as erreur:
        raise DocumentCliniqueInvalide(
            "Le fichier clinique reference ne peut pas etre lu."
        ) from erreur


def _decoder_document_json(contenu: bytes) -> dict[str, JsonValue]:
    try:
        texte = contenu.decode("utf-8-sig")
        document = json.loads(
            texte,
            parse_constant=_refuser_constante_json,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as erreur:
        raise DocumentCliniqueInvalide(
            "Le fichier source n'est pas un document JSON UTF-8 valide."
        ) from erreur
    if not isinstance(document, dict):
        raise DocumentCliniqueInvalide(
            "Le document clinique doit etre un objet JSON."
        )
    return document


def _refuser_constante_json(valeur: str) -> None:
    raise ValueError(f"Constante JSON non standard interdite : {valeur}")


def _valider_document_clinique(
    document: dict[str, JsonValue],
    reference: ReferenceSourceV1,
) -> _DocumentCliniqueV2:
    schema_document = document.get("schema_version")
    if (
        reference.type_document != "json_clinique_v2"
        or reference.extraction_schema_version != SCHEMA_CLINIQUE_V2
        or schema_document != reference.extraction_schema_version
    ):
        raise SchemaCliniqueIncompatible(
            "Le schema du document clinique ne correspond pas a la reference V1."
        )
    try:
        document_valide = _DocumentCliniqueV2.model_validate(document)
    except ValidationError as erreur:
        raise DocumentCliniqueInvalide(
            "Le document ne respecte pas le contrat clinique V2."
        ) from erreur
    if document_valide.date_seance != reference.date_seance:
        raise DocumentCliniqueInvalide(
            "La date de seance du document ne correspond pas a la reference."
        )
    return document_valide


def _resoudre_pointeur_element(
    document: dict[str, JsonValue],
    reference: ReferenceSourceV1,
) -> JsonValue:
    pointeur = reference.json_pointer
    if re.search(r"~(?![01])", pointeur):
        raise PointeurSourceInvalide(
            "Le pointeur JSON contient un echappement invalide."
        )
    segments = pointeur.split("/")
    if len(segments) != 3 or segments[0] != "":
        raise PointeurSourceInvalide(
            "La provenance V1 exige un pointeur /categorie/index."
        )

    categorie = _decoder_segment_json_pointer(segments[1])
    index_texte = _decoder_segment_json_pointer(segments[2])
    if categorie != reference.categorie_source:
        raise PointeurSourceInvalide(
            "La categorie du pointeur differe de celle de la reference."
        )
    if categorie not in CATEGORIES_CLINIQUES_V2:
        raise CategorieSourceIntrouvable(
            "La categorie referencee n'existe pas dans le schema clinique V2."
        )
    if categorie not in document:
        raise CategorieSourceIntrouvable(
            "La categorie referencee est absente du document clinique."
        )
    if not re.fullmatch(r"0|[1-9][0-9]*", index_texte):
        raise PointeurSourceInvalide(
            "L'index du pointeur clinique doit etre un entier non negatif."
        )

    elements = document[categorie]
    if not isinstance(elements, list):
        raise DocumentCliniqueInvalide(
            "La categorie clinique referencee n'est pas une liste."
        )
    index = int(index_texte)
    if index >= len(elements):
        raise IndexSourceHorsLimites(
            "L'index du pointeur depasse la liste clinique referencee."
        )
    try:
        return elements[index]
    except IndexError as erreur:
        raise ElementSourceIntrouvable(
            "L'element clinique reference est introuvable."
        ) from erreur


def _decoder_segment_json_pointer(segment: str) -> str:
    return segment.replace("~1", "/").replace("~0", "~")
