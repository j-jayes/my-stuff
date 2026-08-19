import uuid
from datetime import UTC, datetime

from sqlalchemy import (
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
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow)

    items: Mapped[list["Item"]] = relationship(back_populates="category")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("purchase_price_minor IS NULL OR purchase_price_minor >= 0"),
        Index("ix_items_room_id", "room_id"),
        Index("ix_items_category_id", "category_id"),
        Index("ix_items_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str | None] = mapped_column(String)
    descriptor_notes: Mapped[str | None] = mapped_column(Text)
    purchase_price_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    purchase_date: Mapped[str | None] = mapped_column(String)
    serial_number: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String)

    image_key: Mapped[str | None] = mapped_column(String)
    thumb_key: Mapped[str | None] = mapped_column(String)
    receipt_key: Mapped[str | None] = mapped_column(String)

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


SEED_ROOMS = ["Kitchen", "Bedroom", "Lounge", "Bathroom", "Storage Room"]
SEED_CATEGORIES = [
    "Furniture",
    "Electronics",
    "Major Appliances",
    "Small Appliances",
    "Kitchenware",
    "Tools",
    "Decor",
    "Clothing & Accessories",
    "Miscellaneous",
]
