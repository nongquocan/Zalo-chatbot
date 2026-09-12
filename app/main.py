"""
FastAPI entry point – Webhook Zalo OA + Mock Chat + Admin Dashboard.

Endpoints:
  GET  /health          – Health check
  GET  /webhook         – Verify webhook với Zalo OA
  POST /webhook         – Nhận sự kiện tin nhắn từ Zalo OA (production)
  POST /mock-chat       – Giả lập hội thoại (dev/test, không cần Zalo OA thật)
  DELETE /mock-chat/{user_id} – Xóa lịch sử hội thoại của user (reset)
  GET  /stats           – Thống kê hoạt động chatbot (JSON API)
  GET  /orders          – Xem danh sách đơn hàng (JSON API)
  GET  /admin           – Trang quản trị trực quan
  GET  /chat            – Trang giả lập chat Zalo (Demo UI)
  GET  /api/conversations – Lịch sử hội thoại (JSON API cho admin)
"""
import asyncio
import json
import secrets
import sys

# Console Windows (cmd/PowerShell) mặc định dùng codepage cp1252, không encode
# được tiếng Việt có dấu → print() sẽ raise UnicodeEncodeError và làm sập cả
# request đang xử lý (không chỉ là vấn đề hiển thị như tưởng ban đầu).
# Ép stdout/stderr sang UTF-8, thay ký tự không encode được thay vì crash.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi import Depends, FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
import uvicorn
from pathlib import Path

from app.config import get_settings
from app.models import ZaloWebhookEvent, ChatRequest, ChatResponse, HealthResponse, MessageRole
from app.conversation import conversation_manager
from app.gemini_client import generate_reply, extract_order_async
from app.intent_handler import check_needs_fallback_smart
from app.zalo_client import (
    send_text_message,
    notify_owner_fallback,
    verify_webhook_signature,
    get_valid_access_token as zalo_get_valid_access_token,
    ZALO_SIGNATURE_HEADER,
)
from app import database as db
from app.logger import setup_logging, get_logger

# Khởi tạo logging
setup_logging()
logger = get_logger(__name__)

settings = get_settings()

# Giữ tham chiếu tới các background task (asyncio.create_task) – event loop
# chỉ giữ weak reference nên task có thể bị garbage-collected giữa chừng nếu
# không có nơi nào khác giữ tham chiếu tới nó.
_background_tasks: set = set()

# ─────────────────────────────────────────────
# Admin Auth (bảo vệ /admin, /stats, /orders, /api/conversations)
# ─────────────────────────────────────────────

_admin_security = HTTPBasic(auto_error=False)


def require_admin(credentials: HTTPBasicCredentials = Depends(_admin_security)):
    """
    Yêu cầu HTTP Basic Auth cho các endpoint hiển thị dữ liệu tổng hợp
    (thống kê, đơn hàng, lịch sử chat toàn bộ user). Nếu ADMIN_PASSWORD chưa
    được cấu hình trong .env → bỏ qua xác thực (giữ nguyên hành vi demo cũ),
    nhưng sẽ có cảnh báo lúc khởi động server.
    """
    if not settings.admin_password:
        return
    valid = (
        credentials is not None
        and secrets.compare_digest(credentials.username, settings.admin_username)
        and secrets.compare_digest(credentials.password, settings.admin_password)
    )
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )

