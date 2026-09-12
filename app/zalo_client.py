"""
Client giao tiếp với Zalo OA API để gửi tin nhắn về cho khách hàng.
(Sẽ được kích hoạt đầy đủ sau khi có Zalo OA token thực)
"""
import asyncio
import hashlib
import hmac
import time
from typing import Optional

import httpx
from app.config import get_settings
from app.logger import get_logger
from app import database as db

logger = get_logger(__name__)

settings = get_settings()

ZALO_SEND_MESSAGE_URL = "https://openapi.zalo.me/v3.0/oa/message/cs"
ZALO_TOKEN_URL = "https://oauth.zaloapp.com/v4/oa/access_token"
ZALO_SIGNATURE_HEADER = "x-zevent-signature"

# Access token Zalo OA chỉ sống ~1 giờ, refresh_token chỉ dùng được 1 lần
# (mỗi lần refresh Zalo trả về refresh_token MỚI, bắt buộc phải lưu lại).
# Làm mới sớm hơn hạn thật một khoảng đệm để tránh gọi API đúng lúc token
# vừa hết hạn (lệch giờ đồng hồ, độ trễ mạng...).
_TOKEN_REFRESH_BUFFER_SECONDS = 300
_token_lock = asyncio.Lock()


def verify_webhook_signature(raw_body: bytes, app_id: str, timestamp: str, received_mac: str) -> bool:
    """
    Xác thực chữ ký webhook Zalo OA (header X-ZEvent-Signature), theo công thức:
        mac = SHA256(app_id + raw_body + timestamp + app_secret)

    LƯU Ý QUAN TRỌNG: công thức trên được tổng hợp từ tài liệu cộng đồng/bài viết
    kỹ thuật (trang docs chính thức developers.zalo.me là SPA nên không lấy được
    nội dung tĩnh để đối chiếu 100%). BẮT BUỘC kiểm thử lại với ít nhất 1 webhook
    event thật từ Zalo OA (xem log warning "Webhook signature không hợp lệ")
    trước khi triển khai chính thức — nếu công thức sai, mọi webhook thật sẽ bị
    từ chối oan.

    Nếu ZALO_APP_SECRET chưa được cấu hình (giai đoạn dev/demo, chưa có OA thật)
    → bỏ qua xác thực, giữ nguyên hành vi cũ để không phá luồng test hiện tại.
    """
    if not settings.zalo_app_secret:
        return True

    base_string = f"{app_id}{raw_body.decode('utf-8')}{timestamp}{settings.zalo_app_secret}"
    expected_mac = hashlib.sha256(base_string.encode("utf-8")).hexdigest()

    # Header thực tế có dạng "mac=<hex>" (không phải chỉ riêng hex) – bóc tiền
    # tố "mac=" trước khi so sánh. Phát hiện được từ 1 webhook event thật bị
    # từ chối oan lúc chưa bóc tiền tố này.
    received_clean = (received_mac or "").strip()
    if received_clean.lower().startswith("mac="):
        received_clean = received_clean[4:]

    is_valid = hmac.compare_digest(expected_mac, received_clean)
    if not is_valid:
        # Log tạm thời (kể cả raw_body) để đối chiếu offline nhiều công thức
        # khác nhau – chỉ bật tạm lúc debug, không để log này khi lên thật.
        logger.debug(
            "Signature mismatch – expected=%s received_raw=%r app_id=%s timestamp=%s raw_body=%r",
            expected_mac, received_mac, app_id, timestamp, raw_body,
        )
    return is_valid


async def _call_zalo_token_endpoint(data: dict) -> dict:
    """Gọi endpoint đổi/refresh token của Zalo OA."""
    headers = {
        "secret_key": settings.zalo_app_secret,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(ZALO_TOKEN_URL, headers=headers, data=data)
        response.raise_for_status()
        return response.json()


async def _refresh_zalo_token(refresh_token: str) -> Optional[dict]:
    """
    Dùng refresh_token hiện có để lấy access_token + refresh_token MỚI.
    refresh_token cũ chỉ dùng được đúng 1 lần nên luôn phải lưu lại cặp mới
    trả về, kể cả khi refresh_token không đổi bề ngoài.
    """
    try:
        result = await _call_zalo_token_endpoint({
            "app_id": settings.zalo_app_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        })
    except Exception as e:
        logger.error("Lỗi gọi API refresh Zalo OA token: %s", e)
        return None

    if "access_token" not in result or "refresh_token" not in result:
        logger.error("Zalo trả về lỗi khi refresh token (kiểm tra app_id/secret_key/refresh_token): %s", result)
        return None

    expires_in = int(result.get("expires_in", 3600))
    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "expires_at": int(time.time()) + expires_in,
    }


