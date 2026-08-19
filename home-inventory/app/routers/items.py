import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_session
from app.config import Settings, get_settings
from app.db import get_session, save_snapshot
from app.deps import get_storage, to_detail, to_summary
from app.extract import ExtractionUnavailable, _to_minor, suggest_item
from app.imaging import UnreadableImage, extension_for, make_thumbnail
from app.models import Category, Item, Room, new_id
from app.schemas import ItemDetail, ItemPage, ItemWrite, SuggestionResponse
from app.scrape import BlockedUrl, PageMetadata, download_image, fetch_page_metadata
from app.storage import MediaStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/items", tags=["items"], dependencies=[Depends(require_session)])


def _sane_date(value: str | None) -> str | None:
    """Drop a suggested date that is malformed or in the future rather than raising: the
    owner is being offered a form to correct, not making a write."""
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return None if parsed > date.today() else value


def _parse_payload(payload: str | None) -> ItemWrite:
    if not payload:
        return ItemWrite()
    try:
        return ItemWrite.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.errors(include_url=False)[0]["msg"])


async def _read_upload(upload: UploadFile, settings: Settings) -> bytes:
    data = await upload.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"That image is larger than {settings.max_upload_bytes // (1024 * 1024)} MB",
        )
    return data


def _store_image(
    storage: MediaStorage, item_id: str, data: bytes, content_type: str
) -> tuple[str, str]:
    """Save the original and a thumbnail; return their keys."""
    try:
        thumb = make_thumbnail(data)
    except UnreadableImage as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"That file is not a readable image: {exc}"
        )

    image_key = f"items/{item_id}/original.{extension_for(content_type)}"
    thumb_key = f"items/{item_id}/thumb.webp"
    storage.put(image_key, data, content_type)
    storage.put(thumb_key, thumb, "image/webp")
    return image_key, thumb_key


def _apply(item: Item, body: ItemWrite, fields_sent: set[str]) -> None:
    for field in (
        "name",
        "brand",
        "descriptor_notes",
        "purchase_price_minor",
        "currency",
        "quantity",
        "serial_number",
        "source_url",
        "room_id",
        "category_id",
    ):
        if field in fields_sent:
            setattr(item, field, getattr(body, field))
    if "purchase_date" in fields_sent:
        item.purchase_date = body.purchase_date.isoformat() if body.purchase_date else None
    if "ai_suggested_fields" in fields_sent:
        item.ai_suggested_fields = json.dumps(body.ai_suggested_fields)