app = FastAPI(
    title="AI Zalo OA Chatbot – Bếp Sạch Việt",
    description=(
        "Trợ lý AI tự động trả lời tin nhắn khách hàng trên Zalo OA "
        "cho shop đặc sản chế biến sẵn Bếp Sạch Việt. Sử dụng Google Gemini 2.5 Flash."
    ),
    version="0.6.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─────────────────────────────────────────────
# Startup Event – Khởi tạo Database
# ─────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    """Khởi tạo database khi server bắt đầu chạy."""
    db.init_db()
    logger.info("Server started – v%s", app.version)
    if not settings.admin_password:
        logger.warning(
            "ADMIN_PASSWORD chưa được cấu hình – /admin, /stats, /orders, "
            "/api/conversations đang MỞ CÔNG KHAI không cần đăng nhập. "
            "Đặt ADMIN_USERNAME/ADMIN_PASSWORD trong .env trước khi public server "
            "(vd. qua ngrok để nối Zalo OA)."
        )
    if settings.zalo_app_secret:
        logger.info("Đã cấu hình ZALO_APP_SECRET – webhook sẽ được xác thực chữ ký.")
    else:
        logger.warning(
            "ZALO_APP_SECRET chưa được cấu hình – /webhook đang CHẤP NHẬN mọi "
            "request mà không xác thực nguồn gốc từ Zalo."
        )
    if settings.zalo_app_id and settings.zalo_app_secret:
        logger.info("Đã cấu hình ZALO_APP_ID/SECRET – access token sẽ được tự động làm mới.")
    elif settings.zalo_oa_token:
        logger.warning(
            "Chỉ có ZALO_OA_TOKEN tĩnh, chưa có ZALO_APP_ID – token này sẽ tự "
            "hết hạn sau ~1 giờ và KHÔNG được tự động làm mới."
        )
    # Dọn dẹp session hết hạn định kỳ để tránh rò rỉ bộ nhớ (_cache/_last_active
    # tăng vô hạn nếu không ai chủ động gọi cleanup_expired_sessions()).
    task = asyncio.create_task(_periodic_session_cleanup())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    if settings.zalo_app_id and settings.zalo_app_secret:
        # Chủ động làm mới access token định kỳ (thay vì chỉ refresh lười khi
        # có tin nhắn cần gửi) để tránh độ trễ + phát hiện sớm nếu refresh_token
        # bị lỗi/hết hạn, thay vì chỉ biết khi có khách nhắn tin thật.
        token_task = asyncio.create_task(_periodic_zalo_token_refresh())
        _background_tasks.add(token_task)
        token_task.add_done_callback(_background_tasks.discard)


async def _periodic_session_cleanup(interval_sec: int = 600):
    """Định kỳ dọn dẹp session hội thoại đã hết hạn khỏi bộ nhớ cache."""
    while True:
        await asyncio.sleep(interval_sec)
        try:
            removed = conversation_manager.cleanup_expired_sessions()
            if removed:
                logger.info("Đã dọn dẹp %d session hết hạn khỏi cache.", removed)
        except Exception as e:
            logger.error("Lỗi khi dọn dẹp session hết hạn: %s", e, exc_info=True)


async def _periodic_zalo_token_refresh(interval_sec: int = 2700):
    """
    Định kỳ (mặc định 45 phút) chủ động làm mới Zalo OA access token trước
    khi hết hạn (~1 giờ), thay vì chỉ refresh lười lúc gửi tin. Chạy ngay 1
    lần lúc khởi động để đảm bảo có token sẵn sàng trước khi khách nhắn tin.
    """
    while True:
        try:
            token = await zalo_get_valid_access_token()
            if not token:
                logger.warning(
                    "Không lấy được Zalo OA access token hợp lệ (kiểm tra "
                    "ZALO_APP_ID/ZALO_APP_SECRET/ZALO_REFRESH_TOKEN_SEED)."
                )
        except Exception as e:
            logger.error("Lỗi khi tự động làm mới Zalo OA token: %s", e, exc_info=True)
        await asyncio.sleep(interval_sec)


# ─────────────────────────────────────────────
# Trang chủ (dùng để xác thực quyền sở hữu domain với Zalo bằng thẻ meta –
# xem ZALO_DOMAIN_VERIFICATION trong .env. Zalo yêu cầu bước này trước khi
# domain dùng được cho Webhook.)
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, tags=["System"])
def homepage():
    meta_tag = (
        f'<meta name="zalo-platform-site-verification" content="{settings.zalo_domain_verification}" />'
        if settings.zalo_domain_verification
        else ""
    )
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
{meta_tag}
<title>{settings.app_name}</title>
</head>
<body>{settings.app_name} đang hoạt động.</body>
</html>""")


# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Kiểm tra trạng thái hoạt động của server."""
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        gemini_configured=bool(settings.gemini_api_key),
        zalo_configured=bool(settings.zalo_oa_token),
    )


