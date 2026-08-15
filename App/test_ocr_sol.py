from __future__ import annotations

from io import BytesIO
from pathlib import Path
import base64
import os

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageOps


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

IMAGE_PATH = (
    BASE_DIR
    / "patients_test"
    / "P-0001"
    / "notes_originales"
    / "2026-08-15_PA.jpg"
)

MODEL = "gpt-5.6-sol"

MAX_IMAGE_SIZE = (2400, 2400)
JPEG_QUALITY = 92


def charger_client() -> OpenAI:
    load_dotenv(ENV_PATH)

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY absente dans .env."
        )

    return OpenAI(api_key=api_key)


def convertir_image_en_data_url(
    image_path: Path,
) -> str:

    with Image.open(image_path) as image:
        print(
            f"Format réel : {image.format}"
        )
        print(
            f"Dimensions originales : {image.size}"
        )

        image = ImageOps.exif_transpose(image)

        image.thumbnail(
            MAX_IMAGE_SIZE,
            Image.Resampling.LANCZOS,
        )

        print(
            f"Dimensions envoyées : {image.size}"
        )

        if image.mode != "RGB":
            image = image.convert("RGB")

        tampon = BytesIO()

        image.save(
            tampon,
            format="JPEG",
            quality=JPEG_QUALITY,
            optimize=True,
        )

        donnees = tampon.getvalue()

    print(
        f"Taille envoyée : "
        f"{len(donnees) / 1024:.1f} Ko"
    )

    contenu_base64 = base64.b64encode(
        donnees
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        f"{contenu_base64}"
    )


def main() -> None:
    print("=" * 70)
    print("TEST OCR — GPT-5.6 SOL")
    print("=" * 70)

    print(f"Image : {IMAGE_PATH}")
    print(f"Modèle : {MODEL}")

    if not IMAGE_PATH.exists():
        raise FileNotFoundError(
            f"Image introuvable : {IMAGE_PATH}"
        )

    client = charger_client()

    image_data_url = convertir_image_en_data_url(
        IMAGE_PATH
    )

    reponse = client.responses.create(
        model=MODEL,

        reasoning={
            "effort": "none",
        },

        store=False,

        max_output_tokens=2000,

        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Transcris exactement cette note "
                            "manuscrite.\n\n"

                            "Règles impératives :\n"
                            "- Ne résume pas.\n"
                            "- N'analyse pas.\n"
                            "- N'interprète pas.\n"
                            "- Ne reformule rien.\n"
                            "- Ne corrige pas les fautes.\n"
                            "- N'invente aucun mot.\n"
                            "- Conserve les formulations exactes.\n"
                            "- Conserve les dates exactement telles "
                            "qu'elles apparaissent.\n"
                            "- Écris [illisible] si un passage "
                            "n'est pas suffisamment lisible.\n"
                            "- Écris [mot incertain : proposition] "
                            "si un mot reste incertain.\n"
                            "- Retourne uniquement la transcription."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url,
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    print("\n--- TRANSCRIPTION SOL ---\n")
    print(reponse.output_text.strip())

    usage = getattr(
        reponse,
        "usage",
        None,
    )

    if usage:
        print("\n--- UTILISATION ---")
        print(
            f"Tokens d'entrée : "
            f"{usage.input_tokens}"
        )
        print(
            f"Tokens de sortie : "
            f"{usage.output_tokens}"
        )
        print(
            f"Tokens totaux : "
            f"{usage.total_tokens}"
        )


if __name__ == "__main__":
    main()