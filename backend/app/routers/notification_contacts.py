from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional
from datetime import datetime
import re
from app.database import get_db
from app.models.user import User
from app.models.notification_contact import NotificationContact
from app.core.deps import get_current_user, require_admin


class ContactCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    is_active: Optional[bool] = True

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v is None or v == '':
            return None
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确，需为11位且以1开头的大陆手机号')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not v or '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('请输入有效的邮箱地址')
        return v


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v is None or v == '':
            return None
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确，需为11位且以1开头的大陆手机号')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v is None:
            return v
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('请输入有效的邮箱地址')
        return v


class ContactResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

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
    contact = NotificationContact(
        name=payload.name,
        email=payload.email,
        phone=payload.phone if payload.phone else None,
        is_active=payload.is_active if payload.is_active is not None else True,
    )
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
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
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
