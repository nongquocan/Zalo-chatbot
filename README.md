# 🤖 AI Zalo OA Chatbot – Bếp Sạch Việt (Đặc sản chế biến sẵn)

> Trợ lý AI tự động trả lời tin nhắn khách hàng trên Zalo OA  
> **Đề tài TTTN – B22DCCN050 – Học viện Công nghệ Bưu chính Viễn thông**

---

## 📋 Mô tả

Hệ thống chatbot AI tích hợp **Zalo Official Account** với **Google Gemini 2.5 Flash** để tự động tư vấn và trả lời khách hàng cho **Bếp Sạch Việt** – shop chuyên đặc sản chế biến sẵn (vịt/gà/heo/cá ủ xì dầu, chả, ruốc, giò, nem...). Dự án đang ở giai đoạn **40% (Proof of Concept)** – các module core đã hoạt động, chờ tích hợp Zalo OA thật.

> Dữ liệu sản phẩm/giá lấy từ bảng báo giá đại lý thực tế của Bếp Sạch Việt (08/2026) và trang bepsachviet.com. Giá trong `products.json` là giá đại lý tham khảo – cần xác nhận lại giá bán lẻ chính thức với chủ shop trước khi vận hành thật.

## 🏗️ Kiến trúc hệ thống

```
Khách hàng (Zalo)
      │
      ▼
[Zalo OA API] ──webhook──► [FastAPI Server :8000]
                                   │
                     ┌─────────────┴─────────────┐
                     │                           │
              [Gemini 2.5 Flash]        [Data Files (JSON)]
                     │                  products / faq / shop_info
                     └────────────┬──────────────┘
                                  │
                       [Trả lời → Khách hàng]
                                  │
                       [Fallback → Người bán]
```

## 📁 Cấu trúc thư mục

```
AI ZALO/
├── app/
│   ├── main.py           # FastAPI app (webhook + mock-chat)
│   ├── config.py         # Cấu hình từ .env
│   ├── models.py         # Pydantic data models
│   ├── gemini_client.py  # Gọi Gemini API
│   ├── prompt_builder.py # Xây dựng system prompt
│   ├── conversation.py   # Quản lý lịch sử hội thoại
│   ├── intent_handler.py # Phát hiện fallback intent
│   └── zalo_client.py    # Gọi Zalo OA API
├── data/
│   ├── products.json     # 60 sản phẩm (lấy từ file Excel import sản phẩm thật của shop)
│   ├── faq.json          # Chính sách & FAQ
│   └── shop_info.json    # Thông tin shop
├── tests/
│   └── mock_webhook.py   # Script test hội thoại
├── .env.example
├── requirements.txt
└── README.md
```

## ⚙️ Cài đặt

### 1. Yêu cầu
- Python 3.10+
- Gemini API Key từ [Google AI Studio](https://aistudio.google.com/app/apikey) (miễn phí)

### 2. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### 3. Cấu hình môi trường

```bash
# Sao chép file mẫu
copy .env.example .env

# Mở .env và điền GEMINI_API_KEY
```

File `.env`:
```
GEMINI_API_KEY=AIza...  ← Dán API key vào đây
```

### 4. Chạy server

```bash
python -m uvicorn app.main:app --reload
```

Server sẽ chạy tại: `http://localhost:8000`

## 🧪 Kiểm thử

### Swagger UI (API docs)
Mở trình duyệt: `http://localhost:8000/docs`

### Test qua mock-chat (không cần Zalo OA)

```bash
# Terminal 1: Chạy server
python -m uvicorn app.main:app --reload

# Terminal 2: Chạy test demo (8 kịch bản)
python tests/mock_webhook.py

# Hoặc bộ test đầy đủ (28 kịch bản + đo thời gian phản hồi, xuất tests/test_results.json)
python tests/test_suite.py
```

> ⚠️ **Lưu ý về quota Gemini free tier**: API key free tier hiện bị giới hạn khá
> thấp (quan sát thực tế: `quota_value: 20` request/ngày cho `gemini-2.5-flash`,
> báo lỗi `429 ResourceExhausted`). Vì bước xác nhận fallback bằng Gemini (xem
> mục dưới) tốn thêm 1 request cho các tin nhắn nghi ngờ, quota có thể hết rất
> nhanh khi chạy `tests/test_suite.py` nhiều lần trong ngày hoặc demo trực tiếp
> nhiều lượt. Khi hết quota, hệ thống tự động dùng lại kết quả lọc từ khóa làm
> phương án dự phòng (không crash, chỉ giảm độ chính xác) — xem
> `app/intent_handler.py::check_needs_fallback_smart`. Nên nâng cấp lên gói trả
> phí hoặc dùng API key khác trước khi demo/nộp báo cáo để có kết quả ổn định.

### Test thủ công qua curl

```bash
curl -X POST http://localhost:8000/mock-chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user001", "message": "Shop ơi ốp iPhone 15 giá bao nhiêu?"}'
```

## 🎯 Tiến độ hiện tại (Tháng 7)

| Module | Trạng thái |
|--------|-----------|
| Cấu trúc dự án | ✅ Hoàn thành |
| Dữ liệu sản phẩm mẫu (15 SP) | ✅ Hoàn thành |
| Dữ liệu FAQ & chính sách shop | ✅ Hoàn thành |
| FastAPI server + webhook endpoint | ✅ Hoàn thành |
| Gemini 2.5 Flash integration | ✅ Hoàn thành |
| System prompt builder | ✅ Hoàn thành |
| Conversation history manager | ✅ Hoàn thành |
| Mock chat endpoint (test) | ✅ Hoàn thành |
| Fallback intent detection (từ khóa) | ✅ Hoàn thành |
| Fallback intent detection (Gemini xác nhận, giảm false-positive) | ✅ Hoàn thành |
| Gửi thông báo Zalo thật cho chủ shop khi fallback | ✅ Hoàn thành (code sẵn sàng, cần `ZALO_OA_TOKEN` + `ZALO_OWNER_ID` thật) |
| Bộ test 28 câu + đo thời gian phản hồi | ✅ Hoàn thành (`tests/test_suite.py`) |
| Zalo OA webhook thật | 🔲 Chờ đăng ký OA |
| Gửi tin trả lời khách qua Zalo API thật | 🔲 Chờ OA token |
| Báo cáo đánh giá kết quả | 🔲 Kế hoạch tháng tới |

## 📝 Kịch bản hội thoại hỗ trợ

1. 📱 Hỏi giá sản phẩm, tình trạng còn hàng
2. 🛒 Hỏi cách đặt hàng
3. 💰 Hỏi phương thức thanh toán (CK/COD/MoMo)
4. 🚚 Hỏi phí ship, thời gian giao hàng
5. 🔄 Hỏi chính sách đổi trả, bảo hành
6. ✅ Chốt đơn hàng – AI tóm tắt
7. ⚠️ Khiếu nại/hàng lỗi → Chuyển người bán

## 🛠️ Tech Stack

| Thành phần | Công nghệ |
|-----------|-----------|
| Backend | Python 3.10+, FastAPI |
| LLM | Google Gemini 2.5 Flash |
| Webhook | Zalo OA API v3 |
| Dữ liệu | JSON files |
| Môi trường | python-dotenv |

---

**Sinh viên**: Nông Quốc Ân – B22DCCN050  
**GVHD**: TS. Nguyễn Quang Hưng  
**Học viện**: Học viện Công nghệ Bưu chính Viễn thông
