"""
Script giả lập webhook từ Zalo OA để test các kịch bản hội thoại.
Chạy: python tests/mock_webhook.py
Yêu cầu server đang chạy tại http://localhost:8000
"""
import httpx
import json

BASE_URL = "http://localhost:8000"
MOCK_CHAT_URL = f"{BASE_URL}/mock-chat"


def chat(user_id: str, message: str, user_name: str = "Khách test") -> dict:
    """Gửi một tin nhắn và in câu trả lời."""
    payload = {
        "user_id": user_id,
        "message": message,
        "user_name": user_name,
    }
    response = httpx.post(MOCK_CHAT_URL, json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()


def reset(user_id: str):
    """Xóa lịch sử hội thoại của user."""
    httpx.delete(f"{BASE_URL}/mock-chat/{user_id}")


def print_chat(user: str, result: dict):
    """In kết quả hội thoại theo định dạng dễ đọc."""
    needs_human = result.get("needs_human", False)
    human_icon = " [⚠️ FALLBACK → người bán]" if needs_human else ""
    print(f"\n  👤 User: {user}")
    print(f"  🤖 Bot : {result['reply']}{human_icon}")
    if result.get("fallback_reason"):
        print(f"  📋 Lý do fallback: {result['fallback_reason']}")
    print(f"  📊 Lịch sử: {result['history_length']} tin nhắn")


def run_demo():
    """
    Chạy một chuỗi hội thoại demo để kiểm thử các kịch bản.
    """
    user_id = "demo_user_001"
    print("=" * 60)
    print("  DEMO: AI Chatbot Shop Phụ Kiện Điện Thoại")
    print("=" * 60)

    # Reset session trước khi test
    reset(user_id)

    scenarios = [
        # Kịch bản 1: Hỏi giá sản phẩm
        "Shop ơi, ốp lưng iPhone 15 Pro Max giá bao nhiêu vậy?",

        # Kịch bản 2: Hỏi còn hàng
        "Còn màu xanh không shop?",

        # Kịch bản 3: Hỏi cách đặt hàng
        "Cho mình hỏi mua thì đặt kiểu gì vậy shop?",

        # Kịch bản 4: Hỏi thanh toán
        "Shop nhận thanh toán qua MoMo không?",

        # Kịch bản 5: Hỏi ship
        "Mình ở Đà Nẵng ship mấy ngày shop?",

        # Kịch bản 6: Chốt đơn
        "Ok mình lấy 1 cái ốp iPhone 15 Pro Max màu trong suốt nhé. Địa chỉ: 56 Lê Lợi, Hải Châu, Đà Nẵng",

        # Kịch bản 7: Hỏi đổi trả
        "Nếu hàng lỗi thì đổi trả thế nào shop?",

        # Kịch bản 8: Fallback – khiếu nại
        "Shop ơi hàng mình nhận bị lỗi rồi, hàng hỏng hết rồi, mình muốn khiếu nại",
    ]

    for msg in scenarios:
        print(f"\n{'─' * 50}")
        try:
            result = chat(user_id, msg)
            print_chat(msg, result)
        except Exception as e:
            print(f"  ❌ Lỗi: {e}")

    print(f"\n{'=' * 60}")
    print("  Demo hoàn thành!")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
