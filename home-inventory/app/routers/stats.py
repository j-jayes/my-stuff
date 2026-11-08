"""The one page that adds the money up.

Amounts stay in the currency they were paid in. Summing kronor and dollars would need an exchange
rate for each purchase date, and a total built on a guessed rate looks more certain than it is.
"""

import re
from collections import defaultdict
from collections.abc import Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_session
from app.db import get_session
from app.models import Category, Item

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(require_session)])

HOME_CURRENCY = "SEK"
TOP_ITEMS = 8
NOT_RECORDED = "Not recorded"
UNDATED = "Undated"
# Imports end an item's notes with "Sellpy order Abc123, line 2." There is no shop column, so this
# reference is the only record of where most things came from.
ORDER_REFERENCE = re.compile(r"(?:^|\. )([^.]+\.?) order \S+, line \d+\.$")


class Row(BaseModel):
    label: str
    entries: int
    spent: dict[str, int]


class TopItem(BaseModel):
    id: str
    name: str
    brand: str | None
    minor: int
    currency: str


class Stats(BaseModel):
    entries: int
    units: int
    unpriced: int
    totals: dict[str, int]
    second_hand_entries: int
    second_hand_totals: dict[str, int]
    by_shop: list[Row]
    by_category: list[Row]
    by_room: list[Row]
    by_year: list[Row]
    most_expensive: list[TopItem]


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


def _year(item: Item) -> str:
    return item.purchase_date[:4] if item.purchase_date else UNDATED


def _category(item: Item) -> str:
    if item.category is None:
        return "No category"
    return (item.category.parent or item.category).name


def _rows(items: list[Item], key: Callable[[Item], str]) -> list[Row]:
    groups: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        groups[key(item)].append(item)
    return [
        Row(label=label, entries=len(members), spent=_sum(members))
        for label, members in groups.items()
    ]


def _by_spend(rows: list[Row]) -> list[Row]:
    return sorted(rows, key=lambda row: (-row.spent.get(HOME_CURRENCY, 0), row.label))


@router.get("", response_model=Stats)
def stats(session: Session = Depends(get_session)) -> Stats:
    items = list(
        session.scalars(
            select(Item)
            .where(Item.gifted_at.is_(None))
            .options(joinedload(Item.room), joinedload(Item.category).joinedload(Category.parent))
        )
    )
    second_hand = [item for item in items if item.second_hand]
    home = [item for item in items if item.currency == HOME_CURRENCY and _line_total(item)]
    top = sorted(home, key=lambda item: -_line_total(item))[:TOP_ITEMS]

    return Stats(
        entries=len(items),
        units=sum(item.quantity for item in items),
        unpriced=sum(1 for item in items if _line_total(item) is None),
        totals=_sum(items),
        second_hand_entries=len(second_hand),
        second_hand_totals={k: v for k, v in _sum(second_hand).items() if v},
        by_shop=_by_spend(_rows(items, _shop)),
        by_category=_by_spend(_rows(items, _category)),
        by_room=_by_spend(_rows(items, lambda item: item.room.name if item.room else "No room")),
        # An empty sort key puts Undated after every year once the order is reversed.
        by_year=sorted(
            _rows(items, _year), key=lambda r: "" if r.label == UNDATED else r.label, reverse=True
        ),
        most_expensive=[
            TopItem(id=i.id, name=i.name, brand=i.brand, minor=_line_total(i), currency=i.currency)
            for i in top
        ],
    )
