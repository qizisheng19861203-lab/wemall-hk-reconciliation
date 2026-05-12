"""初始化脚本：创建管理员账号"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, Base, engine
from app.models.user import User, UserRole
from app.core.security import get_password_hash
import app.models

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(
            username="admin",
            password_hash=get_password_hash("Admin@2024"),
            display_name="系统管理员",
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()
        print("Admin user created: admin / Admin@2024")
    else:
        print("Admin user already exists")
finally:
    db.close()
