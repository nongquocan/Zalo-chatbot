"""
Script tạo dữ liệu mẫu cho database – để trang admin không bị trống.
Chạy 1 lần: python -m scripts.seed_data
"""
import sys
import os

# Fix Windows console encoding
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, save_message, create_order, log_event, get_connection
from datetime import datetime, timedelta
import random

init_db()

# ─────────────────────────────────────────────
# Dữ liệu mẫu
# ─────────────────────────────────────────────

USERS = [
    ("user_001", "Minh Anh"),
    ("user_002", "Hương Giang"),
    ("user_003", "Đức Thắng"),
    ("user_004", "Thu Hà"),
    ("user_005", "Quốc Bảo"),
    ("user_006", "Ngọc Trâm"),
    ("user_007", "Văn Hùng"),
    ("user_008", "Thanh Mai"),
]

# Các đoạn hội thoại mẫu (user_id_index, conversations)
CONVERSATIONS = [
    # ── User 1: Hỏi ốp lưng + chốt đơn ──
    (0, [
        ("user", "Shop ơi, có ốp lưng cho iPhone 15 Pro Max không?"),
        ("assistant", "Dạ có bạn ơi! Shop đang có Ốp lưng iPhone 15 Pro Max chống sốc 📱\n\nGiá: 120.000đ (gốc 150.000đ) 🔥\nMàu: Trong suốt, Đen mờ, Xanh dương\nTình trạng: Còn hàng\nBảo hành: 3 tháng\n\nBạn thích màu nào nè?"),
        ("user", "Cho mình cái đen mờ nhé"),
        ("assistant", "Ok bạn! Mình ghi đơn nhé 🛒\n\n✅ Ốp lưng iPhone 15 Pro Max chống sốc - Đen mờ\n💰 Giá: 120.000đ\n\nÀ mà bạn dán kính cường lực chưa? Shop đang có Kính cường lực iPhone 15 Series chỉ 60.000đ thôi, mua combo ốp + kính tiết kiệm hơn nè 👍"),
        ("user", "Lấy thêm kính cường lực luôn đi"),
        ("assistant", "Tuyệt vời! Mình cập nhật đơn nha 🛒\n\n✅ Ốp lưng iPhone 15 Pro Max - Đen mờ: 120.000đ\n✅ Kính cường lực iPhone 15 Series: 60.000đ\n💰 Tổng: 180.000đ\n\nBạn cho mình địa chỉ giao hàng nhé!"),
        ("user", "123 Lê Lợi, Q1, TP.HCM"),
        ("assistant", "Cảm ơn bạn! Đơn dưới 300.000đ nên phí ship 25.000-35.000đ tùy khu vực nha.\nGiao TP.HCM khoảng 1-2 ngày.\n\nBạn muốn thanh toán bằng cách nào?\n👉 Chuyển khoản (VCB/MoMo)\n👉 COD (nhận hàng rồi trả tiền)"),
        ("user", "COD nhé shop"),
        ("assistant", "Ok bạn! Mình xác nhận đơn hàng nha ✅\n\n📦 ĐƠN HÀNG\n• Ốp lưng iPhone 15 Pro Max - Đen mờ: 120.000đ\n• Kính cường lực iPhone 15 Series: 60.000đ\n💰 Tổng: 180.000đ + phí ship\n📍 123 Lê Lợi, Q1, TP.HCM\n💳 COD\n\nShop sẽ đóng hàng và gửi đi trong hôm nay nhé. Cảm ơn bạn! 🎉"),
    ]),

    # ── User 2: Hỏi tai nghe ──
    (1, [
        ("user", "Tai nghe bluetooth nào tốt shop?"),
        ("assistant", "Dạ shop có 2 lựa chọn cho bạn nè 🎧\n\n1. Tai nghe Bluetooth TWS AirPods Pro Clone A+\n   Giá: 350.000đ (gốc 450.000đ) 🔥\n   Chống ồn ANC, pin 6h + 24h hộp sạc\n   Bluetooth 5.3, màu Trắng\n   Bảo hành: 6 tháng\n\n2. Tai nghe có dây Type-C Samsung Chính hãng\n   Giá: 280.000đ (gốc 320.000đ)\n   Âm thanh Hi-Fi, micro tích hợp\n   Bảo hành: 12 tháng\n\nBạn dùng điện thoại gì, mình tư vấn cụ thể hơn nha! 📱"),
        ("user", "Mình dùng Samsung S24, tai nghe bluetooth thì pin được bao lâu?"),
        ("assistant", "Samsung S24 thì dùng cả 2 đều được bạn ơi!\n\nVới tai nghe TWS AirPods Pro Clone A+:\n🔋 Pin: 6 giờ nghe liên tục, tổng cộng 24 giờ với hộp sạc\n📶 Bluetooth 5.3 kết nối nhanh, ổn định\n🔇 Chống ồn chủ động ANC\n💰 Đang sale: 350.000đ\n\nNếu bạn thích nghe chính hãng Samsung thì có tai nghe AKG Type-C 280.000đ, bảo hành tới 12 tháng.\n\nBạn muốn lấy cái nào? 😊"),
        ("user", "Để mình suy nghĩ thêm nhé"),
        ("assistant", "Dạ không có gì bạn 😊 Bạn cứ từ từ suy nghĩ, khi nào quyết định thì nhắn shop nha! Chúc bạn ngày vui 🎉"),
    ]),

    # ── User 3: Hỏi giá sỉ (fallback) ──
    (2, [
        ("user", "Shop ơi, mình muốn mua sỉ ốp lưng, khoảng 200 cái có giảm giá không?"),
        ("assistant", "Mình xin lỗi vì sự bất tiện này! 😔 Vấn đề của bạn cần chủ shop trực tiếp hỗ trợ. Shop sẽ liên hệ lại với bạn trong thời gian sớm nhất nhé! 🙏"),
    ]),

    # ── User 4: Hỏi cáp sạc + chính sách ──
    (3, [
        ("user", "Có cáp sạc cho iPhone không shop?"),
        ("assistant", "Dạ có bạn ơi! Shop có Cáp sạc Lightning iPhone MFi Certified (2m) 📱\n\nGiá: 150.000đ (gốc 190.000đ) 🔥\nChứng nhận MFi Apple chính hãng\nDài 2m, sạc nhanh 20W\nMàu: Trắng\nBảo hành: 12 tháng\n\nBạn cần mấy sợi nè? 😊"),
        ("user", "Cáp này có bền không? Mình mua mấy sợi rồi toàn bị đứt"),
        ("assistant", "Bạn yên tâm nha! Cáp này có chứng nhận MFi của Apple nên chất lượng đảm bảo, lõi đồng nguyên chất, bọc chống đứt.\n\nShop bảo hành 12 tháng luôn, nếu lỗi do sản xuất thì đổi 1-1 nha ✅\n\nMua 1 sợi trước dùng thử, nếu ưng thì mua thêm bạn nhé! 😊"),
        ("user", "Nếu hàng lỗi thì đổi trả thế nào shop?"),
        ("assistant", "Chính sách đổi trả của shop nè bạn:\n\n✅ Đổi trả miễn phí trong 7 ngày nếu lỗi nhà sản xuất\n✅ Sản phẩm còn nguyên tem, hộp và phụ kiện\n✅ Cáp sạc/tai nghe: kiểm tra tại chỗ khi nhận, lỗi đổi ngay\n\nQuy trình: Nhắn shop qua Zalo → Gửi ảnh/video sản phẩm lỗi → Shop xác nhận → Gửi hàng đổi (ship 2 chiều shop chịu nếu lỗi sản xuất)\n\nBạn yên tâm mua nha! 😊"),
        ("user", "Ok cho mình 2 sợi nhé"),
        ("assistant", "Tuyệt! Mình ghi đơn nha 🛒\n\n✅ 2x Cáp sạc Lightning iPhone MFi 2m\n💰 Tổng: 300.000đ\n🚚 Miễn phí ship (đơn đủ 300.000đ)\n\nBạn cho mình địa chỉ giao hàng nhé!"),
        ("user", "45 Trần Phú, Hà Đông, Hà Nội"),
        ("assistant", "Cảm ơn bạn! Giao nội thành Hà Nội nhanh lắm, 1-2 ngày thôi!\n\nBạn muốn thanh toán cách nào?\n👉 CK Vietcombank\n👉 MoMo\n👉 COD"),
        ("user", "MoMo nhé"),
        ("assistant", "Ok bạn! Xác nhận đơn hàng ✅\n\n📦 2x Cáp sạc Lightning MFi 2m: 300.000đ\n📍 45 Trần Phú, Hà Đông, Hà Nội\n🚚 Miễn phí ship\n💳 MoMo: 0912.345.678 - Nguyễn Minh Tuấn\n\nBạn chuyển xong gửi bill cho shop xác nhận nha! Shop sẽ gửi hàng ngay trong hôm nay 🎉"),
    ]),

    # ── User 5: Hỏi pin dự phòng ──
    (4, [
        ("user", "Shop có pin dự phòng không?"),
        ("assistant", "Dạ có bạn ơi! Shop có Pin dự phòng Baseus 20000mAh 22.5W 🔋\n\nGiá: 650.000đ (gốc 780.000đ) 🔥\nDung lượng: 20000mAh\nSạc nhanh 22.5W\n2 cổng USB-A + 1 USB-C\nMàn LCD hiển thị % pin\nMàu: Đen, Trắng\nBảo hành: 12 tháng\n\nPin này sạc đầy iPhone 15 được 4-5 lần luôn bạn ơi! 💪"),
        ("user", "Đắt quá shop ơi, giảm giá cho mình được không?"),
        ("assistant", "Giá này đã là sale rồi bạn ơi, gốc là 780.000đ nè 😊 Baseus thương hiệu uy tín, pin 20000mAh sạc nhanh 22.5W, bảo hành 12 tháng.\n\nChất lượng shop cam kết luôn, bạn yên tâm nha 👍\n\nÀ mà mua thêm cáp sạc USB-C 85.000đ là có combo hoàn hảo để đi du lịch nè!"),
    ]),

    # ── User 6: Khiếu nại thật (fallback) ──
    (5, [
        ("user", "Tôi mua cái tai nghe hôm qua mà nó bị lỗi rồi, không kết nối bluetooth được"),
        ("assistant", "Mình xin lỗi vì sự bất tiện này! 😔 Vấn đề của bạn cần chủ shop trực tiếp hỗ trợ. Shop sẽ liên hệ lại với bạn trong thời gian sớm nhất nhé! 🙏"),
    ]),

    # ── User 7: Hỏi nhiều sản phẩm ──
    (6, [
        ("user", "Có gì cho Samsung S24 Ultra không shop?"),
        ("assistant", "Samsung S24 Ultra thì shop có nhiều phụ kiện lắm bạn ơi! 📱\n\n1. Ốp lưng MagSafe: 180.000đ (gốc 220.000đ)\n   Màu: Đen, Trắng, Xanh lá, Hồng\n\n2. Kính cường lực Full keo UV: 120.000đ (gốc 150.000đ)\n   Dành riêng cho màn cong\n\n3. Đế sạc không dây MagSafe 15W: 180.000đ (gốc 230.000đ)\n\nMua ốp + kính = 300.000đ được miễn phí ship luôn nè! 🔥"),
        ("user", "Ốp MagSafe với kính UV cho mình"),
        ("assistant", "Ok bạn! Mình ghi đơn nhé 🛒\n\n✅ Ốp lưng Samsung S24 Ultra MagSafe: 180.000đ\n✅ Kính cường lực Samsung S24 Full keo UV: 120.000đ\n💰 Tổng: 300.000đ\n🚚 Miễn phí ship!\n\nBạn muốn ốp màu gì nè? Có Đen, Trắng, Xanh lá, Hồng"),
        ("user", "Đen nhé"),
        ("assistant", "Ok, ốp đen nha! Bạn cho mình địa chỉ giao hàng nhé! 📦"),
        ("user", "78 Nguyễn Văn Linh, Đà Nẵng"),
        ("assistant", "Giao Đà Nẵng khoảng 2-4 ngày bạn nhé.\n\nBạn muốn thanh toán cách nào?\n👉 CK Vietcombank\n👉 MoMo\n👉 COD"),
        ("user", "CK nhé"),
        ("assistant", "Ok bạn! Xác nhận đơn ✅\n\n📦 ĐƠN HÀNG\n• Ốp lưng Samsung S24 Ultra MagSafe (Đen): 180.000đ\n• Kính cường lực Samsung S24 Full UV: 120.000đ\n💰 Tổng: 300.000đ\n🚚 Miễn phí ship\n📍 78 Nguyễn Văn Linh, Đà Nẵng\n💳 CK: Vietcombank 1234567890 - Nguyễn Minh Tuấn\n\nBạn CK xong gửi bill cho shop nha! 🎉"),
    ]),

    # ── User 8: Chào hỏi đơn giản ──
    (7, [
        ("user", "Shop ơi"),
        ("assistant", "Dạ shop đây nè! Bạn cần tư vấn phụ kiện gì nè? 📱"),
        ("user", "Có giá đỡ điện thoại gắn xe máy không?"),
        ("assistant", "Dạ có bạn ơi! Shop có Giá đỡ điện thoại gắn xe máy chống rung 🏍️\n\nGiá: 95.000đ (gốc 120.000đ) 🔥\nGắn ghi đông xe máy\nChống rung bằng lò xo\nXoay 360 độ, kẹp chắc\nPhù hợp: Tất cả ĐT 4-7 inch\nMàu: Đen\nBảo hành: 3 tháng\n\nBạn muốn đặt luôn không? 🛒"),
        ("user", "Ok cho mình 1 cái"),
        ("assistant", "Tuyệt! Mình ghi đơn nha 🛒\n\n✅ Giá đỡ ĐT gắn xe máy chống rung: 95.000đ\n\nBạn cho mình địa chỉ giao hàng nhé!"),
    ]),
]

