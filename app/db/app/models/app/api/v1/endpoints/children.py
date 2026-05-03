from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import Child
from pydantic import BaseModel

router = APIRouter()

# Схема данных для входящего запроса
class ChildCreate(BaseModel):
    name: str
    age: int
    parent_id: str

@router.post("/")
async def create_child(obj_in: ChildCreate, db: AsyncSession = Depends(get_db)):
    new_child = Child(
        name=obj_in.name,
        age=obj_in.age,
        parent_id=obj_in.parent_id
    )
    db.add(new_child)
    await db.commit()
    await db.refresh(new_child)
    return new_child