# ─────────────────────────────────────────────
# Zalo OA Webhook
# ─────────────────────────────────────────────

@app.get("/webhook", response_class=PlainTextResponse, tags=["Zalo OA"])
def verify_webhook(
    challenge: str = Query(..., description="Challenge string từ Zalo OA")
):
    """
    Xác minh webhook URL với Zalo OA.
    Zalo sẽ gửi GET request với query param 'challenge', server phải echo lại.
    """
    return challenge


@app.post("/webhook", tags=["Zalo OA"])
async def receive_webhook(request: Request):
    """
    Nhận sự kiện tin nhắn từ Zalo OA và tự động trả lời.
    Đây là endpoint production – được gọi bởi Zalo server.
    """
    raw_body = await request.body()
    try:
        body = json.loads(raw_body)
        event = ZaloWebhookEvent(**body)
    except Exception as e:
        logger.warning("Webhook parse error: %s", e)
        # Trả về 200 để Zalo không retry liên tục
        return {"status": "ignored", "reason": str(e)}

    received_mac = request.headers.get(ZALO_SIGNATURE_HEADER, "")
    if not verify_webhook_signature(raw_body, event.app_id or "", event.timestamp or "", received_mac):
        if settings.zalo_enforce_webhook_signature:
            logger.warning("Webhook signature không hợp lệ – từ chối request (có thể giả mạo).")
            return {"status": "ignored", "reason": "invalid_signature"}
        logger.warning(
            "Webhook signature không hợp lệ nhưng ZALO_ENFORCE_WEBHOOK_SIGNATURE=false "
            "nên vẫn xử lý tiếp (đang tạm tắt vì chưa xác định đúng OA Secret Key)."
        )

    # Chỉ xử lý sự kiện tin nhắn văn bản từ người dùng
    if event.event_name != "user_send_text":
        return {"status": "ignored", "event": event.event_name}

    user_id = event.sender.id if event.sender else "unknown"
    user_name = event.sender.display_name or "Khách hàng"
    user_message = event.message.text if event.message else ""

    if not user_message:
        return {"status": "ignored", "reason": "empty_message"}

    logger.info("[Zalo] %s (%s): %s", user_name, user_id, user_message[:100])

    # QUAN TRỌNG: Zalo yêu cầu webhook phản hồi 200 OK rất nhanh (có ràng buộc
    # về thời gian xử lý) – không được đợi Gemini sinh câu trả lời (thường mất
    # vài giây) rồi mới response, sẽ bị tính là timeout/lỗi (quan sát thực tế:
    # lỗi 408 khi test webhook lúc còn await trực tiếp ở đây). Nên trả 200 OK
    # ngay, xử lý Gemini + gửi trả lời ở tác vụ nền phía sau.
    task = asyncio.create_task(
        _handle_webhook_message_async(user_id, user_name, user_message)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"status": "ok"}


async def _handle_webhook_message_async(user_id: str, user_name: str, user_message: str):
    """Xử lý tin nhắn Zalo ngầm (sau khi webhook đã trả 200 OK cho Zalo)."""
    try:
        reply, needs_human, reason = await _process_message(user_id, user_name, user_message)
        await send_text_message(user_id, reply)

        if needs_human:
            await notify_owner_fallback(user_id, user_name, user_message, reason)
    except Exception as e:
        logger.error("Lỗi khi xử lý webhook (nền): %s", e, exc_info=True)


# ─────────────────────────────────────────────
# Mock Chat (Dev / Test)
# ─────────────────────────────────────────────

