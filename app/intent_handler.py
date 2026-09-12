"""
Phát hiện các intent cần chuyển tiếp cho người bán xử lý (fallback).

Chiến lược 2 bước:
1. Lọc nhanh bằng từ khóa (rẻ, không tốn API call) – nếu không khớp từ khóa nào
   thì chắc chắn không cần fallback, trả về ngay.
2. Nếu khớp từ khóa, gọi Gemini phân loại lại để xác nhận đây có phải fallback
   thật hay chỉ là câu hỏi chính sách thông thường có chứa từ khóa
   (ví dụ: "hàng lỗi thì đổi trả thế nào?" KHÔNG phải khiếu nại thật).
   Nếu Gemini lỗi/không cấu hình, dùng lại kết quả từ khóa làm phương án dự phòng.
"""
from typing import Tuple
from app.logger import get_logger

logger = get_logger(__name__)

# Danh sách từ khóa kích hoạt fallback
FALLBACK_KEYWORDS = [
    # Khiếu nại / hàng lỗi
    "hàng lỗi", "hàng hỏng", "bị lỗi", "bị hỏng", "không dùng được",
    "không hoạt động", "không kết nối", "bị vỡ", "nứt", "rạn",
    "không đúng", "sai hàng", "giao nhầm", "thiếu hàng",
    # Hoàn tiền
    "hoàn tiền", "trả tiền", "bồi thường", "đền bù",
    # Khiếu kiện / phản ánh
    "khiếu nại", "khiếu kiện", "phản ánh", "tố cáo",
    "không hài lòng", "thất vọng", "tệ quá", "lừa đảo",
    # Vấn đề đơn hàng
    "chưa nhận được", "mất hàng", "thất lạc", "không thấy đơn",
    "đơn bị hủy", "bị gian lận",
    # Yêu cầu người thật
    "gặp người thật", "nhân viên", "chủ shop", "người phụ trách",
    "tôi cần nói chuyện trực tiếp",
]

# Từ khóa yêu cầu báo giá sỉ / đặc biệt
WHOLESALE_KEYWORDS = [
    "giá sỉ", "đại lý", "mua sỉ", "nhập sỉ", "mua số lượng lớn",
    "hợp tác", "đối tác",
]


def _keyword_prefilter(message: str) -> Tuple[bool, str]:
    """
    Bước 1: lọc nhanh bằng từ khóa. Trả về ứng viên cần xác nhận thêm.

    Returns:
        (candidate: bool, reason: str)
    """
    msg_lower = message.lower()

    for keyword in FALLBACK_KEYWORDS:
        if keyword in msg_lower:
            return True, f"Phát hiện từ khóa khiếu nại/vấn đề: '{keyword}'"

    for keyword in WHOLESALE_KEYWORDS:
        if keyword in msg_lower:
            return True, f"Yêu cầu tư vấn giá sỉ/đại lý: '{keyword}'"

    return False, ""


def check_needs_fallback(message: str) -> Tuple[bool, str]:
    """
    Kiểm tra xem tin nhắn có cần chuyển tiếp cho người bán không (chỉ dựa từ khóa).
    Giữ lại cho tương thích ngược / dùng khi không muốn gọi Gemini.

    Returns:
        (needs_fallback: bool, reason: str)
    """
    return _keyword_prefilter(message)


async def check_needs_fallback_smart(message: str) -> Tuple[bool, str]:
    """
    Kiểm tra 2 bước: từ khóa trước, Gemini xác nhận sau (chỉ khi khớp từ khóa).
    Đây là phiên bản nên dùng trong luồng xử lý chính vì giảm được false positive
    (ví dụ câu hỏi chính sách chứa từ "hàng lỗi" nhưng không phải khiếu nại thật).

    Returns:
        (needs_fallback: bool, reason: str)
    """
    is_candidate, keyword_reason = _keyword_prefilter(message)
    if not is_candidate:
        return False, ""

    logger.info("Keyword match: '%s' → gọi Gemini xác nhận...", keyword_reason)

    # Import cục bộ để tránh vòng lặp import và chỉ tải khi thực sự cần
    from app.gemini_client import classify_intent

    try:
        result = await classify_intent(message)
    except Exception as e:
        # Gemini lỗi/không cấu hình → dùng lại kết quả từ khóa để an toàn
        logger.warning("classify_intent thất bại, dùng fallback từ khóa: %s", e)
        return True, keyword_reason

    if result["needs_human"]:
        return True, result["reason"] or keyword_reason
    return False, ""
