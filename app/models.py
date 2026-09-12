"""
Pydantic models cho Zalo OA webhook payload và các request/response nội bộ.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ─────────────────────────────────────────────
# Zalo OA Webhook Models
# ─────────────────────────────────────────────

class ZaloSender(BaseModel):
    id: str
    display_name: Optional[str] = None
    avatar: Optional[str] = None


class ZaloRecipient(BaseModel):
    id: str


class ZaloMessage(BaseModel):
    id: Optional[str] = None
    text: Optional[str] = None
    type: Optional[str] = None


class ZaloWebhookEvent(BaseModel):
    """Payload nhận từ Zalo OA webhook khi có tin nhắn mới."""
    app_id: Optional[str] = None
    user_id_by_app: Optional[str] = None
    event_name: Optional[str] = None
    timestamp: Optional[str] = None
    sender: Optional[ZaloSender] = None
    recipient: Optional[ZaloRecipient] = None
    message: Optional[ZaloMessage] = None


# ─────────────────────────────────────────────
# Internal Chat Models
# ─────────────────────────────────────────────

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """Một lượt hội thoại trong lịch sử."""
    role: MessageRole
    content: str


class ChatRequest(BaseModel):
    """Request cho endpoint /mock-chat (dùng khi test không có Zalo OA)."""
    user_id: str = Field(default="test_user_001", description="ID người dùng (giả lập)")
    message: str = Field(..., description="Tin nhắn của người dùng")
    user_name: Optional[str] = Field(default="Khách hàng", description="Tên hiển thị")


class ChatResponse(BaseModel):
    """Response trả về cho endpoint /mock-chat."""
    user_id: str
    reply: str
    needs_human: bool = False
    fallback_reason: Optional[str] = None
    history_length: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    app_name: str
    gemini_configured: bool
    zalo_configured: bool


# ─────────────────────────────────────────────
# Order Extraction Models (for Gemini Structured Output)
# ─────────────────────────────────────────────

class OrderProduct(BaseModel):
    name: str = Field(description="Tên sản phẩm đầy đủ kèm màu sắc nếu có")
    qty: int = Field(description="Số lượng")
    price: int = Field(description="Đơn giá (chỉ số, ví dụ 150000)")


class ExtractedOrder(BaseModel):
    """Lược đồ dữ liệu bắt buộc trả về khi AI trích xuất thông tin chốt đơn."""
    products: List[OrderProduct] = Field(description="Danh sách sản phẩm khách đặt")
    total_amount: int = Field(description="Tổng tiền đơn hàng (chỉ số)")
    shipping_address: str = Field(description="Địa chỉ giao hàng khách đã cung cấp")
    payment_method: str = Field(description="Phương thức thanh toán khách chọn (ví dụ: COD, CK, MoMo)")
    note: Optional[str] = Field(default=None, description="Ghi chú thêm nếu có")
