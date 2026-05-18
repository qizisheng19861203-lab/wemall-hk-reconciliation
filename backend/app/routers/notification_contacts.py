from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models.user import User
from app.models.notification_contact import NotificationContact
from app.core.deps import get_current_user, require_admin


class ContactCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    email: Optional[str] = None


class ContactResponse(BaseModel):
    id: int
    name: str
    phone: str
    is_active: bool
    email: Optional[str] = None

    class Config:
        from_attributes = True


router = APIRouter(prefix="/notification-contacts", tags=["通知联系人"])


@router.get("", response_model=List[ContactResponse])
def list_contacts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(NotificationContact).all()


@router.post("", response_model=ContactResponse)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    contact = NotificationContact(name=payload.name, phone=payload.phone, email=payload.email)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    contact = db.query(NotificationContact).filter(NotificationContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(contact, k, v)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}")
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    contact = db.query(NotificationContact).filter(NotificationContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    db.delete(contact)
    db.commit()
    return {"ok": True}
