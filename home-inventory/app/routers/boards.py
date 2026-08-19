from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_session
from app.db import get_session, save_snapshot
from app.deps import media_url, to_summary
from app.models import Board, BoardItem, Item
from app.schemas import BoardDetail, BoardSummary, Placement, PlacementsWrite, TaxonomyWrite

router = APIRouter(prefix="/api/boards", tags=["boards"], dependencies=[Depends(require_session)])


def _get_or_404(session: Session, board_id: str) -> Board:
    board = session.get(Board, board_id)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such board")
    return board


def _detail(board: Board) -> BoardDetail:
    return BoardDetail(
        id=board.id,
        name=board.name,
        created_at=board.created_at,
        placements=[
            Placement(
                id=p.id,
                item=to_summary(p.item),
                position_x=p.position_x,
                position_y=p.position_y,
                scale=p.scale,
                z_index=p.z_index,
            )
            for p in board.placements
        ],
    )


@router.get("", response_model=list[BoardSummary])
def list_boards(session: Session = Depends(get_session)) -> list[BoardSummary]:
    boards = session.scalars(
        select(Board)
        .options(joinedload(Board.placements).joinedload(BoardItem.item))
        .order_by(Board.created_at.desc())
    ).unique().all()
    return [
        BoardSummary(
            id=b.id,
            name=b.name,
            item_count=len(b.placements),
            cover_thumb_url=media_url(b.placements[0].item.thumb_key) if b.placements else None,
        )
        for b in boards
    ]


@router.post("", response_model=BoardDetail, status_code=status.HTTP_201_CREATED)
def create_board(body: TaxonomyWrite, session: Session = Depends(get_session)) -> BoardDetail:
    board = Board(name=body.name)
    session.add(board)
    session.commit()
    save_snapshot()
    return _detail(board)


@router.get("/{board_id}", response_model=BoardDetail)
def get_board(board_id: str, session: Session = Depends(get_session)) -> BoardDetail:
    return _detail(_get_or_404(session, board_id))


@router.patch("/{board_id}", response_model=BoardDetail)
def rename_board(
    board_id: str, body: TaxonomyWrite, session: Session = Depends(get_session)
) -> BoardDetail:
    board = _get_or_404(session, board_id)
    board.name = body.name
    session.commit()
    save_snapshot()
    return _detail(board)


@router.put("/{board_id}/placements", response_model=BoardDetail)
def replace_placements(
    board_id: str, body: PlacementsWrite, session: Session = Depends(get_session)
) -> BoardDetail:
    """The canvas saves as a unit, so a half-saved board is not representable (FR-018)."""
    board = _get_or_404(session, board_id)

    item_ids = {p.item_id for p in body.placements}
    known = set(session.scalars(select(Item.id).where(Item.id.in_(item_ids))).all())
    missing = item_ids - known
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"{len(missing)} of those items no longer exist"
        )

    board.placements.clear()
    session.flush()
    for placement in body.placements:
        board.placements.append(
            BoardItem(
                item_id=placement.item_id,
                position_x=placement.position_x,
                position_y=placement.position_y,
                scale=placement.scale,
                z_index=placement.z_index,
            )
        )
    session.commit()
    save_snapshot()
    session.refresh(board)
    return _detail(board)


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(board_id: str, session: Session = Depends(get_session)) -> None:
    """Deleting a board never touches the items on it (FR-019)."""
    session.delete(_get_or_404(session, board_id))
    session.commit()
    save_snapshot()
