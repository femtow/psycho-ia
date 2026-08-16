from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import base64
import unittest

from PIL import Image, ImageChops

import main as app


class TestPretraitementOcr(unittest.TestCase):
    def test_pretraitement_produit_une_image_rgb_grise(self) -> None:
        image = Image.new(
            "RGB",
            (4, 1),
        )
        image.putdata(
            [
                (20, 80, 160),
                (60, 120, 200),
                (100, 160, 240),
                (180, 220, 250),
            ]
        )

        resultat = app.appliquer_pretraitement_ocr(
            image
        )

        self.assertEqual(resultat.mode, "RGB")

        rouge, vert, bleu = resultat.split()
        self.assertIsNone(
            ImageChops.difference(
                rouge,
                vert,
            ).getbbox()
        )
        self.assertIsNone(
            ImageChops.difference(
                rouge,
                bleu,
            ).getbbox()
        )

    def test_conversion_preserve_original_et_dimensions(self) -> None:
        with TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "note.png"
            image = Image.new(
                "RGB",
                (3000, 1500),
                (210, 90, 170),
            )
            image.save(chemin)
            original = chemin.read_bytes()

            data_url = app.convertir_image_en_data_url(
                chemin
            )

            self.assertEqual(
                chemin.read_bytes(),
                original,
            )
            self.assertTrue(
                data_url.startswith(
                    "data:image/jpeg;base64,"
                )
            )

            donnees = base64.b64decode(
                data_url.split(",", 1)[1]
            )
            with Image.open(BytesIO(donnees)) as envoyee:
                self.assertEqual(envoyee.format, "JPEG")
                self.assertEqual(envoyee.mode, "RGB")
                self.assertLessEqual(
                    max(envoyee.size),
                    max(app.MAX_IMAGE_SIZE),
                )

    def test_prompt_interdit_reconstruction_ratures(self) -> None:
        self.assertIn(
            "annulée par plusieurs traits ou une surcharge",
            app.PROMPT_OCR,
        )
        self.assertIn(
            "Ne reconstruis jamais un texte raturé",
            app.PROMPT_OCR,
        )
        self.assertIn(
            "remplace uniquement la rature",
            app.PROMPT_OCR,
        )
        self.assertIn(
            "Un mot encore clairement lisible",
            app.PROMPT_OCR,
        )

    def test_transcription_utilise_prompt_et_detail_high(self) -> None:
        reponse = SimpleNamespace(
            output_text="Transcription fictive"
        )
        create = Mock(return_value=reponse)
        client = SimpleNamespace(
            responses=SimpleNamespace(
                create=create
            )
        )

        with patch.object(
            app,
            "convertir_image_en_data_url",
            return_value="data:image/jpeg;base64,TEST",
        ):
            transcription, retour = app.transcrire_image(
                client,
                Path("note.jpg"),
            )

        self.assertEqual(
            transcription,
            "Transcription fictive",
        )
        self.assertIs(retour, reponse)

        appel = create.call_args.kwargs
        contenu = appel["input"][0]["content"]
        self.assertEqual(
            contenu[0]["text"],
            app.PROMPT_OCR,
        )
        self.assertEqual(
            contenu[1]["detail"],
            "high",
        )
        self.assertFalse(appel["store"])


if __name__ == "__main__":
    unittest.main()
