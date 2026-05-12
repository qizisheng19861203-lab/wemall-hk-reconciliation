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
    WEMALL_API_BASE: str = "https://api.weimob.com"

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

    # CORS
    CORS_ORIGINS: str = "*"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
