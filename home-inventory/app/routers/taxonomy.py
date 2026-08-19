"""Rooms and categories. Identical behaviour, so one factory builds both (FR-014/015).

Built as two concrete routers rather than one router on /api/{kind}, because a wildcard segment
at that level would shadow every other /api/* route registered after it.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_session
from app.db import get_session, save_snapshot
from app.models import Category, Item, Room
from app.schemas import TaxonomyEntry, TaxonomyWrite


def _build_router(path: str, model, item_column, noun: str) -> APIRouter:
    router = APIRouter(
        prefix=f"/api/{path}", tags=["taxonomy"], dependencies=[Depends(require_session)]
    )

    def get_or_404(session: Session, entity_id: str):
        entity = session.get(model, entity_id)
        if entity is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No such {noun}")
        return entity

    def reject_duplicate(session: Session, name: str, exclude_id: str | None = None) -> None:
        query = select(model).where(func.lower(model.name) == name.lower())
        if exclude_id:
            query = query.where(model.id != exclude_id)
        if session.scalar(query) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, f"'{name}' already exists")

    def count_items(session: Session, entity_id: str) -> int:
        return session.scalar(select(func.count(Item.id)).where(item_column == entity_id)) or 0

    @router.get("", response_model=list[TaxonomyEntry])
    def list_entries(session: Session = Depends(get_session)) -> list[TaxonomyEntry]:
        counts = dict(
            session.execute(select(item_column, func.count(Item.id)).group_by(item_column)).all()
        )
        entities = session.scalars(select(model).order_by(model.sort_order, model.name)).all()
        return [TaxonomyEntry(id=e.id, name=e.name, item_count=counts.get(e.id, 0)) for e in entities]

    @router.post("", response_model=TaxonomyEntry, status_code=status.HTTP_201_CREATED)
    def create_entry(
        body: TaxonomyWrite, session: Session = Depends(get_session)
    ) -> TaxonomyEntry:
        reject_duplicate(session, body.name)
        entity = model(name=body.name, sort_order=999)
        session.add(entity)
        session.commit()
        save_snapshot()
        return TaxonomyEntry(id=entity.id, name=entity.name, item_count=0)

    @router.patch("/{entity_id}", response_model=TaxonomyEntry)
    def rename_entry(
        entity_id: str, body: TaxonomyWrite, session: Session = Depends(get_session)
    ) -> TaxonomyEntry:
        entity = get_or_404(session, entity_id)
        reject_duplicate(session, body.name, exclude_id=entity_id)
        entity.name = body.name
        session.commit()
        save_snapshot()
        return TaxonomyEntry(id=entity.id, name=entity.name, item_count=count_items(session, entity_id))

    @router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_entry(entity_id: str, session: Session = Depends(get_session)) -> None:
        entity = get_or_404(session, entity_id)
        in_use = count_items(session, entity_id)
        if in_use:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{in_use} item{'s are' if in_use != 1 else ' is'} still in this {noun}",
            )
        session.delete(entity)
        session.commit()
        save_snapshot()

    return router


rooms_router = _build_router("rooms", Room, Item.room_id, "room")
categories_router = _build_router("categories", Category, Item.category_id, "category")
