from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    password: str


class NamedRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class TaxonomyEntry(NamedRef):
    item_count: int = 0


class TaxonomyWrite(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned


class ItemWrite(BaseModel):
    """Fields the owner can set. Every one except name is optional (FR-009)."""

    name: str | None = None
    brand: str | None = None
    descriptor_notes: str | None = None
    purchase_price_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    purchase_date: date | None = None
    serial_number: str | None = None
    source_url: str | None = None
    source_image_url: str | None = None
    room_id: str | None = None
    category_id: str | None = None
    ai_suggested_fields: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("purchase_date")
    @classmethod
    def not_in_the_future(cls, value: date | None) -> date | None:
        from datetime import date as _date

        if value and value > _date.today():
            raise ValueError("Purchase date cannot be in the future")
        return value

    @model_validator(mode="after")
    def currency_accompanies_price(self) -> "ItemWrite":
        if self.purchase_price_minor is not None and not self.currency:
            raise ValueError("A currency is required when a price is given")
        return self


class ItemSummary(BaseModel):
    id: str
    name: str
    brand: str | None
    thumb_url: str | None
    room: NamedRef | None
    category: NamedRef | None
    created_at: str


class ItemDetail(ItemSummary):
    descriptor_notes: str | None
    purchase_price_minor: int | None
    currency: str | None
    purchase_date: str | None
    serial_number: str | None
    source_url: str | None
    image_url: str | None
    receipt_url: str | None
    ai_suggested_fields: list[str]
    updated_at: str


class ItemPage(BaseModel):
    items: list[ItemSummary]
    total: int


class SuggestionResponse(BaseModel):
    name: str
    category: str | None
    brand: str | None
    descriptor_notes: str | None


class ScrapeRequest(BaseModel):
    url: str


class ScrapeResponse(BaseModel):
    title: str | None
    image_url: str | None
    source_url: str


class PlacementWrite(BaseModel):
    item_id: str
    position_x: float
    position_y: float
    scale: float = Field(default=1.0, gt=0)
    z_index: int = 0


class PlacementsWrite(BaseModel):
    placements: list[PlacementWrite]


class Placement(BaseModel):
    id: str
    item: ItemSummary
    position_x: float
    position_y: float
    scale: float
    z_index: int


class BoardSummary(BaseModel):
    id: str
    name: str
    item_count: int
    cover_thumb_url: str | None


class BoardDetail(BaseModel):
    id: str
    name: str
    created_at: str
    placements: list[Placement]
