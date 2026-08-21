"""Confirmation locale et versionnee d'une transcription clinique V1."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Callable, ClassVar, Literal
import hashlib
import json
import os
import re
import tempfile
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_SOURCE_CLINIQUE = "1.0"
SCHEMA_PROVENANCE_JSON = "1.0"
DOSSIER_SOURCES_CONFIRMEES = "sources_cliniques_confirmees"
DOSSIER_TRANSCRIPTIONS = "transcriptions"
DOSSIER_DONNEES_CLINIQUES = "donnees_cliniques"
DECLARATION_CONFIRMATION = (
    "Cette transcription correspond suffisamment a ma note clinique "
    "pour etre utilisee par Psycho IA."
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ErreurSourceClinique(Exception):
    code: ClassVar[str] = "erreur_source_clinique"


class SourceCliniqueInvalide(ErreurSourceClinique):
    code = "source_clinique_invalide"


class ConfirmationExpliciteManquante(ErreurSourceClinique):
    code = "confirmation_explicite_manquante"


class IncertitudesNonAcceptees(ErreurSourceClinique):
    code = "incertitudes_non_acceptees"


class SourceCliniqueObsolete(ErreurSourceClinique):
    code = "source_clinique_obsolete"


class PersistanceSourceEchouee(ErreurSourceClinique):
    code = "persistance_source_echouee"


class StatutSourceCliniqueV1(str, Enum):
    PRODUITE = "produite"
    CONFIRMEE = "confirmee"
    CORRIGEE_ET_CONFIRMEE = "corrigee_et_confirmee"
    OBSOLETE = "obsolete"


class OrigineVersionTranscriptionV1(str, Enum):
    MACHINE = "machine"
    CORRECTION_CLINICIEN = "correction_clinicien"


class ModeleSourceStrict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VersionTranscriptionV1(ModeleSourceStrict):
    numero: int = Field(ge=1)
    origine: OrigineVersionTranscriptionV1
    document_courant: str = Field(min_length=1)
    instantane: str = Field(min_length=1)
    transcription_sha256: str
    cree_le: datetime
    auteur_id: str | None = None
    version_precedente: int | None = Field(default=None, ge=1)

    @field_validator("transcription_sha256")
    @classmethod
    def verifier_sha256(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Empreinte SHA-256 de transcription invalide.")
        return valeur

    @field_validator("cree_le")
    @classmethod
    def verifier_fuseau(cls, valeur: datetime) -> datetime:
        if valeur.tzinfo is None or valeur.utcoffset() is None:
            raise ValueError("La date de version doit inclure un fuseau horaire.")
        return valeur

    @model_validator(mode="after")
    def verifier_origine(self) -> VersionTranscriptionV1:
        if self.numero == 1 and self.version_precedente is not None:
            raise ValueError("La premiere version ne peut avoir de precedente.")
        if self.numero > 1 and self.version_precedente != self.numero - 1:
            raise ValueError("Les versions de transcription doivent etre continues.")
        if self.origine is OrigineVersionTranscriptionV1.CORRECTION_CLINICIEN:
            if not self.auteur_id:
                raise ValueError("Une correction exige l'identite du clinicien.")
        elif self.auteur_id is not None:
            raise ValueError("Une version machine ne porte pas d'auteur clinicien.")
        return self


class CorrectionTranscriptionV1(ModeleSourceStrict):
    version_avant: int = Field(ge=1)
    version_apres: int = Field(ge=2)
    avant_sha256: str
    apres_sha256: str
    avant_instantane: str = Field(min_length=1)
    apres_instantane: str = Field(min_length=1)
    corrigee_par: str = Field(min_length=1)
    corrigee_le: datetime

    @field_validator("avant_sha256", "apres_sha256")
    @classmethod
    def verifier_sha256(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Empreinte de correction invalide.")
        return valeur

    @model_validator(mode="after")
    def verifier_versions(self) -> CorrectionTranscriptionV1:
        if self.version_apres != self.version_avant + 1:
            raise ValueError("Une correction doit creer la version suivante.")
        if self.corrigee_le.tzinfo is None or self.corrigee_le.utcoffset() is None:
            raise ValueError("La date de correction doit inclure un fuseau horaire.")
        return self


class ConfirmationSourceV1(ModeleSourceStrict):
    id: str
    version_transcription: int = Field(ge=1)
    transcription_sha256: str
    confirmee_par: str = Field(min_length=1)
    confirmee_le: datetime
    declaration: Literal[
        "Cette transcription correspond suffisamment a ma note clinique pour etre utilisee par Psycho IA."
    ] = DECLARATION_CONFIRMATION
    passages_signales: tuple[str, ...] = ()
    incertitudes_acceptees: bool

    @field_validator("id")
    @classmethod
    def verifier_id(cls, valeur: str) -> str:
        if not re.fullmatch(r"^conf_[0-9a-f]{32}$", valeur):
            raise ValueError("Identifiant de confirmation invalide.")
        return valeur

    @field_validator("transcription_sha256")
    @classmethod
    def verifier_sha256(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Empreinte de confirmation invalide.")
        return valeur

    @model_validator(mode="after")
    def verifier_confirmation(self) -> ConfirmationSourceV1:
        if self.confirmee_le.tzinfo is None or self.confirmee_le.utcoffset() is None:
            raise ValueError("La date de confirmation doit inclure un fuseau horaire.")
        if self.passages_signales and not self.incertitudes_acceptees:
            raise ValueError("Les incertitudes signalees doivent etre acceptees.")
        return self


class DossierSourceCliniqueV1(ModeleSourceStrict):
    schema_version: Literal["1.0"] = SCHEMA_SOURCE_CLINIQUE
    dossier_id_pseudonymise: str = Field(min_length=1)
    date_seance: date
    transcription_machine: str = Field(min_length=1)
    version_courante: int = Field(ge=1)
    versions: tuple[VersionTranscriptionV1, ...] = Field(min_length=1)
    corrections: tuple[CorrectionTranscriptionV1, ...] = ()
    confirmations: tuple[ConfirmationSourceV1, ...] = ()

    @model_validator(mode="after")
    def verifier_historique(self) -> DossierSourceCliniqueV1:
        numeros = tuple(version.numero for version in self.versions)
        if numeros != tuple(range(1, len(self.versions) + 1)):
            raise ValueError("Les versions de source doivent etre continues.")
        if self.version_courante != self.versions[-1].numero:
            raise ValueError("La version courante doit etre la derniere version.")
        versions_connues = set(numeros)
        if any(
            confirmation.version_transcription not in versions_connues
            for confirmation in self.confirmations
        ):
            raise ValueError("Une confirmation reference une version inconnue.")
        return self


class ProvenanceJsonCliniqueV1(ModeleSourceStrict):
    schema_version: Literal["1.0"] = SCHEMA_PROVENANCE_JSON
    dossier_id_pseudonymise: str = Field(min_length=1)
    date_seance: date
    json_clinique: str = Field(min_length=1)
    json_sha256: str
    transcription: str = Field(min_length=1)
    transcription_sha256: str
    confirmation_source: str | None = None
    confirmation_id: str | None = None
    relation: Literal["derive_machine_depuis_transcription"] = (
        "derive_machine_depuis_transcription"
    )
    assertions_json_validees_individuellement: Literal[False] = False

    @field_validator("json_sha256", "transcription_sha256")
    @classmethod
    def verifier_sha256(cls, valeur: str) -> str:
        if not SHA256_RE.fullmatch(valeur):
            raise ValueError("Empreinte de provenance JSON invalide.")
        return valeur

    @model_validator(mode="after")
    def verifier_confirmation(self) -> ProvenanceJsonCliniqueV1:
        if (self.confirmation_source is None) != (self.confirmation_id is None):
            raise ValueError("La reference de confirmation doit etre complete.")
        return self


class EtatSourceCliniqueV1(ModeleSourceStrict):
    statut: StatutSourceCliniqueV1
    dossier_id_pseudonymise: str
    date_seance: date
    version: int | None = None
    confirmation_id: str | None = None
    passages_signales: tuple[str, ...] = ()
    motif: str
    json_clinique_lie: bool = False

    @property
    def est_confirmee(self) -> bool:
        return self.statut in {
            StatutSourceCliniqueV1.CONFIRMEE,
            StatutSourceCliniqueV1.CORRIGEE_ET_CONFIRMEE,
        }


class ResultatConfirmationV1(ModeleSourceStrict):
    etat: EtatSourceCliniqueV1
    confirmation: ConfirmationSourceV1
    deja_confirmee: bool


def calculer_sha256_octets(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def detecter_passages_signales(texte: str) -> tuple[str, ...]:
    resultat = []
    for ligne in texte.splitlines():
        ligne_nettoyee = ligne.strip()
        ligne_minuscule = ligne_nettoyee.lower()
        if "[illisible]" in ligne_minuscule or "[mot incertain" in ligne_minuscule:
            resultat.append(ligne_nettoyee)
    return tuple(resultat)


class ServiceSourceCliniqueConfirmeeV1:
    """Service local; aucune dependance reseau ou OpenAI."""

    def __init__(
        self,
        dossier_patient: Path,
        transcription_path: Path,
        date_seance: date,
        dossier_id_pseudonymise: str,
        *,
        remplacer_fichier: Callable[[Path, Path], None] = os.replace,
    ) -> None:
        self.dossier_patient = _valider_dossier_patient(
            dossier_patient,
            dossier_id_pseudonymise,
        )
        self.dossier_id_pseudonymise = dossier_id_pseudonymise
        self.date_seance = date_seance
        self.transcription_path = _valider_transcription(
            transcription_path,
            self.dossier_patient,
            date_seance,
        )
        self._remplacer_fichier = remplacer_fichier
        self.dossier_session = (
            self.dossier_patient
            / DOSSIER_SOURCES_CONFIRMEES
            / self.transcription_path.stem
        )
        self.chemin_dossier_source = self.dossier_session / "source_clinique_v1.json"
        self.chemin_provenance_json = (
            self.dossier_session / "provenance_json_clinique_v1.json"
        )

    def lire_transcription(self) -> str:
        dossier = self._charger_dossier()
        if dossier is None:
            return _lire_texte(self.transcription_path)
        version = dossier.versions[-1]
        return _lire_texte(_resoudre_document(version.document_courant, self.dossier_patient))

    def passages_signales(self) -> tuple[str, ...]:
        return detecter_passages_signales(self.lire_transcription())

    def verifier_autorite(self) -> EtatSourceCliniqueV1:
        dossier = self._charger_dossier()
        if dossier is None:
            return EtatSourceCliniqueV1(
                statut=StatutSourceCliniqueV1.PRODUITE,
                dossier_id_pseudonymise=self.dossier_id_pseudonymise,
                date_seance=self.date_seance,
                passages_signales=detecter_passages_signales(
                    _lire_texte(self.transcription_path)
                ),
                motif="Transcription produite mais jamais confirmee.",
            )
        version = dossier.versions[-1]
        confirmation = _confirmation_version_courante(dossier)
        passages = _passages_version(version, self.dossier_patient)
        if confirmation is None:
            return EtatSourceCliniqueV1(
                statut=StatutSourceCliniqueV1.PRODUITE,
                dossier_id_pseudonymise=self.dossier_id_pseudonymise,
                date_seance=self.date_seance,
                version=version.numero,
                passages_signales=passages,
                motif="La version courante n'a pas ete confirmee.",
            )
        if not _version_intacte(version, self.dossier_patient):
            return EtatSourceCliniqueV1(
                statut=StatutSourceCliniqueV1.OBSOLETE,
                dossier_id_pseudonymise=self.dossier_id_pseudonymise,
                date_seance=self.date_seance,
                version=version.numero,
                confirmation_id=confirmation.id,
                passages_signales=passages,
                motif="Le fichier confirme a change ou n'existe plus.",
            )
        statut = (
            StatutSourceCliniqueV1.CORRIGEE_ET_CONFIRMEE
            if version.origine is OrigineVersionTranscriptionV1.CORRECTION_CLINICIEN
            else StatutSourceCliniqueV1.CONFIRMEE
        )
        return EtatSourceCliniqueV1(
            statut=statut,
            dossier_id_pseudonymise=self.dossier_id_pseudonymise,
            date_seance=self.date_seance,
            version=version.numero,
            confirmation_id=confirmation.id,
            passages_signales=passages,
            motif="La version exacte de la transcription est confirmee.",
            json_clinique_lie=self._json_lie_a_confirmation(confirmation),
        )

    def confirmer(
        self,
        *,
        clinicien_id: str,
        confirmation_explicite: bool,
        accepter_incertitudes: bool,
        confirmee_le: datetime | None = None,
    ) -> ResultatConfirmationV1:
        if not confirmation_explicite:
            raise ConfirmationExpliciteManquante(
                "La source exige une confirmation explicite du clinicien."
            )
        dossier = self._charger_ou_initialiser_dossier()
        version = dossier.versions[-1]
        if not _version_intacte(version, self.dossier_patient):
            raise SourceCliniqueObsolete(
                "La version affichee a change; rechargez-la avant confirmation."
            )
        texte = _lire_texte(_resoudre_document(version.document_courant, self.dossier_patient))
        passages = detecter_passages_signales(texte)
        if passages and not accepter_incertitudes:
            raise IncertitudesNonAcceptees(
                "Les passages signales doivent etre conserves ou corriges explicitement."
            )
        existante = _confirmation_version_courante(dossier)
        if existante is not None and existante.transcription_sha256 == version.transcription_sha256:
            etat = self.verifier_autorite()
            return ResultatConfirmationV1(
                etat=etat,
                confirmation=existante,
                deja_confirmee=True,
            )
        instant = confirmee_le or datetime.now(timezone.utc)
        confirmation = ConfirmationSourceV1(
            id=f"conf_{uuid.uuid4().hex}",
            version_transcription=version.numero,
            transcription_sha256=version.transcription_sha256,
            confirmee_par=clinicien_id,
            confirmee_le=instant,
            passages_signales=passages,
            incertitudes_acceptees=not passages or accepter_incertitudes,
        )
        mis_a_jour = dossier.model_copy(
            update={"confirmations": (*dossier.confirmations, confirmation)}
        )
        self._enregistrer_dossier(mis_a_jour)
        self._lier_json_a_confirmation(confirmation)
        return ResultatConfirmationV1(
            etat=self.verifier_autorite(),
            confirmation=confirmation,
            deja_confirmee=False,
        )

    def corriger(
        self,
        nouveau_texte: str,
        *,
        clinicien_id: str,
        corrigee_le: datetime | None = None,
    ) -> DossierSourceCliniqueV1:
        if not nouveau_texte.strip():
            raise SourceCliniqueInvalide("Une transcription corrigee ne peut etre vide.")
        dossier = self._charger_ou_initialiser_dossier()
        version_avant = dossier.versions[-1]
        if not _version_intacte(version_avant, self.dossier_patient):
            raise SourceCliniqueObsolete(
                "La version a corriger a change; rechargez-la avant correction."
            )
        texte_avant = _lire_texte(
            _resoudre_document(version_avant.document_courant, self.dossier_patient)
        )
        if nouveau_texte == texte_avant:
            raise SourceCliniqueInvalide("La correction ne modifie pas la transcription.")
        numero = version_avant.numero + 1
        instant = corrigee_le or datetime.now(timezone.utc)
        chemin_correction = (
            self.dossier_session
            / "versions"
            / f"v{numero:04d}_correction_clinicien.txt"
        )
        contenu_apres = nouveau_texte.encode("utf-8")
        empreinte_apres = calculer_sha256_octets(contenu_apres)
        relative_correction = _chemin_relatif(chemin_correction, self.dossier_patient)
        version_apres = VersionTranscriptionV1(
            numero=numero,
            origine=OrigineVersionTranscriptionV1.CORRECTION_CLINICIEN,
            document_courant=relative_correction,
            instantane=relative_correction,
            transcription_sha256=empreinte_apres,
            cree_le=instant,
            auteur_id=clinicien_id,
            version_precedente=version_avant.numero,
        )
        correction = CorrectionTranscriptionV1(
            version_avant=version_avant.numero,
            version_apres=version_apres.numero,
            avant_sha256=version_avant.transcription_sha256,
            apres_sha256=version_apres.transcription_sha256,
            avant_instantane=version_avant.instantane,
            apres_instantane=version_apres.instantane,
            corrigee_par=clinicien_id,
            corrigee_le=instant,
        )
        mis_a_jour = dossier.model_copy(
            update={
                "version_courante": numero,
                "versions": (*dossier.versions, version_apres),
                "corrections": (*dossier.corrections, correction),
            }
        )
        _persister_correction_et_dossier(
            chemin_correction,
            contenu_apres,
            self.chemin_dossier_source,
            _serialiser_modele(mis_a_jour),
            self._remplacer_fichier,
        )
        return mis_a_jour

    def corriger_et_confirmer(
        self,
        nouveau_texte: str,
        *,
        clinicien_id: str,
        confirmation_explicite: bool,
        accepter_incertitudes: bool,
        instant: datetime | None = None,
    ) -> ResultatConfirmationV1:
        moment = instant or datetime.now(timezone.utc)
        self.corriger(
            nouveau_texte,
            clinicien_id=clinicien_id,
            corrigee_le=moment,
        )
        return self.confirmer(
            clinicien_id=clinicien_id,
            confirmation_explicite=confirmation_explicite,
            accepter_incertitudes=accepter_incertitudes,
            confirmee_le=moment,
        )

    def _charger_ou_initialiser_dossier(self) -> DossierSourceCliniqueV1:
        dossier = self._charger_dossier()
        if dossier is not None:
            return dossier
        contenu = self.transcription_path.read_bytes()
        empreinte = calculer_sha256_octets(contenu)
        chemin_instantane = (
            self.dossier_session / "versions" / "v0001_machine.txt"
        )
        _ecrire_atomique(
            chemin_instantane,
            contenu,
            self._remplacer_fichier,
        )
        version = VersionTranscriptionV1(
            numero=1,
            origine=OrigineVersionTranscriptionV1.MACHINE,
            document_courant=_chemin_relatif(
                self.transcription_path,
                self.dossier_patient,
            ),
            instantane=_chemin_relatif(
                chemin_instantane,
                self.dossier_patient,
            ),
            transcription_sha256=empreinte,
            cree_le=datetime.now(timezone.utc),
        )
        dossier = DossierSourceCliniqueV1(
            dossier_id_pseudonymise=self.dossier_id_pseudonymise,
            date_seance=self.date_seance,
            transcription_machine=version.document_courant,
            version_courante=1,
            versions=(version,),
        )
        try:
            self._enregistrer_dossier(dossier)
        except Exception:
            chemin_instantane.unlink(missing_ok=True)
            raise
        return dossier

    def _charger_dossier(self) -> DossierSourceCliniqueV1 | None:
        if not self.chemin_dossier_source.is_file():
            return None
        try:
            dossier = DossierSourceCliniqueV1.model_validate_json(
                self.chemin_dossier_source.read_bytes()
            )
        except Exception as erreur:
            raise SourceCliniqueInvalide(
                "Le dossier de confirmation de source est invalide."
            ) from erreur
        if (
            dossier.dossier_id_pseudonymise != self.dossier_id_pseudonymise
            or dossier.date_seance != self.date_seance
            or dossier.transcription_machine
            != _chemin_relatif(self.transcription_path, self.dossier_patient)
        ):
            raise SourceCliniqueInvalide(
                "Le dossier de source ne correspond pas au patient ou a la seance."
            )
        return dossier

    def _enregistrer_dossier(self, dossier: DossierSourceCliniqueV1) -> None:
        _ecrire_atomique(
            self.chemin_dossier_source,
            _serialiser_modele(dossier),
            self._remplacer_fichier,
        )

    def _lier_json_a_confirmation(self, confirmation: ConfirmationSourceV1) -> None:
        if not self.chemin_provenance_json.is_file():
            return
        try:
            provenance = ProvenanceJsonCliniqueV1.model_validate_json(
                self.chemin_provenance_json.read_bytes()
            )
            json_path = _resoudre_document(
                provenance.json_clinique,
                self.dossier_patient,
            )
        except Exception:
            return
        if (
            provenance.dossier_id_pseudonymise != self.dossier_id_pseudonymise
            or provenance.date_seance != self.date_seance
            or provenance.transcription_sha256 != confirmation.transcription_sha256
            or calculer_sha256_octets(json_path.read_bytes()) != provenance.json_sha256
        ):
            return
        mise_a_jour = provenance.model_copy(
            update={
                "confirmation_source": _chemin_relatif(
                    self.chemin_dossier_source,
                    self.dossier_patient,
                ),
                "confirmation_id": confirmation.id,
            }
        )
        _ecrire_atomique(
            self.chemin_provenance_json,
            _serialiser_modele(mise_a_jour),
            self._remplacer_fichier,
        )

    def _json_lie_a_confirmation(self, confirmation: ConfirmationSourceV1) -> bool:
        if not self.chemin_provenance_json.is_file():
            return False
        try:
            provenance = ProvenanceJsonCliniqueV1.model_validate_json(
                self.chemin_provenance_json.read_bytes()
            )
            json_path = _resoudre_document(
                provenance.json_clinique,
                self.dossier_patient,
            )
        except Exception:
            return False
        return (
            provenance.confirmation_id == confirmation.id
            and provenance.transcription_sha256 == confirmation.transcription_sha256
            and calculer_sha256_octets(json_path.read_bytes()) == provenance.json_sha256
        )


def enregistrer_provenance_json_produite(
    dossier_patient: Path,
    dossier_id_pseudonymise: str,
    date_seance: date,
    transcription_path: Path,
    json_path: Path,
) -> Path:
    """Lie un JSON machine a la transcription exacte utilisee, sans validation humaine."""

    racine = _valider_dossier_patient(dossier_patient, dossier_id_pseudonymise)
    transcription = _valider_transcription(transcription_path, racine, date_seance)
    json_resolu = _valider_json_clinique(json_path, racine, date_seance)
    dossier_session = (
        racine / DOSSIER_SOURCES_CONFIRMEES / transcription.stem
    )
    chemin = dossier_session / "provenance_json_clinique_v1.json"
    provenance = ProvenanceJsonCliniqueV1(
        dossier_id_pseudonymise=dossier_id_pseudonymise,
        date_seance=date_seance,
        json_clinique=_chemin_relatif(json_resolu, racine),
        json_sha256=calculer_sha256_octets(json_resolu.read_bytes()),
        transcription=_chemin_relatif(transcription, racine),
        transcription_sha256=calculer_sha256_octets(transcription.read_bytes()),
    )
    _ecrire_atomique(chemin, _serialiser_modele(provenance), os.replace)
    return chemin


def enregistrer_provenance_json_depuis_source_confirmee(
    service: ServiceSourceCliniqueConfirmeeV1,
    json_path: Path,
    transcription_sha256_utilisee: str,
) -> Path:
    """Lie un JSON nouvellement genere a la version confirmee exactement utilisee."""

    etat = service.verifier_autorite()
    if not etat.est_confirmee or etat.confirmation_id is None:
        raise SourceCliniqueInvalide(
            "La version courante de la transcription n'est pas confirmee."
        )
    dossier = service._charger_dossier()
    if dossier is None:
        raise SourceCliniqueInvalide("Le dossier de source confirmee est absent.")
    version = dossier.versions[-1]
    confirmation = _confirmation_version_courante(dossier)
    if confirmation is None or confirmation.id != etat.confirmation_id:
        raise SourceCliniqueInvalide(
            "La confirmation courante ne peut pas etre resolue."
        )
    transcription_courante = _resoudre_document(
        version.document_courant,
        service.dossier_patient,
    )
    empreinte_courante = calculer_sha256_octets(
        transcription_courante.read_bytes()
    )
    if (
        transcription_sha256_utilisee != empreinte_courante
        or confirmation.transcription_sha256 != empreinte_courante
    ):
        raise SourceCliniqueInvalide(
            "Le JSON n'a pas ete genere depuis la version confirmee courante."
        )
    json_resolu = _valider_json_clinique(
        json_path,
        service.dossier_patient,
        service.date_seance,
    )
    provenance = ProvenanceJsonCliniqueV1(
        dossier_id_pseudonymise=service.dossier_id_pseudonymise,
        date_seance=service.date_seance,
        json_clinique=_chemin_relatif(json_resolu, service.dossier_patient),
        json_sha256=calculer_sha256_octets(json_resolu.read_bytes()),
        transcription=_chemin_relatif(
            transcription_courante,
            service.dossier_patient,
        ),
        transcription_sha256=empreinte_courante,
        confirmation_source=_chemin_relatif(
            service.chemin_dossier_source,
            service.dossier_patient,
        ),
        confirmation_id=confirmation.id,
    )
    _ecrire_atomique(
        service.chemin_provenance_json,
        _serialiser_modele(provenance),
        os.replace,
    )
    return service.chemin_provenance_json


def charger_provenance_json(chemin: Path) -> ProvenanceJsonCliniqueV1:
    return ProvenanceJsonCliniqueV1.model_validate_json(chemin.read_bytes())


def _valider_dossier_patient(dossier_patient: Path, dossier_id: str) -> Path:
    try:
        racine = dossier_patient.resolve(strict=True)
    except (FileNotFoundError, OSError) as erreur:
        raise SourceCliniqueInvalide("Le dossier patient est introuvable.") from erreur
    if not racine.is_dir() or racine.name != dossier_id:
        raise SourceCliniqueInvalide(
            "Le dossier patient ne correspond pas a l'identifiant attendu."
        )
    return racine


def _valider_transcription(
    transcription_path: Path,
    racine: Path,
    date_attendue: date,
) -> Path:
    try:
        chemin = transcription_path.resolve(strict=True)
    except (FileNotFoundError, OSError) as erreur:
        raise SourceCliniqueInvalide("La transcription est introuvable.") from erreur
    _verifier_dans_racine(chemin, racine)
    if chemin.parent.name.lower() != DOSSIER_TRANSCRIPTIONS:
        raise SourceCliniqueInvalide("La transcription doit etre dans son dossier dedie.")
    if not chemin.is_file() or chemin.suffix.lower() != ".txt":
        raise SourceCliniqueInvalide("La source doit etre une transcription texte.")
    _verifier_date_nom(chemin, date_attendue)
    if not _lire_texte(chemin).strip():
        raise SourceCliniqueInvalide("La transcription est vide.")
    return chemin


def _valider_json_clinique(json_path: Path, racine: Path, date_attendue: date) -> Path:
    try:
        chemin = json_path.resolve(strict=True)
    except (FileNotFoundError, OSError) as erreur:
        raise SourceCliniqueInvalide("Le JSON clinique est introuvable.") from erreur
    _verifier_dans_racine(chemin, racine)
    if chemin.parent.name.lower() != DOSSIER_DONNEES_CLINIQUES:
        raise SourceCliniqueInvalide("Le JSON doit etre dans donnees_cliniques.")
    _verifier_date_nom(chemin, date_attendue)
    try:
        document = json.loads(chemin.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise SourceCliniqueInvalide("Le JSON clinique est invalide.") from erreur
    if document.get("date_seance") != date_attendue.isoformat():
        raise SourceCliniqueInvalide("La date du JSON clinique est incoherente.")
    return chemin


def _verifier_date_nom(chemin: Path, date_attendue: date) -> None:
    try:
        date_nom = date.fromisoformat(chemin.stem[:10])
    except ValueError as erreur:
        raise SourceCliniqueInvalide(
            "Le nom de fichier doit commencer par une date AAAA-MM-JJ."
        ) from erreur
    if date_nom != date_attendue:
        raise SourceCliniqueInvalide("La source ne correspond pas a la seance attendue.")


def _verifier_dans_racine(chemin: Path, racine: Path) -> None:
    try:
        chemin.relative_to(racine)
    except ValueError as erreur:
        raise SourceCliniqueInvalide("Le chemin sort du dossier patient.") from erreur


def _chemin_relatif(chemin: Path, racine: Path) -> str:
    resolu = chemin.resolve(strict=False)
    _verifier_dans_racine(resolu, racine)
    return resolu.relative_to(racine).as_posix()


def _resoudre_document(document: str, racine: Path) -> Path:
    posix = PurePosixPath(document)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise SourceCliniqueInvalide("Chemin relatif de source invalide.")
    try:
        chemin = racine.joinpath(*posix.parts).resolve(strict=True)
    except (FileNotFoundError, OSError) as erreur:
        raise SourceCliniqueInvalide("Une version de transcription est absente.") from erreur
    _verifier_dans_racine(chemin, racine)
    return chemin


def _lire_texte(chemin: Path) -> str:
    try:
        return chemin.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as erreur:
        raise SourceCliniqueInvalide("La transcription ne peut pas etre lue.") from erreur


def _confirmation_version_courante(
    dossier: DossierSourceCliniqueV1,
) -> ConfirmationSourceV1 | None:
    for confirmation in reversed(dossier.confirmations):
        if confirmation.version_transcription == dossier.version_courante:
            return confirmation
    return None


def _version_intacte(version: VersionTranscriptionV1, racine: Path) -> bool:
    try:
        courant = _resoudre_document(version.document_courant, racine)
        instantane = _resoudre_document(version.instantane, racine)
        empreinte_courante = calculer_sha256_octets(courant.read_bytes())
        empreinte_instantane = calculer_sha256_octets(instantane.read_bytes())
    except (ErreurSourceClinique, OSError):
        return False
    return (
        empreinte_courante == version.transcription_sha256
        and empreinte_instantane == version.transcription_sha256
    )


def _passages_version(version: VersionTranscriptionV1, racine: Path) -> tuple[str, ...]:
    try:
        texte = _lire_texte(_resoudre_document(version.document_courant, racine))
    except ErreurSourceClinique:
        return ()
    return detecter_passages_signales(texte)


def _serialiser_modele(modele: BaseModel) -> bytes:
    return (
        json.dumps(
            modele.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _ecrire_temporaire(chemin: Path, contenu: bytes) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    descripteur, nom = tempfile.mkstemp(
        prefix=f".{chemin.name}.",
        suffix=".tmp",
        dir=chemin.parent,
    )
    temporaire = Path(nom)
    try:
        with os.fdopen(descripteur, "wb") as fichier:
            fichier.write(contenu)
            fichier.flush()
            os.fsync(fichier.fileno())
    except Exception:
        temporaire.unlink(missing_ok=True)
        raise
    return temporaire


def _ecrire_atomique(
    chemin: Path,
    contenu: bytes,
    remplacer: Callable[[Path, Path], None],
) -> None:
    temporaire = _ecrire_temporaire(chemin, contenu)
    try:
        remplacer(temporaire, chemin)
    except Exception as erreur:
        temporaire.unlink(missing_ok=True)
        raise PersistanceSourceEchouee(
            "La source clinique n'a pas pu etre enregistree."
        ) from erreur


def _persister_correction_et_dossier(
    chemin_correction: Path,
    contenu_correction: bytes,
    chemin_dossier: Path,
    contenu_dossier: bytes,
    remplacer: Callable[[Path, Path], None],
) -> None:
    temporaire_correction = _ecrire_temporaire(
        chemin_correction,
        contenu_correction,
    )
    temporaire_dossier = _ecrire_temporaire(chemin_dossier, contenu_dossier)
    correction_remplacee = False
    try:
        remplacer(temporaire_correction, chemin_correction)
        correction_remplacee = True
        remplacer(temporaire_dossier, chemin_dossier)
    except Exception as erreur:
        temporaire_correction.unlink(missing_ok=True)
        temporaire_dossier.unlink(missing_ok=True)
        if correction_remplacee:
            chemin_correction.unlink(missing_ok=True)
        raise PersistanceSourceEchouee(
            "La correction n'a pas ete conservee partiellement."
        ) from erreur
