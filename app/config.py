"""
Cấu hình ứng dụng – load từ file .env
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Zalo OA (điền sau khi đăng ký)
    zalo_app_id: str = ""      # App ID tạo trên Zalo for Developers, gắn với OA
    zalo_app_secret: str = ""  # Secret Key của app (verify webhook + đổi/refresh token)
    zalo_owner_id: str = ""    # Zalo user_id của chủ shop, nhận thông báo fallback

    # Access token/refresh token thật được LẤY TỰ ĐỘNG và lưu vào DB (bảng
    # zalo_tokens) sau lần đầu, không đọc lại từ đây mỗi lần gửi tin — vì access
    # token Zalo chỉ sống 1 giờ. Hai giá trị dưới đây CHỈ dùng làm "hạt giống"
    # (seed) để bootstrap lần chạy đầu tiên:
    #   - zalo_oa_token: có thể để trống, hoặc dán tạm access token ngắn hạn để
    #     test nhanh (sẽ tự hết hạn sau ~1 giờ nếu không có refresh_token).
    #   - zalo_refresh_token_seed: refresh_token lấy được từ bước đổi
    #     authorization code lần đầu (xem hướng dẫn) – dùng để tự động sinh
    #     access token mới. Sau lần refresh đầu tiên, hệ thống lưu refresh_token
    #     MỚI vào DB và không cần giá trị seed này nữa (refresh_token cũ chỉ
    #     dùng được 1 lần).
    zalo_oa_token: str = ""
    zalo_refresh_token_seed: str = ""

    # Admin Dashboard (bảo vệ /admin, /stats, /orders, /api/conversations)
    admin_username: str = "admin"
    admin_password: str = ""  # để trống = chưa bật xác thực (chỉ dùng khi demo nội bộ)

    # App
    app_name: str = "AI Zalo OA Chatbot - Bếp Sạch Việt"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Conversation
    max_history_turns: int = 10
    session_timeout_minutes: int = 30

    # Tự động trích xuất & lưu đơn hàng khi chatbot chốt đơn qua chat.
    # ĐANG TẮT theo yêu cầu: khách được dẫn ra website/Zalo Mini App để tự đặt
    # hàng thay vì chốt đơn ngay trong khung chat. Code trích xuất đơn hàng
    # (extract_order_async, database.create_order, bảng "orders"...) vẫn giữ
    # nguyên, chỉ cần đổi lại True nếu sau này muốn bật lại tính năng này.
    enable_auto_order: bool = False

    # BẬT/TẮT việc từ chối webhook khi chữ ký X-ZEvent-Signature không khớp.
    # Đang TẠM TẮT (False) vì chưa tìm ra đúng "OA Secret Key" dùng để ký (khác
    # App Secret Key) — công thức đã verify đúng cấu trúc (mac=<sha256 hex>,
    # ghép app_id+raw_body+timestamp+secret) nhưng sai giá trị secret nên mọi
    # webhook thật đều bị từ chối oan. Vẫn LOG warning khi sai để biết, chỉ là
    # không chặn xử lý. BẬT LẠI (True) ngay khi tìm/xác nhận được đúng secret.
    zalo_enforce_webhook_signature: bool = False

    # Xác thực quyền sở hữu domain với Zalo (bắt buộc trước khi domain dùng
    # được cho Webhook). Lấy giá trị "content" từ thẻ meta Zalo hiện ra ở
    # trang "Xác thực domain" -> "Thêm thẻ meta vào trang chủ trang web của bạn".
    zalo_domain_verification: str = ""

    # Ngrok (chạy local + expose ra internet qua run.py, dùng khi CHƯA deploy
    # lên server thật). Domain tĩnh miễn phí lấy tại dashboard.ngrok.com ->
    # Domains -> New Domain (dạng ten-ban.ngrok-free.app). Để trống thì mỗi
    # lần chạy sẽ ra 1 URL ngẫu nhiên khác nhau (phải cấu hình lại Webhook).
    ngrok_domain: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
