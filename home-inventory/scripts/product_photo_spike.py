"""Prove that Gemini can turn a photograph of a possession into a product photo of it.

The owner's photograph of a garment is a garment on a rail, in a pile, or on the bed, next to
three other garments. A product photo is that one object, alone, lit evenly, on white. This
asks the image model to do that conversion and writes the answer out to look at.

    uv run python scripts/product_photo_spike.py --name "ochre cotton jacket"

Writes nothing to the database or to the app's storage. Needs application default credentials
(`gcloud auth application-default login`), because Vertex is a real call.
"""

import argparse
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings

# A cluttered rail: an ochre jacket, a pink blouse, a belt and folded jeans, all overlapping.
# Deliberately not a studio shot — the whole question is whether one object can be lifted out
# of the sort of photo somebody actually takes of their own wardrobe. CC0, Unsplash via
# Wikimedia Commons.
PHOTO = "https://commons.wikimedia.org/wiki/Special:FilePath/Wardrobe%20(Unsplash).jpg?width=1200"
# Wikimedia refuses the default httpx user agent.
AGENT = "my-stuff-inventory-spike/1.0 (https://github.com/jonathanjayes)"

PROMPT = (
    "This is the owner's own photograph of something they own. Produce a product photograph "
    "of the {name} in it, and nothing else: the single object alone on a plain white "
    "background, front on, evenly lit, no hanger, no rail, no hands, no other garments, no "
    "text or watermark. Keep its exact colour, pattern, material, proportions and any visible "
    "wear — this is a photograph of one specific object that someone owns, not a new design."
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="ochre cotton jacket", help="Which object to lift out")
    parser.add_argument("--url", default=PHOTO, help="Photograph to work from")
    parser.add_argument("--out", default="spike-product-photo", help="Output path, no extension")
    parser.add_argument("--model", default="gemini-3.1-flash-image")
    args = parser.parse_args()

    from google import genai
    from google.genai import types

    settings = Settings()

    source = httpx.get(args.url, headers={"User-Agent": AGENT}, follow_redirects=True)
    source.raise_for_status()
    mime = source.headers.get("content-type", "image/jpeg").split(";")[0]
    print(f"Source: {len(source.content):,} bytes of {mime}")

    client = genai.Client(
        vertexai=True, project=settings.gcp_project, location=settings.gemini_location
    )
    started = time.monotonic()
    response = client.models.generate_content(
        model=args.model,
        contents=[
            types.Part.from_bytes(data=source.content, mime_type=mime),
            PROMPT.format(name=args.name),
        ],
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    print(f"Answered in {time.monotonic() - started:.1f}s")

    for part in response.candidates[0].content.parts:
        if part.text:
            print(f"Model said: {part.text.strip()[:300]}")
        if part.inline_data:
            data = part.inline_data.data
            suffix = part.inline_data.mime_type.split("/")[-1]
            out = Path(f"{args.out}.{suffix}")
            out.write_bytes(data)
            print(f"Wrote {out} — {len(data):,} bytes of {part.inline_data.mime_type}")
            return 0

    print("No image came back. The model answered with text only.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
