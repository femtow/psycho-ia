from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from main import (
    DateNomFichierInvalide,
    DateTranscriptionInvalide,
    DivergenceDateDonneesCliniques,
    DivergenceDateTranscription,
    DonneesCliniques,
    donnees_cliniques_valides,
    extraire_date_entete_transcription,
    extraire_date_nom_fichier,
    verifier_date_donnees_cliniques,
    verifier_date_transcription,
)


def creer_donnees_cliniques(
    date_seance: date | None,
) -> DonneesCliniques:

    return DonneesCliniques(
        schema_version="2.0",
        date_seance=date_seance,
        faits_rapportes=[],
        emotions=[],
        cognitions=[],
        comportements=[],
        evitements=[],
        interventions=[],
        taches_interseances=[],
        elements_incertains=[],
    )


class TestControleDateSeance(unittest.TestCase):
    def test_date_nom_fichier_valide(self) -> None:
        attendue = date(2026, 8, 22)

        self.assertEqual(
            extraire_date_nom_fichier(
                "2026-08-22_PA.jpg"
            ),
            attendue,
        )

        self.assertEqual(
            extraire_date_nom_fichier(
                "2026-08-22_PA_02.jpg"
            ),
            attendue,
        )

        self.assertEqual(
            extraire_date_nom_fichier(
                "2026-08-22-PA.jpg"
            ),
            attendue,
        )

    def test_date_nom_fichier_absente_ou_impossible(self) -> None:
        for nom in (
            "note_PA.jpg",
            "22-08-2026_PA.jpg",
            "2026-02-30_PA.jpg",
            "2026-08-22.jpg",
        ):
            with self.subTest(nom=nom):
                with self.assertRaises(
                    DateNomFichierInvalide
                ):
                    extraire_date_nom_fichier(
                        nom
                    )

    def test_date_transcription_formats_valides(self) -> None:
        attendue = date(2026, 8, 22)

        self.assertEqual(
            extraire_date_entete_transcription(
                "Séance 22-08-2026\nContenu fictif"
            ),
            attendue,
        )

        self.assertEqual(
            extraire_date_entete_transcription(
                "Séance : 2026/08/22\nContenu fictif"
            ),
            attendue,
        )

    def test_date_transcription_absente(self) -> None:
        self.assertIsNone(
            extraire_date_entete_transcription(
                "Séance de suivi\nContenu fictif"
            )
        )

    def test_date_transcription_impossible_ou_ambigue(self) -> None:
        with self.assertRaises(
            DateTranscriptionInvalide
        ):
            extraire_date_entete_transcription(
                "Séance 31-02-2026\nContenu fictif"
            )

        with self.assertRaises(
            DateTranscriptionInvalide
        ):
            extraire_date_entete_transcription(
                "Séance 22-08-2026\nCorrection 23-08-2026"
            )

    def test_divergence_date_transcription(self) -> None:
        with self.assertRaises(
            DivergenceDateTranscription
        ):
            verifier_date_transcription(
                "Séance 23-08-2026",
                date(2026, 8, 22),
            )

    def test_date_json_absente_completee(self) -> None:
        attendue = date(2026, 8, 22)
        donnees = creer_donnees_cliniques(
            None
        )

        resultat = (
            verifier_date_donnees_cliniques(
                donnees,
                attendue,
            )
        )

        self.assertEqual(
            resultat.date_seance,
            attendue,
        )

    def test_divergence_date_json(self) -> None:
        with self.assertRaises(
            DivergenceDateDonneesCliniques
        ):
            verifier_date_donnees_cliniques(
                creer_donnees_cliniques(
                    date(2026, 8, 23)
                ),
                date(2026, 8, 22),
            )

    def test_reutilisation_json_exige_la_date_attendue(self) -> None:
        attendue = date(2026, 8, 22)

        with TemporaryDirectory() as dossier:
            dossier_path = Path(dossier)
            transcription_path = (
                dossier_path
                / "2026-08-22_PA.txt"
            )
            json_path = (
                dossier_path
                / "2026-08-22_PA.json"
            )

            transcription_path.write_text(
                "Séance 22-08-2026",
                encoding="utf-8",
            )

            donnees = creer_donnees_cliniques(
                attendue
            )

            json_path.write_text(
                json.dumps(
                    donnees.model_dump(
                        mode="json"
                    )
                ),
                encoding="utf-8",
            )

            self.assertTrue(
                donnees_cliniques_valides(
                    json_path,
                    transcription_path,
                    attendue,
                )
            )

            self.assertFalse(
                donnees_cliniques_valides(
                    json_path,
                    transcription_path,
                    date(2026, 8, 23),
                )
            )


if __name__ == "__main__":
    unittest.main()
