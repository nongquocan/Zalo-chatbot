"""
Client giao tiếp với Google Gemini API (gemini-2.5-flash).

Nâng cấp:
  - Async: generate_reply + classify_intent chạy không đồng bộ (asyncio.to_thread)
  - Few-shot classify prompt: giảm false positive
  - Logging: thay print() bằng logging module
"""
import asyncio
import json
import time
from google import genai
from google.genai import types, errors
from typing import Callable, List, TypeVar, Optional
from app.config import get_settings
from app.models import ChatMessage, MessageRole, ExtractedOrder
from app.prompt_builder import build_system_prompt
from app.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_T = TypeVar("_T")
# 429 = rate limit (RESOURCE_EXHAUSTED), 503/504 = quá tải/timeout tạm thời phía server.
_RETRYABLE_STATUS_CODES = (429, 503, 504)


def _is_retryable(e: BaseException) -> bool:
    return isinstance(e, errors.APIError) and e.code in _RETRYABLE_STATUS_CODES


def _call_with_retry(fn: Callable[[], _T], retries: int = 1, backoff_sec: float = 5.0) -> _T:
    """
    Gọi Gemini API với 1 lần thử lại khi gặp lỗi tạm thời (quá tải/rate limit).
    Free tier Gemini giới hạn số request/phút khá thấp nên lỗi 429 xảy ra khá
    thường xuyên khi có nhiều tin nhắn dồn dập; retry ngắn giúp giảm tỉ lệ lỗi
    trả về người dùng cuối.
    """
    for attempt in range(retries + 1):
        try:
            return fn()
        except errors.APIError as e:
            if not _is_retryable(e) or attempt == retries:
                raise
            logger.warning(
                "Gemini API lỗi tạm thời (attempt %d/%d): %s. Retry sau %.1fs...",
                attempt + 1, retries + 1, e, backoff_sec,
            )
            time.sleep(backoff_sec)


def _get_client() -> genai.Client:
    """Khởi tạo Gemini client (lazy initialization)."""
    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY chưa được cấu hình. "
            "Vui lòng thêm vào file .env"
        )
    return genai.Client(api_key=settings.gemini_api_key)


# ─────────────────────────────────────────────
# Classify Intent Prompt (Few-shot)
# ─────────────────────────────────────────────

_CLASSIFY_PROMPT = """Bạn là bộ phân loại intent cho chatbot bán hàng phụ kiện điện thoại.
Nhiệm vụ DUY NHẤT: xác định tin nhắn của khách có thực sự cần CHỦ SHOP (người thật) can thiệp trực tiếp hay không.

## QUY TẮC PHÂN LOẠI

Cần chuyển cho người thật (needs_human=true) KHI VÀ CHỈ KHI khách:
- Đang khiếu nại về một sản phẩm/đơn hàng CỤ THỂ họ đã nhận (hàng lỗi, giao nhầm, thiếu hàng, mất hàng...)
- Yêu cầu hoàn tiền/bồi thường cho đơn đã mua
- Muốn đặt vấn đề giá sỉ, hợp tác đại lý, mua số lượng lớn (≥50 cái)
- Yêu cầu nói chuyện trực tiếp với chủ shop/nhân viên
- Đe dọa, sử dụng ngôn ngữ bạo lực, hoặc quấy rối

KHÔNG chuyển (needs_human=false) khi khách chỉ đang:
- Hỏi thông tin chung về chính sách (đổi trả, bảo hành, shipping) – dù câu hỏi chứa từ "hàng lỗi", "đổi trả"
- Hỏi giá, tồn kho, thông tin sản phẩm
- Muốn đặt hàng số lượng bình thường
- Chào hỏi, cảm ơn, tạm biệt
- Hỏi bất cứ câu hỏi nào mà AI có thể trả lời được từ dữ liệu shop

## VÍ DỤ (FEW-SHOT)

Tin nhắn: "hàng lỗi thì đổi trả thế nào shop?"
→ {{"needs_human": false, "category": "none", "reason": "Khách hỏi chính sách đổi trả chung, không khiếu nại đơn cụ thể"}}

Tin nhắn: "tôi mua cái tai nghe hôm qua mà nó bị lỗi rồi, không kết nối bluetooth được"
→ {{"needs_human": true, "category": "complaint", "reason": "Khách khiếu nại sản phẩm cụ thể đã mua bị lỗi"}}

Tin nhắn: "cho hỏi bảo hành bao lâu vậy shop?"
→ {{"needs_human": false, "category": "none", "reason": "Câu hỏi chính sách bảo hành chung"}}

Tin nhắn: "shop có bán sỉ không? mình muốn lấy 100 cái ốp lưng"
→ {{"needs_human": true, "category": "wholesale", "reason": "Yêu cầu mua sỉ số lượng lớn"}}

Tin nhắn: "nếu mua mà không ưng thì trả lại được không?"
→ {{"needs_human": false, "category": "none", "reason": "Hỏi chính sách đổi trả chung, chưa mua"}}

Tin nhắn: "cho tôi gặp chủ shop"
→ {{"needs_human": true, "category": "escalation", "reason": "Khách yêu cầu gặp trực tiếp chủ shop"}}

## ĐỊNH DẠNG TRẢ VỀ
Chỉ trả về JSON theo đúng định dạng, không thêm chữ nào khác:
{{"needs_human": true/false, "category": "complaint"/"wholesale"/"escalation"/"abuse"/"none", "reason": "giải thích ngắn gọn 1 câu bằng tiếng Việt"}}

Tin nhắn của khách: "{message}"
"""


