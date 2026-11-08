import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class Base(DeclarativeBase):
    pass


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow)

    items: Mapped[list["Item"]] = relationship(back_populates="room")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Null for a top-level category. Exactly one level of nesting is allowed; the router is
    # what enforces that, since a self-referencing column cannot express a depth limit.
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), name="parent_id"
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow)

    items: Mapped[list["Item"]] = relationship(back_populates="category")
    children: Mapped[list["Category"]] = relationship(
        back_populates="parent", order_by="Category.sort_order"
    )
    parent: Mapped["Category | None"] = relationship(
        back_populates="children", remote_side="Category.id"
    )


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("purchase_price_minor IS NULL OR purchase_price_minor >= 0"),
        CheckConstraint("quantity >= 1", name="ck_items_quantity_positive"),
        Index("ix_items_room_id", "room_id"),
        Index("ix_items_category_id", "category_id"),
        Index("ix_items_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str | None] = mapped_column(String)
    descriptor_notes: Mapped[str | None] = mapped_column(Text)
    purchase_price_minor: Mapped[int | None] = mapped_column(Integer)
    # How many of the thing this row stands for. The price above is per one of them.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    currency: Mapped[str | None] = mapped_column(String(3))
    # Bought used. Says nothing about the price — what was paid is what was paid — but it is
    # why a shirt cost a third of its shop price, and it is worth knowing years later.
    second_hand: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Set once the thing has been given away. It stops being part of the inventory but the row
    # stays, so what it was and what it cost are not lost.
    gifted_at: Mapped[str | None] = mapped_column(String)
    gifted_to: Mapped[str | None] = mapped_column(String)
    purchase_date: Mapped[str | None] = mapped_column(String)
    serial_number: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)

    image_key: Mapped[str | None] = mapped_column(String)
    thumb_key: Mapped[str | None] = mapped_column(String)
    receipt_key: Mapped[str | None] = mapped_column(String)
    # The photograph the owner took, kept when a generated product photo replaces it above.
    source_image_key: Mapped[str | None] = mapped_column(String)

    room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"))
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )

    # Field names the model suggested and the owner left untouched, so the UI can keep marking
    # them as suggestions after a reload. Carries no behaviour.
    ai_suggested_fields: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow, onupdate=utcnow)

    room: Mapped[Room | None] = relationship(back_populates="items")
    category: Mapped[Category | None] = relationship(back_populates="items")
    placements: Mapped[list["BoardItem"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class Board(Base):
    __tablename__ = "boards"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow, onupdate=utcnow)

    placements: Mapped[list["BoardItem"]] = relationship(
        back_populates="board", cascade="all, delete-orphan", order_by="BoardItem.z_index"
    )


class BoardItem(Base):
    __tablename__ = "board_items"
    __table_args__ = (
        UniqueConstraint("board_id", "item_id"),
        CheckConstraint("scale > 0"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    board_id: Mapped[str] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    # Canvas units in a fixed 1000x1000 space, not pixels, so a board laid out on a laptop
    # reopens correctly on a phone.
    position_x: Mapped[float] = mapped_column(Float, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, nullable=False)
    scale: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    z_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    board: Mapped[Board] = relationship(back_populates="placements")
    item: Mapped[Item] = relationship(back_populates="placements")


SEED_ROOMS = ["Kitchen", "Bedroom", "Lounge", "Bathroom", "Storage Room", "Closet"]
SEED_CATEGORIES = [
    "Furniture",
    "Lighting",
    "Electronics",
    "Major Appliances",
    "Small Appliances",
    "Kitchenware",
    "Bedding & Linen",
    "Bathroom & Grooming",
    "Tools",
    "Decor",
    "Clothing & Accessories",
    "Miscellaneous",
]
# Shelves, by the category they hang under. Kitchenware alone was doing the work of a dozen —
# a cooking spoon, a bread knife and a 5.5 L casserole all landed in it. The names follow the
# Google product taxonomy's Kitchen & Dining branch, in British usage: "Cutlery" is what goes
# on the table, and "crockery" and "plates and bowls" are one shelf under its trade name,
# Dinnerware.
#
# Towels live under Bedding & Linen rather than Bathroom & Grooming so that they have exactly
# one home — a beach towel is not a bathroom item, and splitting them by intended use would
# mean deciding case by case where each one belongs.
SEED_SUBCATEGORIES = {
    "Kitchenware": [
        "Cookware",
        "Bakeware",
        "Kitchen Knives",
        "Cutting Boards",
        "Kitchen Tools & Utensils",
        "Dinnerware",
        "Serveware & Trays",
        "Drinkware & Glassware",
        "Cutlery",
        "Barware",
        "Food Storage",
        "Kitchen Textiles",
    ],
    "Bedding & Linen": [
        "Bed Linen",
        "Duvets & Pillows",
        "Blankets & Throws",
        "Towels",
    ],
    "Bathroom & Grooming": [
        "Bathroom Storage",
        "Bathroom Fittings",
        "Grooming & Personal Care",
    ],
    # Shelved by the part of an outfit each fills, not by garment type. Dressing means picking
    # a top, then a bottom, then shoes — a shirt and a t-shirt answer the same question, so
    # splitting them would put one decision across two shelves. What kind of top it is lives
    # in the name, where it is read.
    "Clothing & Accessories": [
        "Tops",
        "Bottoms",
        "Outerwear",
        "Shoes",
        "Accessories",
    ],
}