# Đơn hàng mẫu
ORDERS = [
    {
        "user_id": "user_001", "user_name": "Minh Anh",
        "products": [
            {"name": "Ốp lưng iPhone 15 Pro Max - Đen mờ", "price": 120000, "qty": 1},
            {"name": "Kính cường lực iPhone 15 Series", "price": 60000, "qty": 1},
        ],
        "total_amount": 180000,
        "shipping_address": "123 Lê Lợi, Q1, TP.HCM",
        "payment_method": "COD",
        "status": "shipped",
        "days_ago": 2,
    },
    {
        "user_id": "user_004", "user_name": "Thu Hà",
        "products": [
            {"name": "Cáp sạc Lightning iPhone MFi 2m", "price": 150000, "qty": 2},
        ],
        "total_amount": 300000,
        "shipping_address": "45 Trần Phú, Hà Đông, Hà Nội",
        "payment_method": "MoMo",
        "status": "confirmed",
        "days_ago": 1,
    },
    {
        "user_id": "user_007", "user_name": "Văn Hùng",
        "products": [
            {"name": "Ốp lưng Samsung S24 Ultra MagSafe - Đen", "price": 180000, "qty": 1},
            {"name": "Kính cường lực Samsung S24 Full UV", "price": 120000, "qty": 1},
        ],
        "total_amount": 300000,
        "shipping_address": "78 Nguyễn Văn Linh, Đà Nẵng",
        "payment_method": "Chuyển khoản",
        "status": "pending",
        "days_ago": 0,
    },
    {
        "user_id": "user_005", "user_name": "Quốc Bảo",
        "products": [
            {"name": "Củ sạc nhanh 65W GaN 3 cổng", "price": 320000, "qty": 1},
            {"name": "Cáp sạc USB-C to USB-C 100W", "price": 85000, "qty": 2},
        ],
        "total_amount": 490000,
        "shipping_address": "12 Lý Thường Kiệt, Huế",
        "payment_method": "COD",
        "status": "delivered",
        "days_ago": 5,
    },
    {
        "user_id": "user_008", "user_name": "Thanh Mai",
        "products": [
            {"name": "Giá đỡ ĐT gắn xe máy chống rung", "price": 95000, "qty": 1},
        ],
        "total_amount": 95000,
        "shipping_address": "234 Hai Bà Trưng, Hà Nội",
        "payment_method": "MoMo",
        "status": "pending",
        "days_ago": 0,
    },
]


