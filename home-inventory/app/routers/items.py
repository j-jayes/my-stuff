import json
import logging
import re
import unicodedata
from datetime import date
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_session
from app.config import Settings, get_settings
from app.db import get_session, save_snapshot
from app.deps import get_storage, to_detail, to_summary
from app.extract import (
    ExtractionUnavailable,
    _to_minor,
    find_product_page,
    resolve_name,
    suggest_item,
)
from app.ikea import matches as ikea_matches
from app.ikea import query_for as ikea_query_for
from app.ikea import search as ikea_search
from app.imaging import UnreadableImage, extension_for, make_thumbnail
from app.models import Category, Item, Room, new_id
from app.schemas import (
    BrandEntry,
    ItemDetail,
    ItemPage,
    ItemSummary,
    ItemWrite,
    SuggestionResponse,
)
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


def _normalised_brand(session: Session, brand: str | None) -> str | None:
    """Reuse the spelling already in use for this brand, ignoring case.

    The database holds both "IKEA" and "Ikea" as separate brands. One is a typo and there is
    no telling which, so whichever arrived first wins from then on and the two stop drifting.
    """
    cleaned = (brand or "").strip()
    if not cleaned:
        return None
    # Whichever spelling most items already use, so the answer does not depend on scan order.
    existing = session.scalar(
        select(Item.brand)
        .where(func.lower(Item.brand) == cleaned.lower())
        .group_by(Item.brand)
        .order_by(func.count(Item.id).desc(), Item.brand)
        .limit(1)
    )
    return existing or cleaned


def _apply(item: Item, body: ItemWrite, fields_sent: set[str], session: Session) -> None:
    if "brand" in fields_sent:
        body = body.model_copy(update={"brand": _normalised_brand(session, body.brand)})
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


async def _search_for_page(note: str, settings: Settings) -> tuple[str | None, PageMetadata | None]:
    """Find and vet a product page for something described only in words.

    Everything here is best-effort: no photograph is a perfectly good outcome, so nothing
    raises. A page that cannot be fetched, or turns out to be about something else, is simply
    not used.
    """
    import httpx

    candidate = None
    if "ikea" in note.casefold():
        # Their own search knows the article number; a model only knows the shape of one, and
        # an invented one redirects to the catalogue and answers 200.
        query = ikea_query_for(note)
        product = await ikea_search(query, settings.scrape_timeout_seconds)
        if product and not ikea_matches(query, product):
            logger.info("IKEA answered %s for %r; not the same product", product.url, query)
        elif product:
            candidate = product.url
        if not candidate:
            # No falling back to a web search for an IKEA product. IKEA's own catalogue is
            # the authority on what IKEA sells, and asking a model instead is how a
            # nickel-plated FORSÅ came back for a white one — right lamp, wrong finish, and
            # a photograph that looks perfectly correct.
            return None, None

    if not candidate:
        candidate = find_product_page(note, settings)
    if not candidate:
        return None, None
    try:
        found = await fetch_page_metadata(candidate, settings.scrape_timeout_seconds)
    except (BlockedUrl, httpx.HTTPError) as exc:
        logger.info("Product page %s could not be read: %s", candidate, exc)
        return None, None

    if not _page_is_about(note, found, candidate):
        logger.info("Product page %s is not about %r; ignoring it", candidate, note[:60])
        return None, None
    return candidate, found


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
    elif note and image is None:
        # Words alone had no picture and no price. Go and look for the product page — but the
        # owner's own photograph, when there is one, is of their actual thing and beats any
        # stock shot, so this only runs when there is no image.
        url, page = await _search_for_page(note, settings)

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

    def resolve(entities, answer: str | None):
        matched = resolve_name([e.name for e in entities], answer)
        return next((e for e in entities if e.name == matched), None)

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


# Words too common in a home inventory to mean two things are the same item.
COMMON_WORDS = frozenset(
    {"the", "and", "with", "for", "chair", "table", "lamp", "shelf", "unit", "set", "cm", "mm"}
)


def _fold(text: str) -> str:
    """Casefold and strip accents, so POANG and POÄNG are the same word.

    The model writes what it can type; the inventory holds what the shop printed. Without
    this, the duplicate that prompted the whole feature — POÄNG entered twice — is invisible.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _distinctive_words(name: str) -> set[str]:
    words = re.findall(r"[\w]+", _fold(name))
    return {w for w in words if len(w) > 2 and w not in COMMON_WORDS}


def _page_is_about(note: str, page: PageMetadata, url: str) -> bool:
    """Is a page the model went and found actually about the thing the owner described?

    "It fetched successfully" proves nothing: a product URL that does not exist redirects to
    the retailer's catalogue and answers 200. Attaching that page's photograph to the item
    would be worse than leaving it without one, because a wrong photograph looks right.

    The check is a shared distinctive word between the note and the page title, ignoring any
    word that is already in the hostname — every page on ikea.com says IKEA, so the brand on
    its own is no evidence at all. It is the same reasoning as the duplicate check, where a
    shared brand is not enough to call two things the same.
    """
    site_words = _distinctive_words(urlparse(url).hostname or "")
    wanted = _distinctive_words(note) - site_words
    found = _distinctive_words(page.title or "") - site_words
    return bool(wanted & found)


@router.get("/similar", response_model=list[ItemSummary])
def list_similar(name: str, session: Session = Depends(get_session)) -> list[ItemSummary]:
    """Items that look like the one being added. A warning for the client to show, never a
    block — two identical chairs is a real thing to own.

    Done here rather than by reusing the search endpoint because SQL LIKE cannot fold an
    accent, and matching on the whole suggested name finds nothing: "Poang armchair" shares
    no substring with "POÄNG".
    """
    wanted = _distinctive_words(name)
    if not wanted:
        return []

    # Small inventories, and the comparison needs accent folding that SQLite will not do.
    # If this ever needs an index it needs a different design, not a cleverer query.
    # Brand is deliberately not part of this: owning two IKEA things is normal, so a shared
    # brand with no shared word is not a duplicate.
    matches = [
        item
        for item in session.scalars(
            select(Item).options(joinedload(Item.room), joinedload(Item.category))
        )
        if wanted & _distinctive_words(item.name)
    ]
    return [to_summary(item) for item in matches[:5]]


@router.get("/brands", response_model=list[BrandEntry])
def list_brands(session: Session = Depends(get_session)) -> list[BrandEntry]:
    """Feeds the brand field's autocomplete. Registered above /{item_id}, or the path
    parameter would match "brands" and try to look it up as an id."""
    rows = session.execute(
        select(Item.brand, func.count(Item.id))
        .where(Item.brand.isnot(None), Item.brand != "")
        .group_by(Item.brand)
        .order_by(func.count(Item.id).desc(), Item.brand)
    ).all()
    return [BrandEntry(name=name, item_count=count) for name, count in rows]


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
    _apply(item, body, fields_sent, session)

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
    _apply(item, body, fields_sent, session)

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
