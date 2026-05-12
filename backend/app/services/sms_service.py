from tencentcloud.common import credential
from tencentcloud.sms.v20210111 import sms_client, models
from app.config import settings
from app.models.settlement import Settlement, SettlementNotification
from sqlalchemy.orm import Session
import json


async def send_settlement_notification(db: Session, settlement: Settlement) -> dict:
    phones = [p.strip() for p in settings.SETTLEMENT_NOTIFY_PHONE.split(",") if p.strip()]
    if not phones:
        return {"status": "skipped", "reason": "no phone configured"}

    cred = credential.Credential(settings.TENCENT_SECRET_ID, settings.TENCENT_SECRET_KEY)
    client = sms_client.SmsClient(cred, "ap-guangzhou")

    req = models.SendSmsRequest()
    req.SmsSdkAppId = settings.TENCENT_SMS_SDK_APP_ID
    req.SignName = settings.TENCENT_SMS_SIGN_NAME
    req.TemplateId = settings.TENCENT_SMS_SETTLEMENT_TEMPLATE_ID
    req.TemplateParamSet = [
        settlement.invoice_number,
        str(settlement.payment_amount_hkd),
        settlement.period_end.strftime("%Y-%m-%d"),
    ]
    req.PhoneNumberSet = [f"+86{p}" if not p.startswith("+") else p for p in phones]

    try:
        resp = client.SendSms(req)
        success = sum(1 for r in resp.SendStatusSet if r.Code == "Ok")
        for phone in phones:
            notif = SettlementNotification(
                settlement_id=settlement.id,
                channel="sms",
                recipient=phone,
                message=f"结算通知 {settlement.invoice_number} HKD {settlement.payment_amount_hkd}",
                status="sent",
            )
            db.add(notif)
        db.commit()
        return {"status": "ok", "success": success, "total": len(phones)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
