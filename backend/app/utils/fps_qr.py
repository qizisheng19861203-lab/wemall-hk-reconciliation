"""
Generate Hong Kong FPS (转数快) QR codes following EMVCo / HKMA standard.
Reference: https://www.hkma.gov.hk/media/eng/doc/key-functions/financial-infrastructure/infrastructure/retail-payment-infrastructure/fps-qr-code-guidelines.pdf
"""
import io
import base64
import qrcode
from qrcode.image.pil import PilImage


def _crc16(data: str) -> int:
    """CRC-16/CCITT-FALSE used by EMVCo QR codes."""
    crc = 0xFFFF
    for char in data:
        crc ^= ord(char) << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def _tlv(tag: int, value: str) -> str:
    return f"{tag:02d}{len(value):02d}{value}"


def build_fps_payload(fps_id: str, merchant_name: str = "BLUE HEALTH MANAGEMENT", amount: float = None) -> str:
    """Build EMVCo-compliant FPS QR payload string."""
    # Merchant Account Info (tag 26) for FPS
    fps_inner = _tlv(0, "hk.com.hkicl.fps") + _tlv(2, fps_id)
    merchant_account = _tlv(26, fps_inner)

    # Truncate merchant name to 25 chars (EMVCo limit)
    name = merchant_name[:25].upper()

    parts = [
        _tlv(0, "01"),          # Payload Format Indicator
        _tlv(1, "11"),          # Static QR code
        merchant_account,
        _tlv(52, "0000"),       # Merchant Category Code (generic)
        _tlv(53, "344"),        # Currency: HKD = 344
    ]

    if amount is not None:
        parts.append(_tlv(54, f"{amount:.2f}"))

    parts += [
        _tlv(58, "HK"),         # Country Code
        _tlv(59, name),         # Merchant Name
        _tlv(60, "HONG KONG"),  # Merchant City
        "6304",                 # CRC placeholder (always last, value appended below)
    ]

    payload_no_crc = "".join(parts)
    crc = _crc16(payload_no_crc)
    return payload_no_crc + f"{crc:04X}"


def fps_qr_base64(fps_id: str, merchant_name: str = "BLUE HEALTH MANAGEMENT", size: int = 200) -> str:
    """
    Generate FPS QR code and return as base64-encoded PNG data URI.
    Usage in HTML: <img src="{{ fps_qr_uri }}">
    """
    payload = build_fps_payload(fps_id, merchant_name)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"