@app.post("/mock-chat", response_model=ChatResponse, tags=["Dev / Test"])
async def mock_chat(req: ChatRequest):
    """
    Giả lập hội thoại với AI mà không cần kết nối Zalo OA thật.
    Dùng cho mục đích phát triển và kiểm thử.
    """
    logger.info("[Mock] %s (%s): %s", req.user_name, req.user_id, req.message[:100])

    reply, needs_human, reason = await _process_message(
        req.user_id, req.user_name or "Khách hàng", req.message
    )
    return ChatResponse(
        user_id=req.user_id,
        reply=reply,
        needs_human=needs_human,
        fallback_reason=reason if reason else None,
        history_length=conversation_manager.get_history_length(req.user_id),
    )


@app.delete("/mock-chat/{user_id}", tags=["Dev / Test"])
def reset_conversation(user_id: str):
    """Xóa lịch sử hội thoại của một user (reset session – xóa cả DB)."""
    conversation_manager.clear_all(user_id)
    logger.info("Đã reset conversation cho user: %s", user_id)
    return {"status": "ok", "message": f"Đã xóa lịch sử hội thoại của user {user_id}"}


# ─────────────────────────────────────────────
# Statistics & Orders API
# ─────────────────────────────────────────────

@app.get("/stats", tags=["Analytics"], dependencies=[Depends(require_admin)])
def get_statistics(days: int = Query(default=7, description="Số ngày thống kê")):
    """Lấy thống kê hoạt động chatbot trong N ngày gần nhất."""
    return db.get_stats(days=days)


@app.get("/orders", tags=["Orders"], dependencies=[Depends(require_admin)])
def list_orders(
    user_id: str = Query(default=None, description="Lọc theo user_id"),
    status: str = Query(default=None, description="Lọc theo status"),
):
    """Xem danh sách đơn hàng."""
    orders = db.get_orders(user_id=user_id, status=status)
    return {"total": len(orders), "orders": orders}


@app.get("/api/conversations", tags=["Analytics"], dependencies=[Depends(require_admin)])
def list_conversations(
    user_id: str = Query(default=None, description="Lọc theo user_id"),
    limit: int = Query(default=50, description="Số tin nhắn tối đa"),
):
    """Lấy lịch sử hội thoại từ database."""
    if user_id:
        history = db.get_conversation_history(user_id, limit=limit)
        return {"user_id": user_id, "total": len(history), "messages": history}

    # Nếu không truyền user_id → lấy danh sách user gần nhất
    return db.get_recent_users(limit=limit)


# ─────────────────────────────────────────────
# Admin Dashboard
# ─────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse, tags=["Admin"], dependencies=[Depends(require_admin)])
def admin_dashboard():
    """Trang quản trị trực quan – xem thống kê, đơn hàng, lịch sử chat."""
    admin_path = Path(__file__).parent.parent / "static" / "admin.html"
    if not admin_path.exists():
        raise HTTPException(status_code=404, detail="Admin page not found")
    return HTMLResponse(content=admin_path.read_text(encoding="utf-8"))


