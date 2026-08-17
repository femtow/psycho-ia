from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import json
import unittest

import main as app


def creer_donnees_cliniques(
    date_seance: date,
) -> app.DonneesCliniques:

    return app.DonneesCliniques(
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


class TestTraitementParLot(unittest.TestCase):
    def test_une_synthese_par_patient(self) -> None:
        patient_a = {
            "identifiant": "P-A"
        }
        patient_b = {
            "identifiant": "P-B"
        }
        images = [
            Path("a-1.jpg"),
            Path("b-1.jpg"),
            Path("a-2.jpg"),
            Path("b-2.jpg"),
            Path("a-3.jpg"),
        ]
        resultats = {
            "a-1.jpg": patient_a,
            "a-2.jpg": patient_a,
            "a-3.jpg": patient_a,
            "b-1.jpg": patient_b,
            "b-2.jpg": patient_b,
        }
        statistiques = app.creer_statistiques()
        cache_client = {}

        def traiter_image_fictive(
            image,
            patients,
            cache,
            stats,
        ):
            return resultats[image.name]

        with (
            patch.object(
                app,
                "traiter_image",
                side_effect=traiter_image_fictive,
            ),
            patch.object(
                app,
                "mettre_a_jour_synthese_longitudinale",
                return_value=False,
            ) as mettre_a_jour,
            patch.object(
                app,
                "mettre_a_jour_preparation_prochaine_seance",
                return_value=False,
            ) as preparer,
            patch("builtins.print"),
        ):
            app.traiter_lot_images(
                images,
                [patient_a, patient_b],
                cache_client,
                statistiques,
            )

        patients_synthetises = [
            appel.args[0]["identifiant"]
            for appel in mettre_a_jour.call_args_list
        ]

        self.assertEqual(
            patients_synthetises,
            ["P-A", "P-B"],
        )

        patients_prepares = [
            appel.args[0]["identifiant"]
            for appel in preparer.call_args_list
        ]

        self.assertEqual(
            patients_prepares,
            ["P-A", "P-B"],
        )

    def test_erreur_image_ne_bloque_pas_le_lot(self) -> None:
        patient = {
            "identifiant": "P-A"
        }
        images = [
            Path("erreur.jpg"),
            Path("valide.jpg"),
        ]
        statistiques = app.creer_statistiques()

        def traiter_image_fictive(
            image,
            patients,
            cache,
            stats,
        ):
            if image.name == "erreur.jpg":
                raise ValueError(
                    "Erreur fictive"
                )

            return patient

        with (
            patch.object(
                app,
                "traiter_image",
                side_effect=traiter_image_fictive,
            ),
            patch.object(
                app,
                "mettre_a_jour_synthese_longitudinale",
                return_value=False,
            ) as mettre_a_jour,
            patch.object(
                app,
                "mettre_a_jour_preparation_prochaine_seance",
                return_value=False,
            ) as preparer,
            patch("builtins.print"),
        ):
            app.traiter_lot_images(
                images,
                [patient],
                {},
                statistiques,
            )

        self.assertEqual(
            statistiques["erreurs"],
            1,
        )
        mettre_a_jour.assert_called_once()
        preparer.assert_called_once()

    def test_tokens_conserves_apres_rejet_deterministe(self) -> None:
        with TemporaryDirectory() as dossier:
            dossier_patient = Path(dossier)
            donnees_dir = (
                dossier_patient
                / "donnees_cliniques"
            )
            donnees_dir.mkdir()

            for index, date_seance in enumerate(
                (
                    date(2026, 8, 1),
                    date(2026, 8, 8),
                ),
                start=1,
            ):
                donnees = creer_donnees_cliniques(
                    date_seance
                )
                chemin = (
                    donnees_dir
                    / f"seance-{index}.json"
                )
                chemin.write_text(
                    json.dumps(
                        donnees.model_dump(
                            mode="json"
                        )
                    ),
                    encoding="utf-8",
                )

            synthese_invalide = (
                app.SyntheseLongitudinale(
                    problematiques_actuelles=[
                        app.ElementLongitudinal(
                            contenu="Élément fictif",
                            statut="explicite",
                            dates_sources=[
                                date(2026, 8, 3)
                            ],
                        )
                    ],
                    evolution=[],
                    emotions_actuelles=[],
                    cognitions_recurrentes=[],
                    comportements_significatifs=[],
                    evitements_actuels=[],
                    interventions_documentees=[],
                    reponse_aux_interventions=[],
                    taches_actuelles=[],
                    elements_incertains=[],
                    points_a_reprendre=[],
                )
            )

            reponse = SimpleNamespace(
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=40,
                    total_tokens=140,
                )
            )
            statistiques = app.creer_statistiques()
            patient = {
                "identifiant": "P-TEST",
                "dossier": dossier_patient,
            }

            with (
                patch.object(
                    app,
                    "obtenir_client",
                    return_value=object(),
                ),
                patch.object(
                    app,
                    "generer_synthese_longitudinale",
                    return_value=(
                        synthese_invalide,
                        reponse,
                    ),
                ),
                patch("builtins.print"),
            ):
                with self.assertRaises(
                    ValueError
                ):
                    app.mettre_a_jour_synthese_longitudinale(
                        patient,
                        {},
                        statistiques,
                    )

            self.assertEqual(
                statistiques["synthese_input_tokens"],
                100,
            )
            self.assertEqual(
                statistiques["synthese_output_tokens"],
                40,
            )
            self.assertEqual(
                statistiques["synthese_total_tokens"],
                140,
            )
            self.assertEqual(
                statistiques["api_total_tokens"],
                140,
            )
            self.assertEqual(
                statistiques["syntheses_creees"],
                0,
            )
            self.assertFalse(
                (
                    dossier_patient
                    / "syntheses"
                    / "synthese_longitudinale.json"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