# ─────────────────────────────────────────────
# Synchronous internals (chạy trong thread pool)
# ─────────────────────────────────────────────

def _classify_intent_sync(message: str) -> dict:
    """Phân loại intent – phiên bản đồng bộ (gọi bởi async wrapper)."""
    client = _get_client()

    response = _call_with_retry(lambda: client.models.generate_content(
        model=settings.gemini_model,
        contents=_CLASSIFY_PROMPT.format(message=message),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    ))
    data = json.loads(response.text)
    return {
        "needs_human": bool(data.get("needs_human", False)),
        "category": data.get("category", "none"),
        "reason": data.get("reason", ""),
    }


def _generate_reply_sync(user_message: str, history: List[ChatMessage]) -> str:
    """Sinh câu trả lời – phiên bản đồng bộ (gọi bởi async wrapper)."""
    client = _get_client()

    # Chuyển đổi lịch sử sang định dạng Gemini
    gemini_history = [
        types.Content(
            role="user" if msg.role == MessageRole.USER else "model",
            parts=[types.Part(text=msg.content)],
        )
        for msg in history
    ]

    # Tạo chat session với lịch sử
    chat = client.chats.create(
        model=settings.gemini_model,
        config=types.GenerateContentConfig(system_instruction=build_system_prompt()),
        history=gemini_history,
    )

    # Gửi tin nhắn mới
    response = _call_with_retry(lambda: chat.send_message(user_message))
    return response.text.strip()


# ─────────────────────────────────────────────
# Async public API
# ─────────────────────────────────────────────

async def classify_intent(message: str) -> dict:
    """
    Gọi Gemini để phân loại intent (async).

    Sử dụng asyncio.to_thread để không block event loop của FastAPI
    trong khi chờ Gemini API phản hồi (thường 2-10 giây).

    Returns:
        dict: {"needs_human": bool, "category": str, "reason": str}
    """
    logger.debug("Classify intent cho tin nhắn: %s", message[:80])
    result = await asyncio.to_thread(_classify_intent_sync, message)
    logger.info(
        "Classify result: needs_human=%s, category=%s, reason=%s",
        result["needs_human"], result["category"], result["reason"],
    )
    return result


async def generate_reply(user_message: str, history: List[ChatMessage]) -> str:
    """
    Gọi Gemini API sinh câu trả lời (async).

    Sử dụng asyncio.to_thread để không block event loop của FastAPI
    trong khi chờ Gemini API phản hồi (thường 2-10 giây).

    Args:
        user_message: Tin nhắn mới nhất của khách hàng
        history: Lịch sử hội thoại (KHÔNG bao gồm tin nhắn hiện tại)

    Returns:
        Chuỗi câu trả lời từ Gemini
    """
    logger.debug(
        "Generate reply cho: '%s' (history: %d messages)",
        user_message[:80], len(history),
    )
    reply = await asyncio.to_thread(_generate_reply_sync, user_message, history)
    logger.info("Reply generated (%d chars)", len(reply))
    return reply


# ─────────────────────────────────────────────
# Order Extraction (Structured Output)
# ─────────────────────────────────────────────

_EXTRACT_ORDER_PROMPT = """Bạn là trợ lý hệ thống phân tích hội thoại.
Nhiệm vụ: Dựa vào lịch sử hội thoại giữa Khách hàng và Nhân viên (shop), hãy trích xuất thông tin ĐƠN HÀNG mà khách đã đồng ý mua.
Hãy chắc chắn trích xuất đúng tên sản phẩm, số lượng, và đặc biệt là địa chỉ giao hàng và phương thức thanh toán.

Lịch sử hội thoại (Sắp xếp từ cũ đến mới):
{history_text}
"""

def _extract_order_sync(history: List[ChatMessage]) -> Optional[dict]:
    """Phiên bản đồng bộ của hàm trích xuất đơn hàng."""
    client = _get_client()

    # Format lịch sử
    history_lines = []
    for msg in history:
        role = "Khách hàng" if msg.role == MessageRole.USER else "Nhân viên"
        history_lines.append(f"{role}: {msg.content}")
    history_text = "\n".join(history_lines)

    response = _call_with_retry(lambda: client.models.generate_content(
        model=settings.gemini_model,
        contents=_EXTRACT_ORDER_PROMPT.format(history_text=history_text),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractedOrder,
            temperature=0.0,
        ),
    ))
    
    try:
        data = json.loads(response.text)
        return data
    except Exception as e:
        logger.error("Lỗi parse JSON khi extract order: %s", e)
        return None


async def extract_order_async(history: List[ChatMessage]) -> Optional[dict]:
    """
    Gọi Gemini API để trích xuất JSON đơn hàng từ lịch sử hội thoại (async).
    Sử dụng Gemini Structured Output.
    """
    logger.info("Bắt đầu trích xuất đơn hàng ngầm...")
    result = await asyncio.to_thread(_extract_order_sync, history)
    if result:
        logger.info("Đã trích xuất thành công đơn hàng: %d sản phẩm, %d VNĐ", 
                    len(result.get("products", [])), result.get("total_amount", 0))
    else:
        logger.warning("Trích xuất đơn hàng thất bại.")
    return result
