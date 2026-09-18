from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.items.schemas import ItemRead

router = APIRouter()


@router.get("/", response_model=list[ItemRead])
def list_items(db: Session = Depends(get_db)):
    return []
