"""Ask Gemini what an item is, from its photo.

The model's answer is a suggestion that lands in an editable form; it is never written straight
to the database (constitution principle III).
"""

import logging
from functools import lru_cache

from pydantic import BaseModel, Field

from app.config import Settings

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "You catalogue household possessions for a personal home inventory. Identify the single "
    "main object in the photo. Be concise and factual. Leave brand null unless a logo or "
    "marking is actually visible in the photo — never guess a brand from the style of an object."
)

PROMPT = "Identify the main household object in this photo for a home inventory."


class ItemSuggestion(BaseModel):
    name: str = Field(description="A concise, descriptive name for the item.")
    category: str = Field(description="The best-fitting category from the supplied list.")
    brand: str | None = Field(default=None, description="Brand or maker, only if visible.")
    descriptor_notes: str | None = Field(
        default=None, description="One short sentence on colour, material, or notable features."
    )


class ExtractionUnavailable(Exception):
    """The model could not be reached or did not answer. The caller falls back to a blank form."""


@lru_cache
def _client(project: str, location: str):
    """One client for the process. Rebuilding it per request closes the underlying HTTP pool
    out from under the in-flight call."""
    from google import genai

    return genai.Client(vertexai=True, project=project, location=location)


def suggest_item(
    image: bytes, content_type: str, category_names: list[str], settings: Settings
) -> ItemSuggestion:
    """Return suggestions for a photo, or raise ExtractionUnavailable.

    Vertex accepts HEIC and HEIF directly, so no conversion happens on this path.
    """
    from google.genai import types

    # Constraining the category to the owner's actual list removes the "model invented a
    # category" case at the source, rather than filtering it out afterwards.
    schema = ItemSuggestion.model_json_schema()
    schema["properties"]["category"]["enum"] = category_names

    try:
        response = _client(settings.gcp_project, settings.gemini_location).models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=image, mime_type=content_type),
                PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema,
                system_instruction=SYSTEM_INSTRUCTION,
                thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
                http_options=types.HttpOptions(timeout=int(settings.extract_timeout_seconds * 1000)),
            ),
        )
    except Exception as exc:
        logger.warning("Gemini extraction failed: %s", exc)
        raise ExtractionUnavailable(str(exc)) from exc

    if not response.text:
        raise ExtractionUnavailable("The model returned an empty response")
    try:
        return ItemSuggestion.model_validate_json(response.text)
    except ValueError as exc:
        logger.warning("Gemini returned unparseable JSON: %s", response.text[:200])
        raise ExtractionUnavailable("The model returned an unusable answer") from exc
