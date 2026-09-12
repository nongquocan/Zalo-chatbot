# 🤖 AI Zalo OA Chatbot – Bếp Sạch Việt (Đặc sản chế biến sẵn)

> Trợ lý AI tự động trả lời tin nhắn khách hàng trên Zalo OA thật
> **Đề tài Thực tập tốt nghiệp**

---

## 📋 Mô tả

Hệ thống chatbot AI tích hợp **Zalo Official Account thật** với **Google Gemini 2.5 Flash** để tự động tư vấn và trả lời khách hàng cho **Bếp Sạch Việt** ([bepsachviet.com](https://bepsachviet.com)) – công ty chuyên đặc sản chế biến sẵn (vịt/gà/heo ủ xì dầu-muối, chả, ruốc, giò, nem...). Chatbot đã **kết nối và chạy thật** trên Zalo OA của doanh nghiệp: nhận webhook, tự động làm mới access token, trả lời khách qua Zalo API thật.

> Dữ liệu sản phẩm (60 SKU: giá gốc/giá khuyến mãi/tồn kho/đơn vị) lấy từ file Excel xuất bán hàng thật do chủ shop cung cấp (08/2026), mô tả sản phẩm đối chiếu với bài đăng Facebook chính thức của shop.

## 🏗️ Kiến trúc hệ thống

```
Khách hàng (Zalo)
      │
      ▼
[Zalo OA API] ──webhook──► [FastAPI Server] ──ngrok tunnel──► Internet
                                   │
                     ┌─────────────┴─────────────┐
                     │                           │
              [Gemini 2.5 Flash]        [Data Files (JSON) + SQLite]
                     │                  products / faq / shop_info /
                     │                  conversations / orders / zalo_tokens
                     └────────────┬──────────────┘
                                  │
                    [Trả lời khách qua Zalo OA API thật]
                                  │
                       [Fallback → Zalo chủ shop]
```

Webhook xử lý bất đồng bộ: phản hồi Zalo `200 OK` ngay lập tức, xử lý Gemini/trả lời trong tác vụ nền (tránh timeout 2s của Zalo).

## 📁 Cấu trúc thư mục

```
AI ZALO/
├── app/
│   ├── main.py           # FastAPI app (webhook, mock-chat, admin, stats)
│   ├── config.py         # Cấu hình từ .env (bao gồm feature flags)
│   ├── models.py         # Pydantic data models
│   ├── database.py       # SQLite: conversations, orders, analytics, zalo_tokens
│   ├── gemini_client.py  # Gọi Gemini API + trích xuất đơn hàng
│   ├── prompt_builder.py # Xây dựng system prompt từ data/*.json
│   ├── conversation.py   # Quản lý lịch sử hội thoại
│   ├── intent_handler.py # Phát hiện fallback intent (từ khóa + Gemini xác nhận)
│   ├── zalo_client.py    # Gọi Zalo OA API + tự làm mới access token
│   └── logger.py         # Cấu hình logging
├── data/
│   ├── products.json     # 60 sản phẩm thật của Bếp Sạch Việt
│   ├── faq.json          # Chính sách & FAQ
│   └── shop_info.json    # Thông tin công ty thật
├── static/
│   ├── chat.html          # Mock Chat UI để test không cần Zalo
│   └── admin.html          # Dashboard thống kê/đơn hàng
├── scripts/
│   └── seed_data.py       # Script khởi tạo dữ liệu mẫu
├── tests/
│   ├── mock_webhook.py    # Test nhanh 8 kịch bản
│   └── test_suite.py      # Bộ test đầy đủ 28 kịch bản + đo thời gian phản hồi
├── run.py                 # Chạy server + ngrok tunnel cùng lúc (dùng cho Zalo OA thật)
├── .env.example
├── requirements.txt
└── README.md
```

## ⚙️ Cài đặt

### 1. Yêu cầu
- Python 3.10+
- Gemini API Key từ [Google AI Studio](https://aistudio.google.com/app/apikey) (miễn phí)
- (Tuỳ chọn, để kết nối Zalo OA thật) App tạo trên [Zalo for Developers](https://developers.zalo.me), gắn với 1 Zalo OA thật

### 2. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### 3. Cấu hình môi trường

```bash
copy .env.example .env
```

Mở `.env` và điền tối thiểu `GEMINI_API_KEY`. Muốn kết nối Zalo OA thật thì điền thêm `ZALO_APP_ID`, `ZALO_APP_SECRET`, `ZALO_REFRESH_TOKEN_SEED`, `ZALO_DOMAIN_VERIFICATION`, `NGROK_DOMAIN` — xem chú thích chi tiết trong `.env.example`.

### 4. Chạy server

```bash
# Chỉ chạy server local, dùng Mock Chat UI để test — không cần Zalo OA
python -m uvicorn app.main:app --reload

# Hoặc chạy kèm ngrok tunnel để nhận webhook Zalo OA thật
python run.py
```

Server chạy tại `http://localhost:8000`; nếu dùng `run.py`, terminal sẽ in ra URL public (ngrok) để dán vào ô Webhook URL trên Zalo OA Admin.

## 🚩 Feature flags (bật/tắt tính năng không cần sửa code)

| Biến trong `.env` | Ý nghĩa |
|---|---|
| `ENABLE_AUTO_ORDER` | Bật/tắt việc AI tự trích xuất và xác nhận đơn hàng ngay trong chat. Đang tắt theo yêu cầu thực tế của Bếp Sạch Việt — chatbot tư vấn xong sẽ dẫn khách sang website/Zalo Mini App để đặt hàng, code trích xuất đơn hàng tự động vẫn giữ nguyên, sẵn sàng bật lại khi cần. |
| `ZALO_ENFORCE_WEBHOOK_SIGNATURE` | Bật/tắt việc chặn cứng khi chữ ký webhook không khớp. Đang tắt vì chưa xác định được đúng "OA Secret Key" dùng để tính chữ ký (khác với App Secret Key) — mismatch vẫn được log lại để theo dõi. |

## 🧪 Kiểm thử

### Swagger UI (API docs)
`http://localhost:8000/docs`

### Mock Chat UI (không cần Zalo OA)
`http://localhost:8000/chat`

### Bộ test tự động

```bash
# Test nhanh 8 kịch bản
python tests/mock_webhook.py

# Bộ test đầy đủ 28 kịch bản (14 nhóm tình huống) + đo thời gian phản hồi,
# xuất kết quả ra tests/test_results.json
python tests/test_suite.py
```

Kết quả lần chạy gần nhất trên dữ liệu thật: **25/28 (89,3%)** đạt, 0/28 lỗi 500, thời gian phản hồi trung bình ~6,4 giây (chưa tính lợi ích của xử lý webhook bất đồng bộ).

> ⚠️ **Lưu ý quota Gemini free tier**: quota thấp (quan sát thực tế ~20
> request/ngày cho `gemini-2.5-flash`, lỗi `429 ResourceExhausted`). Bước xác
> nhận fallback bằng Gemini tốn thêm 1 request mỗi tin nhắn nghi ngờ nên có
> thể hết quota nhanh khi test nhiều lần liên tiếp. Khi hết quota, hệ thống tự
> động lùi về kết quả lọc từ khóa (không crash, chỉ giảm độ chính xác) — xem
> `app/intent_handler.py::check_needs_fallback_smart`.

## 📝 Kịch bản hội thoại hỗ trợ

1. 📱 Hỏi giá sản phẩm, tình trạng còn hàng
2. 🛒 Hỏi cách đặt hàng → dẫn khách sang website/Zalo Mini App
3. 💰 Hỏi phương thức thanh toán (CK/COD)
4. 🚚 Hỏi phí ship, thời gian giao hàng
5. 🔄 Hỏi chính sách đổi trả, bảo quản
6. ⚠️ Khiếu nại/hàng lỗi, hỏi giá sỉ → chuyển người bán (Zalo thật cho chủ shop)

## 🛠️ Tech Stack

| Thành phần | Công nghệ |
|-----------|-----------|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| LLM | Google Gemini 2.5 Flash (`google-genai`) |
| Zalo OA | Webhook + OAuth v4 + gửi tin nhắn (Zalo OA API) |
| Tunnel | ngrok (`pyngrok`), domain tĩnh miễn phí |
| Lưu trữ | SQLite (`chatbot.db`: conversations/orders/analytics/zalo_tokens) + JSON files (dữ liệu sản phẩm/FAQ) |
| Import dữ liệu | `openpyxl` (đọc file Excel xuất bán hàng thật) |
| Môi trường | python-dotenv / pydantic-settings |

## 🔒 Giới hạn đã biết

- Đang chạy qua ngrok (tunnel tạm), phù hợp demo/thực tập — nếu vận hành lâu dài nên triển khai lên server/tên miền cố định.
- Chưa xác định được "OA Secret Key" đúng để verify chữ ký webhook (xem `ZALO_ENFORCE_WEBHOOK_SIGNATURE` ở trên).
- Quota Gemini free tier thấp, ảnh hưởng độ chính xác của bước xác nhận fallback khi bị giới hạn.