@app.get("/chat", response_class=HTMLResponse, tags=["Dev / Test"])
def chat_ui():
    """Giao diện chat giả lập (giống Zalo) cho mục đích test/demo."""
    chat_path = Path(__file__).parent.parent / "static" / "chat.html"
    if not chat_path.exists():
        raise HTTPException(status_code=404, detail="Chat UI page not found")
    return HTMLResponse(content=chat_path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────
# Core Processing Logic
# ─────────────────────────────────────────────

async def _extract_and_save_order(user_id: str, user_name: str, history: list):
    """Background task để trích xuất đơn hàng và lưu DB."""
    try:
        order_data = await extract_order_async(history)
        if order_data:
            # Lưu vào DB (I/O đồng bộ – chạy trong thread pool để không block event loop)
            await asyncio.to_thread(
                db.create_order,
                user_id=user_id,
                user_name=user_name,
                products=order_data.get("products", []),
                total_amount=order_data.get("total_amount", 0),
                shipping_address=order_data.get("shipping_address", ""),
                payment_method=order_data.get("payment_method", ""),
                note=order_data.get("note", ""),
            )
            logger.info("[Order] Đã lưu đơn hàng mới cho user %s", user_id)
            # Ghi analytics
            await asyncio.to_thread(
                db.log_event,
                user_id, "order", {"status": "created", "amount": order_data.get("total_amount", 0)},
            )
    except Exception as e:
        logger.error("Lỗi khi extract_and_save_order: %s", e, exc_info=True)


async def _process_message(
    user_id: str, user_name: str, user_message: str
) -> tuple[str, bool, str]:
    """
    Xử lý một tin nhắn đến:
    1. Kiểm tra fallback intent
    2. Lấy lịch sử hội thoại
    3. Gọi Gemini sinh câu trả lời (async)
    4. Lưu lịch sử (cache + database)
    5. Ghi analytics event

    Returns:
        (reply: str, needs_human: bool, reason: str)
    """
    # 1. Kiểm tra fallback (từ khóa + xác nhận bằng Gemini)
    needs_human, reason = await check_needs_fallback_smart(user_message)

    if needs_human:
        reply = (
            "Mình xin lỗi vì sự bất tiện này! 😔 "
            "Vấn đề của bạn cần chủ shop trực tiếp hỗ trợ. "
            "Shop sẽ liên hệ lại với bạn trong thời gian sớm nhất nhé! 🙏"
        )
        # Ghi analytics event (I/O đồng bộ – chạy trong thread pool)
        await asyncio.to_thread(
            db.log_event, user_id, "fallback", {"reason": reason, "message": user_message}
        )
        logger.info("[Fallback] user=%s reason=%s", user_id, reason)
        return reply, True, reason

    # 2. Lấy lịch sử hội thoại (trước khi thêm tin nhắn hiện tại)
    history = await asyncio.to_thread(conversation_manager.get_history, user_id)

    # 3. Gọi Gemini (async – không block event loop)
    try:
        reply = await generate_reply(user_message, history)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        reply = "Xin lỗi, shop đang gặp sự cố kỹ thuật. Bạn vui lòng thử lại sau ít phút nhé! 🙏"
        logger.error("Gemini API error: %s", e, exc_info=True)
        # Ghi analytics event lỗi
        await asyncio.to_thread(
            db.log_event, user_id, "error", {"error": str(e), "message": user_message}
        )

    # 4. Lưu lịch sử hội thoại (cache + database) – I/O đồng bộ, chạy trong thread pool
    await asyncio.to_thread(conversation_manager.add_message, user_id, MessageRole.USER, user_message)
    await asyncio.to_thread(conversation_manager.add_message, user_id, MessageRole.ASSISTANT, reply)

    # 5. Ghi analytics event
    await asyncio.to_thread(db.log_event, user_id, "message", {"user_name": user_name})

    # 6. Kiểm tra Trigger trích xuất đơn hàng (đang tắt qua ENABLE_AUTO_ORDER –
    # xem ghi chú trong app/config.py. Giữ nguyên logic, chỉ chặn ở điều kiện
    # này để dễ bật lại sau này mà không cần sửa gì thêm.)
    if settings.enable_auto_order and "📦 ĐƠN HÀNG" in reply:
        logger.info("Phát hiện từ khóa chốt đơn! Kích hoạt trích xuất đơn hàng ngầm...")
        # Lấy history mới nhất (bao gồm cả tin nhắn vừa rồi) để trích xuất
        full_history = await asyncio.to_thread(conversation_manager.get_history, user_id)
        task = asyncio.create_task(_extract_and_save_order(user_id, user_name, full_history))
        # Giữ tham chiếu tới task – event loop chỉ giữ weak ref nên task có thể
        # bị garbage-collected giữa chừng (mất đơn hàng) nếu không lưu ở đâu khác.
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return reply, False, ""


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
