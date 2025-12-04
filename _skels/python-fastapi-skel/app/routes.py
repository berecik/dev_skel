"""API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Item
from app.schemas import ItemCreate, ItemResponse

router = APIRouter(prefix="/api", tags=["items"])


@router.get("/items", response_model=list[ItemResponse])
async def list_items(db: AsyncSession = Depends(get_db)):
    """List all items."""
    result = await db.execute(select(Item))
    return result.scalars().all()


@router.post("/items", response_model=ItemResponse, status_code=201)
async def create_item(item: ItemCreate, db: AsyncSession = Depends(get_db)):
    """Create a new item."""
    db_item = Item(**item.model_dump())
    db.add(db_item)
    await db.flush()
    await db.refresh(db_item)
    return db_item


@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Get an item by ID."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
