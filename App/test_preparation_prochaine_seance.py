from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import json
import unittest

import main as app


def creer_donnees(
    date_seance: date,
    *,
    taches: list[str] | None = None,
    incertitudes: list[str] | None = None,
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
        taches_interseances=(
            taches or []
        ),
        elements_incertains=(
            incertitudes or []
        ),
    )


def creer_preparation_generee(
    date_derniere: date,
) -> app.PreparationGeneree:

    return app.PreparationGeneree(
        resume_derniere_seance=[
            app.ElementPreparationDocumente(
                contenu="Résumé fictif",
                date_source=date_derniere,
            )
        ],
        points_explicitement_a_reprendre=[],
        elements_de_securite_explicitement_documentes=[],
        evolutions_prudentes=[],
        suggestions_prochaine_seance=[],
        questions_possibles=[],
    )


def creer_sources_patient(
    dossier_patient: Path,
) -> tuple[
    dict,
    list[tuple[Path, app.DonneesCliniques]],
    Path,
    app.FichierSyntheseLongitudinale,
]:

    patient = {
        "identifiant": "P-TEST",
        "dossier": dossier_patient,
    }
    donnees_dir = (
        dossier_patient
        / "donnees_cliniques"
    )
    donnees_dir.mkdir(parents=True)

    for index, date_seance in enumerate(
        (
            date(2026, 8, 1),
            date(2026, 8, 8),
        ),
        start=1,
    ):
        donnees = creer_donnees(
            date_seance,
            taches=(
                ["Tâche exacte"]
                if index == 2
                else []
            ),
            incertitudes=(
                ["Élément incertain exact"]
                if index == 2
                else []
            ),
        )
        chemin = (
            donnees_dir
            / f"seance-{index}.json"
        )
        chemin.write_text(
            json.dumps(
                donnees.model_dump(
                    mode="json"
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    fichiers = app.obtenir_fichiers_cliniques_patient(
        patient
    )
    seances, ignores = (
        app.charger_seances_longitudinales(
            fichiers
        )
    )
    assert not ignores

    synthese = app.SyntheseLongitudinale(
        problematiques_actuelles=[],
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
    empreinte = app.calculer_empreinte_sources(
        [fichier for fichier, _ in seances]
    )
    fichier_synthese = app.construire_fichier_synthese(
        patient,
        synthese,
        seances,
        empreinte,
    )
    chemin_synthese = (
        app.obtenir_chemin_synthese_longitudinale(
            patient
        )
    )
    app.enregistrer_synthese_longitudinale(
        fichier_synthese,
        chemin_synthese,
    )

    return (
        patient,
        seances,
        chemin_synthese,
        fichier_synthese,
    )


class TestPreparationProchaineSeance(unittest.TestCase):
    def test_taches_et_incertitudes_copiees_exactement(self) -> None:
        derniere = creer_donnees(
            date(2026, 8, 8),
            taches=["Tâche exacte"],
            incertitudes=["Élément incertain exact"],
        )

        preparation = (
            app.construire_preparation_prochaine_seance(
                creer_preparation_generee(
                    date(2026, 8, 8)
                ),
                derniere,
            )
        )

        self.assertEqual(
            preparation.donnees_documentees
            .taches_interseances_documentees[0]
            .contenu,
            "Tâche exacte",
        )
        self.assertEqual(
            preparation.donnees_documentees
            .elements_incertains[0]
            .contenu,
            "Élément incertain exact",
        )

    def test_refuse_date_inventee(self) -> None:
        generee = creer_preparation_generee(
            date(2026, 8, 9)
        )
        preparation = (
            app.construire_preparation_prochaine_seance(
                generee,
                creer_donnees(
                    date(2026, 8, 8)
                ),
            )
        )

        with self.assertRaises(ValueError):
            app.verifier_dates_preparation(
                preparation,
                {
                    date(2026, 8, 1),
                    date(2026, 8, 8),
                },
                date(2026, 8, 8),
            )

    def test_refuse_evolution_sur_une_seule_date(self) -> None:
        generee = creer_preparation_generee(
            date(2026, 8, 8)
        )
        generee.evolutions_prudentes = [
            app.EvolutionPreparationPrudente(
                contenu="Évolution fictive",
                dates_sources=[
                    date(2026, 8, 8),
                    date(2026, 8, 8),
                ],
            )
        ]
        preparation = (
            app.construire_preparation_prochaine_seance(
                generee,
                creer_donnees(
                    date(2026, 8, 8)
                ),
            )
        )

        with self.assertRaises(ValueError):
            app.verifier_dates_preparation(
                preparation,
                {
                    date(2026, 8, 1),
                    date(2026, 8, 8),
                },
                date(2026, 8, 8),
            )

    def test_ne_conserve_que_les_trois_dernieres_seances(self) -> None:
        seances = [
            (
                Path(f"seance-{index}.json"),
                creer_donnees(
                    date(2026, 8, index)
                ),
            )
            for index in range(1, 5)
        ]

        selection = (
            app.selectionner_seances_preparation(
                seances
            )
        )

        self.assertEqual(
            [
                donnees.date_seance
                for _, donnees in selection
            ],
            [
                date(2026, 8, 2),
                date(2026, 8, 3),
                date(2026, 8, 4),
            ],
        )

    def test_version_generateur_change_empreinte(self) -> None:
        with TemporaryDirectory() as dossier:
            (
                _,
                seances,
                _,
                fichier_synthese,
            ) = creer_sources_patient(
                Path(dossier)
            )

            empreintes_v1 = (
                app.calculer_empreintes_preparation(
                    seances,
                    fichier_synthese,
                )
            )

            with patch.object(
                app,
                "PREPARATION_GENERATOR_VERSION",
                "1.1",
            ):
                empreintes_v2 = (
                    app.calculer_empreintes_preparation(
                        seances,
                        fichier_synthese,
                    )
                )

            self.assertNotEqual(
                empreintes_v1[1],
                empreintes_v2[1],
            )

    def test_anti_doublon_evite_appel_api(self) -> None:
        with TemporaryDirectory() as dossier:
            (
                patient,
                seances,
                chemin_synthese,
                fichier_synthese,
            ) = creer_sources_patient(
                Path(dossier)
            )
            selection = (
                app.selectionner_seances_preparation(
                    seances
                )
            )
            (
                empreinte_sources,
                empreinte_generation,
                prompt_sha256,
            ) = app.calculer_empreintes_preparation(
                selection,
                fichier_synthese,
            )
            preparation = (
                app.construire_preparation_prochaine_seance(
                    creer_preparation_generee(
                        date(2026, 8, 8)
                    ),
                    selection[-1][1],
                )
            )
            fichier_final = (
                app.construire_fichier_preparation(
                    patient,
                    preparation,
                    selection,
                    chemin_synthese,
                    empreinte_sources,
                    empreinte_generation,
                    prompt_sha256,
                )
            )
            app.enregistrer_preparation_prochaine_seance(
                fichier_final,
                app.obtenir_chemin_preparation_prochaine_seance(
                    patient
                ),
            )
            statistiques = app.creer_statistiques()

            with (
                patch.object(
                    app,
                    "obtenir_client",
                ) as obtenir_client,
                patch("builtins.print"),
            ):
                resultat = (
                    app.mettre_a_jour_preparation_prochaine_seance(
                        patient,
                        {},
                        statistiques,
                    )
                )

            self.assertFalse(resultat)
            obtenir_client.assert_not_called()
            self.assertEqual(
                statistiques[
                    "preparations_deja_a_jour"
                ],
                1,
            )

    def test_synthese_obsolete_interdit_preparation(self) -> None:
        with TemporaryDirectory() as dossier:
            patient, _, _, _ = creer_sources_patient(
                Path(dossier)
            )
            fichier_clinique = (
                patient["dossier"]
                / "donnees_cliniques"
                / "seance-2.json"
            )
            contenu = json.loads(
                fichier_clinique.read_text(
                    encoding="utf-8"
                )
            )
            contenu["faits_rapportes"] = [
                "Modification fictive"
            ]
            fichier_clinique.write_text(
                json.dumps(
                    contenu,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            statistiques = app.creer_statistiques()

            with (
                patch.object(
                    app,
                    "obtenir_client",
                ) as obtenir_client,
                patch("builtins.print"),
            ):
                resultat = (
                    app.mettre_a_jour_preparation_prochaine_seance(
                        patient,
                        {},
                        statistiques,
                    )
                )

            self.assertFalse(resultat)
            obtenir_client.assert_not_called()
            self.assertEqual(
                statistiques[
                    "preparations_ignorees"
                ],
                1,
            )

    def test_tokens_conserves_apres_rejet_deterministe(self) -> None:
        with TemporaryDirectory() as dossier:
            patient, _, _, _ = creer_sources_patient(
                Path(dossier)
            )
            generee = creer_preparation_generee(
                date(2026, 8, 9)
            )
            reponse = SimpleNamespace(
                usage=SimpleNamespace(
                    input_tokens=80,
                    output_tokens=30,
                    total_tokens=110,
                )
            )
            statistiques = app.creer_statistiques()

            with (
                patch.object(
                    app,
                    "obtenir_client",
                    return_value=object(),
                ),
                patch.object(
                    app,
                    "generer_preparation_prochaine_seance",
                    return_value=(generee, reponse),
                ),
                patch("builtins.print"),
            ):
                with self.assertRaises(ValueError):
                    app.mettre_a_jour_preparation_prochaine_seance(
                        patient,
                        {},
                        statistiques,
                    )

            self.assertEqual(
                statistiques[
                    "preparation_total_tokens"
                ],
                110,
            )
            self.assertEqual(
                statistiques["api_total_tokens"],
                110,
            )
            self.assertEqual(
                statistiques["preparations_creees"],
                0,
            )


if __name__ == "__main__":
    unittest.main()