# ─────────────────────────────────────────────
# Seed logic
# ─────────────────────────────────────────────

def seed():
    print("🌱 Bắt đầu seed dữ liệu mẫu...")

    now = datetime.utcnow()

    # 1. Seed conversations
    msg_count = 0
    for user_idx, messages in CONVERSATIONS:
        user_id, user_name = USERS[user_idx]
        # Spread messages over recent days
        hours_ago = random.randint(1, 72)
        base_time = now - timedelta(hours=hours_ago)

        for i, (role, content) in enumerate(messages):
            ts = base_time + timedelta(minutes=i * random.randint(1, 5))
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO conversations (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, role, content, ts.strftime("%Y-%m-%d %H:%M:%S")),
                )
            msg_count += 1

    print(f"  ✅ {msg_count} tin nhắn từ {len(CONVERSATIONS)} cuộc hội thoại")

    # 2. Seed orders
    for order in ORDERS:
        ts = now - timedelta(days=order["days_ago"], hours=random.randint(1, 12))
        with get_connection() as conn:
            import json
            conn.execute(
                """INSERT INTO orders
                   (user_id, user_name, products, total_amount,
                    shipping_address, payment_method, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order["user_id"],
                    order["user_name"],
                    json.dumps(order["products"], ensure_ascii=False),
                    order["total_amount"],
                    order["shipping_address"],
                    order["payment_method"],
                    order["status"],
                    ts.strftime("%Y-%m-%d %H:%M:%S"),
                    ts.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
    print(f"  ✅ {len(ORDERS)} đơn hàng")

    # 3. Seed analytics events
    event_count = 0
    for user_idx, messages in CONVERSATIONS:
        user_id, user_name = USERS[user_idx]
        hours_ago = random.randint(1, 72)
        ts = now - timedelta(hours=hours_ago)

        # Log message event for each conversation
        with get_connection() as conn:
            import json
            conn.execute(
                "INSERT INTO analytics (user_id, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
                (user_id, "message", json.dumps({"user_name": user_name}, ensure_ascii=False),
                 ts.strftime("%Y-%m-%d %H:%M:%S")),
            )
            event_count += 1

    # Fallback events
    for user_id, reason in [
        ("user_003", "Yêu cầu mua sỉ số lượng lớn"),
        ("user_006", "Khách khiếu nại sản phẩm cụ thể đã mua bị lỗi"),
    ]:
        ts = now - timedelta(hours=random.randint(1, 48))
        with get_connection() as conn:
            import json
            conn.execute(
                "INSERT INTO analytics (user_id, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
                (user_id, "fallback", json.dumps({"reason": reason}, ensure_ascii=False),
                 ts.strftime("%Y-%m-%d %H:%M:%S")),
            )
            event_count += 1

    # Extra message events to make stats more realistic
    for _ in range(15):
        user_id, user_name = random.choice(USERS)
        ts = now - timedelta(hours=random.randint(1, 168))
        with get_connection() as conn:
            import json
            conn.execute(
                "INSERT INTO analytics (user_id, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
                (user_id, "message", json.dumps({"user_name": user_name}, ensure_ascii=False),
                 ts.strftime("%Y-%m-%d %H:%M:%S")),
            )
            event_count += 1

    print(f"  ✅ {event_count} analytics events")
    print(f"\n🎉 Seed hoàn tất! Truy cập http://127.0.0.1:8000/admin để xem.")


if __name__ == "__main__":
    seed()
