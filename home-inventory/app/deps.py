"""Shared dependencies and the serialisers that turn ORM rows into API responses."""

import json

from app.models import Item
from app.schemas import ItemDetail, ItemSummary, NamedRef
from app.storage import GcsMediaStorage, LocalMediaStorage, MediaStorage

_storage: MediaStorage | None = None


def init_storage(settings) -> None:
    global _storage
    if settings.storage_backend == "gcs":
        _storage = GcsMediaStorage(settings.media_bucket, project=settings.gcp_project)
    else:
        _storage = LocalMediaStorage(settings.local_media_dir)


def set_storage(storage: MediaStorage) -> None:
    """Used by tests to inject a storage backend without touching the filesystem twice."""
    global _storage
    _storage = storage


def get_storage() -> MediaStorage:
    assert _storage is not None, "storage has not been initialised"
    return _storage


def media_url(key: str | None) -> str | None:
    return f"/api/media/{key}" if key else None


def _ref(entity) -> NamedRef | None:
    return NamedRef(id=entity.id, name=entity.name) if entity else None


def to_summary(item: Item) -> ItemSummary:
    return ItemSummary(
        id=item.id,
        name=item.name,
        brand=item.brand,
        thumb_url=media_url(item.thumb_key),
        room=_ref(item.room),
        category=_ref(item.category),
        purchase_price_minor=item.purchase_price_minor,
        currency=item.currency,
        quantity=item.quantity,
        created_at=item.created_at,
    )


def to_detail(item: Item) -> ItemDetail:
    # Price and currency come through the summary spread; passing them again here would be a
    # duplicate keyword argument.
    return ItemDetail(
        **to_summary(item).model_dump(),
        descriptor_notes=item.descriptor_notes,
        second_hand=item.second_hand,
        purchase_date=item.purchase_date,
        serial_number=item.serial_number,
        source_url=item.source_url,
        image_url=media_url(item.image_key),
        receipt_url=media_url(item.receipt_key),
        ai_suggested_fields=json.loads(item.ai_suggested_fields) if item.ai_suggested_fields else [],
        updated_at=item.updated_at,
    )