def _validate_refs(session: Session, body: ItemWrite, fields_sent: set[str]) -> None:
    if body.room_id and "room_id" in fields_sent and session.get(Room, body.room_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That room does not exist")
    if (
        body.category_id
        and "category_id" in fields_sent
        and session.get(Category, body.category_id) is None
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That category does not exist")


@router.get("", response_model=ItemPage)
def list_items(
    q: str | None = None,
    room_id: str | None = None,
    category_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> ItemPage:
    limit = max(1, min(limit, 200))
    filters = []
    if room_id:
        filters.append(Item.room_id == room_id)
    if category_id:
        # Categories nest one level. Picking a parent has to show what is on its shelves, or
        # clicking "Kitchenware" returns nothing once everything is filed under Cookware.
        children = session.scalars(
            select(Category.id).where(Category.parent_id == category_id)
        ).all()
        filters.append(Item.category_id.in_([category_id, *children]))
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(Item.name.ilike(like), Item.brand.ilike(like), Item.descriptor_notes.ilike(like))
        )

    total = session.scalar(select(func.count(Item.id)).where(*filters)) or 0
    rows = session.scalars(
        select(Item)
        .where(*filters)
        .options(joinedload(Item.room), joinedload(Item.category))
        .order_by(Item.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ItemPage(items=[to_summary(i) for i in rows], total=total)


@router.post("/suggest", response_model=SuggestionResponse)
async def suggest(
    image: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    note: str | None = Form(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SuggestionResponse:
    """Suggestions only — this creates nothing (constitution principle III).

    One endpoint for all three ways in, because they are the same question asked with
    different evidence, and the owner can supply any combination: a photo of a lamp plus
    "bought from IKEA in June 2025, in the lounge" is better than either alone.
    """
    import httpx

    if image is None and not url and not note:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Give me a photo, a link, or something typed"
        )

    page: PageMetadata | None = None
    if url:
        try:
            page = await fetch_page_metadata(url, settings.scrape_timeout_seconds)
        except BlockedUrl as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        except httpx.TimeoutException:
            raise HTTPException(
                status.HTTP_504_GATEWAY_TIMEOUT, "That page took too long to respond"
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Could not read that page: {exc}")

    data = await _read_upload(image, settings) if image is not None else None
    categories = session.scalars(select(Category).order_by(Category.sort_order)).all()
    rooms = session.scalars(select(Room).order_by(Room.sort_order)).all()
    tops = [c for c in categories if c.parent_id is None]
    shelves = [c for c in categories if c.parent_id is not None]

    try:
        suggestion = suggest_item(
            settings,
            categories=[c.name for c in tops],
            subcategories=[c.name for c in shelves],
            rooms=[r.name for r in rooms],
            image=data,
            content_type=image.content_type if image is not None else None,
            page=page.digest if page else None,
            note=note,
        )
    except ExtractionUnavailable as exc:
        # A page we fetched is still worth something without the model: this is exactly the
        # old behaviour, so the link path never gets worse than it was.
        if page is not None:
            logger.warning("Falling back to page metadata: %s", exc)
            return SuggestionResponse(
                name=page.title or "",
                source_url=url,
                image_url=page.image_url,
                suggested_fields=["name"] if page.title else [],
            )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Could not work that out: {exc}")

    # Case-insensitively, and tolerating a name that is in nobody's list. The JSON-schema
    # enum turns out to be guidance rather than a guarantee: asked about a lamp with only
    # kitchen shelves on offer, the model answered "Lighting", and asked about "in lounge" it
    # answered "lounge". Both have to survive, so resolution happens here rather than being
    # trusted to the schema.
    def resolve(entities, name: str | None):
        if not name:
            return None
        wanted = name.strip().casefold()
        return next((e for e in entities if e.name.casefold() == wanted), None)

    # The shelf if the model picked one we recognise, otherwise the top-level category.
    category = resolve(categories, suggestion.subcategory) or resolve(
        categories, suggestion.category
    )
    room = resolve(rooms, suggestion.room)
    price_minor = _to_minor(suggestion.price)

    filled = {
        "name": suggestion.name,
        "brand": suggestion.brand,
        "descriptor_notes": suggestion.descriptor_notes,
        "category": category,
        "room": room,
        "purchase_date": _sane_date(suggestion.purchase_date),
        "quantity": suggestion.quantity if suggestion.quantity > 1 else None,
        "price": price_minor,
    }
    return SuggestionResponse(
        name=suggestion.name,
        brand=suggestion.brand,
        descriptor_notes=suggestion.descriptor_notes,
        category_id=category.id if category else None,
        room_id=room.id if room else None,
        purchase_price_minor=price_minor,
        currency=suggestion.currency if price_minor is not None else None,
        purchase_date=_sane_date(suggestion.purchase_date),
        quantity=suggestion.quantity,
        source_url=url,
        image_url=page.image_url if page else None,
        suggested_fields=[field for field, value in filled.items() if value],
    )


@router.get("/{item_id}", response_model=ItemDetail)
def get_item(item_id: str, session: Session = Depends(get_session)) -> ItemDetail:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such item")
    return to_detail(item)


@router.post("", response_model=ItemDetail, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: str = Form(...),
    image: UploadFile | None = File(default=None),
    receipt: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    storage: MediaStorage = Depends(get_storage),
) -> ItemDetail:
    body = _parse_payload(payload)
    if not body.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An item needs a name")
    fields_sent = set(ItemWrite.model_validate_json(payload).model_dump().keys())
    _validate_refs(session, body, fields_sent)

    # The id is assigned here rather than left to the column default, because the image keys are
    # built from it before the row is ever flushed.
    item = Item(id=new_id(), name=body.name)
    _apply(item, body, fields_sent)

    if image is not None:
        data = await _read_upload(image, settings)
        item.image_key, item.thumb_key = _store_image(
            storage, item.id, data, image.content_type or "image/jpeg"
        )
    elif body.source_image_url:
        try:
            data, content_type = await download_image(
                body.source_image_url, settings.scrape_timeout_seconds, settings.max_upload_bytes
            )
        except BlockedUrl as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        item.image_key, item.thumb_key = _store_image(storage, item.id, data, content_type)

    if receipt is not None:
        data = await _read_upload(receipt, settings)
        key = f"items/{item.id}/receipt.{extension_for(receipt.content_type or '')}"
        storage.put(key, data, receipt.content_type or "application/octet-stream")
        item.receipt_key = key

    session.add(item)
    session.commit()
    save_snapshot()
    return to_detail(item)


@router.patch("/{item_id}", response_model=ItemDetail)
async def update_item(
    item_id: str,
    payload: str = Form(...),
    image: UploadFile | None = File(default=None),
    receipt: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    storage: MediaStorage = Depends(get_storage),
) -> ItemDetail:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such item")

    body = _parse_payload(payload)
    fields_sent = set(json.loads(payload).keys())
    if "name" in fields_sent and not body.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An item needs a name")
    _validate_refs(session, body, fields_sent)
    _apply(item, body, fields_sent)

    if image is not None:
        data = await _read_upload(image, settings)
        previous = (item.image_key, item.thumb_key)
        # Write the replacement before dropping the old files: if the new image turns out to be
        # unreadable, the item keeps the photo it already had.
        item.image_key, item.thumb_key = _store_image(
            storage, item.id, data, image.content_type or "image/jpeg"
        )
        for old in previous:
            if old and old not in (item.image_key, item.thumb_key):
                storage.delete(old)
    if receipt is not None:
        data = await _read_upload(receipt, settings)
        if item.receipt_key:
            storage.delete(item.receipt_key)
        key = f"items/{item.id}/receipt.{extension_for(receipt.content_type or '')}"
        storage.put(key, data, receipt.content_type or "application/octet-stream")
        item.receipt_key = key

    session.commit()
    save_snapshot()
    return to_detail(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: str,
    session: Session = Depends(get_session),
    storage: MediaStorage = Depends(get_storage),
) -> None:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such item")
    for key in (item.image_key, item.thumb_key, item.receipt_key):
        if key:
            storage.delete(key)
    session.delete(item)
    session.commit()
    save_snapshot()