async def get_valid_access_token() -> Optional[str]:
    """
    Trả về access_token Zalo OA còn hiệu lực, tự động refresh nếu sắp hết hạn.

    - Nếu chưa cấu hình ZALO_APP_ID/ZALO_APP_SECRET đầy đủ: không thể tự
      refresh, trả về tạm ZALO_OA_TOKEN tĩnh trong .env nếu có (sẽ tự hết hạn
      sau ~1 giờ), hoặc None (chế độ mock).
    - Nếu đã cấu hình đủ: đọc token đang lưu trong DB (bảng zalo_tokens); nếu
      chưa có dòng nào thì bootstrap từ ZALO_REFRESH_TOKEN_SEED (lấy 1 lần thủ
      công theo hướng dẫn OAuth ban đầu).
    """
    if not settings.zalo_app_id or not settings.zalo_app_secret:
        return settings.zalo_oa_token or None

    async with _token_lock:
        stored = await asyncio.to_thread(db.get_zalo_token)
        now = int(time.time())

        if stored and stored["expires_at"] - now > _TOKEN_REFRESH_BUFFER_SECONDS:
            return stored["access_token"]

        refresh_token = stored["refresh_token"] if stored else settings.zalo_refresh_token_seed
        if not refresh_token:
            logger.warning(
                "Chưa có refresh_token nào (DB rỗng và ZALO_REFRESH_TOKEN_SEED "
                "trống trong .env) -> không thể tự lấy access token mới."
            )
            return settings.zalo_oa_token or None

        new_token = await _refresh_zalo_token(refresh_token)
        if not new_token:
            # Refresh lỗi -> dùng tạm token cũ trong DB (nếu còn hạn dùng
            # được chút nào) thay vì làm sập luôn request đang xử lý.
            return stored["access_token"] if stored else (settings.zalo_oa_token or None)

        await asyncio.to_thread(
            db.save_zalo_token,
            new_token["access_token"],
            new_token["refresh_token"],
            new_token["expires_at"],
        )
        logger.info(
            "Đã làm mới Zalo OA access token, hết hạn lúc unix_ts=%s",
            new_token["expires_at"],
        )
        return new_token["access_token"]


async def send_text_message(user_id: str, text: str) -> dict:
    """
    Gửi tin nhắn văn bản đến khách hàng qua Zalo OA API.

    Args:
        user_id: Zalo user ID của khách hàng
        text: Nội dung tin nhắn

    Returns:
        Response JSON từ Zalo API
    """
    access_token = await get_valid_access_token()
    if not access_token:
        # Chế độ mock – chưa cấu hình token/app thật
        logger.info("[MOCK] Gửi tin nhắn → User %s: %s...", user_id, text[:80])
        return {"error": 0, "message": "mock_sent", "data": {"message_id": "mock_id"}}

    headers = {
        "access_token": access_token,
        "Content-Type": "application/json",
    }
    payload = {
        "recipient": {"user_id": user_id},
        "message": {"text": text},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            ZALO_SEND_MESSAGE_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def notify_owner_fallback(user_id: str, user_name: str, message: str, reason: str):
    """
    Thông báo cho chủ shop khi phát hiện tin nhắn cần can thiệp thủ công.

    Nếu đã cấu hình ZALO_OWNER_ID + ZALO_OA_TOKEN: gửi tin nhắn Zalo thật cho chủ shop.
    Nếu chưa (giai đoạn dev/chưa có OA thật): chỉ log ra console, không lỗi.
    Lưu ý: theo giới hạn của Zalo OA CS API, chủ shop phải từng nhắn cho OA
    trong vòng 7 ngày gần nhất thì mới nhận được tin nhắn broadcast dạng này.
    """
    alert_text = (
        f"⚠️ CẦN HỖ TRỢ KHÁCH HÀNG\n"
        f"Khách: {user_name} (ID: {user_id})\n"
        f"Tin nhắn: {message}\n"
        f"Lý do: {reason}"
    )

    logger.warning("FALLBACK ALERT:\n%s", alert_text)

    if not settings.zalo_owner_id:
        return

    try:
        await send_text_message(settings.zalo_owner_id, alert_text)
    except Exception as e:
        # Không để lỗi gửi thông báo làm gián đoạn luồng trả lời khách
        logger.error("Không gửi được thông báo Zalo cho chủ shop: %s", e)
