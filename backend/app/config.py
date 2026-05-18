from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "微盟香港对账系统"
    SECRET_KEY: str = "change-this-to-a-strong-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "mysql+pymysql://root:password@db:3306/wemall_hk"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Wemall API
    WEMALL_APP_KEY: str = ""
    WEMALL_APP_SECRET: str = ""
    WEMALL_SHOP_ID: str = ""

    # Exchange Rate API
    EXCHANGE_RATE_API_KEY: str = ""
    EXCHANGE_RATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Tencent Cloud SMS
    TENCENT_SECRET_ID: str = ""
    TENCENT_SECRET_KEY: str = ""
    TENCENT_SMS_SDK_APP_ID: str = ""
    TENCENT_SMS_SIGN_NAME: str = "微盟香港对账"
    TENCENT_SMS_SETTLEMENT_TEMPLATE_ID: str = ""

    # Notification
    SETTLEMENT_NOTIFY_PHONE: str = ""  # comma separated admin phones

    # Email (SMTP) — 免费邮件通知
    SMTP_HOST: str = ""           # e.g. smtp.qq.com or smtp.gmail.com
    SMTP_PORT: int = 465          # 465=SSL, 587=TLS
    SMTP_USER: str = ""           # sender email
    SMTP_PASSWORD: str = ""       # QQ邮箱授权码 or Gmail App Password
    SMTP_FROM_NAME: str = "香港蔚蓝健康"
    SMTP_USE_SSL: bool = True     # True for port 465, False for 587 (STARTTLS)

    # CORS
    CORS_ORIGINS: str = "*"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
