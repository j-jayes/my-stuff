"""The one page that adds the money up.

The headline figures are worked out here; everything that can be sliced (by shop, room, brand, year)
is left to the page, which gets one row per item and can cross them any way it likes.

Amounts stay in the currency they were paid in. Summing kronor and dollars would need an exchange
rate for each purchase date, and a total built on a guessed rate looks more certain than it is.
"""

import re
from collections import defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_session
from app.db import get_session
from app.deps import media_url
from app.models import Category, Item

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(require_session)])

HOME_CURRENCY = "SEK"
NOT_RECORDED = "Not recorded"
UNNAMED = "Not named"
# Imports end an item's notes with "Sellpy order Abc123, line 2." There is no shop column, so this
# reference is the only record of where most things came from.
ORDER_REFERENCE = re.compile(r"(?:^|\. )([^.]+\.?) order \S+, line \d+\.$")


class Row(BaseModel):
    label: str
    entries: int
    spent: dict[str, int]


class StatItem(BaseModel):
    id: str
    name: str
    brand: str | None
    shop: str
    room: str | None
    category: str | None
    minor: int | None
    currency: str | None
    quantity: int
    date: str | None
    second_hand: bool
    thumb_url: str | None


class Stats(BaseModel):
    entries: int
    units: int
    unpriced: int
    totals: dict[str, int]
    second_hand_entries: int
    second_hand_totals: dict[str, int]
    items: list[StatItem]
    gifts: list[Row]


def _line_total(item: Item) -> int | None:
    if item.purchase_price_minor is None or not item.currency:
        return None
    return item.purchase_price_minor * item.quantity


def _sum(items: list[Item]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for item in items:
        line = _line_total(item)
        if line is not None:
            totals[item.currency] += line
    return dict(totals)


def _shop(item: Item) -> str:
    reference = ORDER_REFERENCE.search(item.descriptor_notes or "")
    if reference:
        return reference[1]
    # IKEA is the one brand that is also the only place to buy it new.
    if (item.brand or "").lower() == "ikea" and not item.second_hand:
        return "IKEA"
    return NOT_RECORDED


def _category(item: Item) -> str | None:
    if item.category is None:
        return None
    return (item.category.parent or item.category).name


def _stat_item(item: Item) -> StatItem:
    return StatItem(
        id=item.id,
        name=item.name,
        brand=item.brand,
        shop=_shop(item),
        room=item.room.name if item.room else None,
        category=_category(item),
        minor=_line_total(item),
        currency=item.currency,
        quantity=item.quantity,
        date=item.purchase_date,
        second_hand=item.second_hand,
        thumb_url=media_url(item.thumb_key, item.updated_at),
    )


def _gifts_by_person(gifts: list[Item]) -> list[Row]:
    people: dict[str, list[Item]] = defaultdict(list)
    for item in gifts:
        people[item.gifted_to or UNNAMED].append(item)
    rows = [Row(label=k, entries=len(v), spent=_sum(v)) for k, v in people.items()]
    return sorted(rows, key=lambda row: (-row.spent.get(HOME_CURRENCY, 0), row.label))


@router.get("", response_model=Stats)
def stats(session: Session = Depends(get_session)) -> Stats:
    everything = list(
        session.scalars(
            select(Item).options(
                joinedload(Item.room), joinedload(Item.category).joinedload(Category.parent)
            )
        )
    )
    items = [item for item in everything if item.gifted_at is None]
    second_hand = [item for item in items if item.second_hand]

    return Stats(
        entries=len(items),
        units=sum(item.quantity for item in items),
        unpriced=sum(1 for item in items if _line_total(item) is None),
        totals=_sum(items),
        second_hand_entries=len(second_hand),
        second_hand_totals={k: v for k, v in _sum(second_hand).items() if v},
        items=[_stat_item(item) for item in items],
        gifts=_gifts_by_person([item for item in everything if item.gifted_at is not None]),
    )
