"""
Bộ kiểm thử mở rộng (25-30 câu) cho chatbot, dùng để đo:
  - Độ chính xác chức năng cơ bản (fallback đúng/sai, câu trả lời có chứa
    thông tin bắt buộc như giá/tên sản phẩm hay không)
  - Thời gian phản hồi (latency) của từng request

Chạy: python tests/test_suite.py
Yêu cầu server đang chạy tại http://localhost:8000 (python -m uvicorn app.main:app --reload)

Kết quả được in ra console dạng bảng tổng hợp và xuất chi tiết ra
tests/test_results.json để đưa vào báo cáo đánh giá.
"""
import json
import time
from pathlib import Path
from statistics import mean, median

import httpx

BASE_URL = "http://localhost:8000"
MOCK_CHAT_URL = f"{BASE_URL}/mock-chat"
RESULTS_PATH = Path(__file__).parent / "test_results.json"


def reset(user_id: str):
    httpx.delete(f"{BASE_URL}/mock-chat/{user_id}", timeout=10.0)


def send(user_id: str, message: str) -> tuple[dict, float]:
    """Gửi 1 tin nhắn, trả về (response_json, latency_seconds)."""
    payload = {"user_id": user_id, "message": message, "user_name": "Khách test"}
    t0 = time.perf_counter()
    resp = httpx.post(MOCK_CHAT_URL, json=payload, timeout=60.0)
    latency = time.perf_counter() - t0
    resp.raise_for_status()
    return resp.json(), latency


# ─────────────────────────────────────────────
# Bộ kịch bản kiểm thử
# Mỗi case: messages là 1 chuỗi lượt hội thoại (dùng chung user_id để giữ ngữ
# cảnh); chỉ lượt CUỐI CÙNG mới được chấm điểm (các lượt trước chỉ để tạo bối cảnh).
# expected_fallback: giá trị fallback kỳ vọng ở lượt cuối (None = không kiểm tra)
# must_contain: các cụm từ (không phân biệt hoa/thường) kỳ vọng có trong câu trả
# lời cuối để coi là "có vẻ đúng" (kiểm tra tự động thô, không thay thế đánh giá
# thủ công về chất lượng ngôn ngữ)
# ─────────────────────────────────────────────

TEST_CASES = [
    # ---- 1. Hỏi giá sản phẩm ----
    {"id": "TC01", "category": "Giá sản phẩm", "user_id": "t_price_1",
     "messages": ["Chả vịt Vân Đình giá bao nhiêu shop?"],
     "expected_fallback": False, "must_contain": ["100.000", "100000"]},

    {"id": "TC02", "category": "Giá sản phẩm", "user_id": "t_price_2",
     "messages": ["Vịt ủ xì dầu nguyên con bán mấy tiền?"],
     "expected_fallback": False, "must_contain": ["300.000", "300000"]},

    {"id": "TC03", "category": "Giá sản phẩm", "user_id": "t_price_3",
     "messages": ["Gà ủ muối nguyên con bao tiền vậy shop?"],
     "expected_fallback": False, "must_contain": ["220.000", "220000", "220,000"]},

    # ---- 2. Hỏi tồn kho / hết hàng ----
    {"id": "TC04", "category": "Tồn kho", "user_id": "t_stock_1",
     "messages": ["Tai heo ủ xì dầu còn hàng không shop?"],
     "expected_fallback": False, "must_contain": ["còn", "9"]},

    {"id": "TC05", "category": "Tồn kho", "user_id": "t_stock_2",
     "messages": ["Nem hải sản còn không shop?"],
     "expected_fallback": False, "must_contain": []},

    # ---- 3. Quy cách đóng gói (đơn lượt) ----
    {"id": "TC06", "category": "Quy cách đóng gói", "user_id": "t_pack_1",
     "messages": ["Ruốc tôm rong biển đóng gói bao nhiêu gam vậy shop?"],
     "expected_fallback": False, "must_contain": ["250"]},

    # ---- 4. Ngữ cảnh đa lượt (context) ----
    {"id": "TC07", "category": "Ngữ cảnh đa lượt", "user_id": "t_ctx_1",
     "messages": [
         "Vịt ủ xì dầu nguyên con giá bao nhiêu shop?",
         "Có bán nửa con không?",
     ],
     "expected_fallback": False, "must_contain": ["150.000", "150000", "1/2"]},

    {"id": "TC08", "category": "Ngữ cảnh đa lượt", "user_id": "t_ctx_2",
     "messages": [
         "Chả cá thác lác có mấy loại vậy shop?",
         "Loại tẩm gia vị giá bao nhiêu?",
     ],
     "expected_fallback": False, "must_contain": ["150.000", "150000"]},

    # ---- 5. Bảo quản / cách dùng ----
    {"id": "TC09", "category": "Bảo quản/Cách dùng", "user_id": "t_store_1",
     "messages": ["Vịt ủ xì dầu bảo quản thế nào, để được bao lâu?"],
     "expected_fallback": False, "must_contain": []},

    {"id": "TC10", "category": "Bảo quản/Cách dùng", "user_id": "t_store_2",
     "messages": ["Ruốc cá thu có cần để ngăn mát không shop?"],
     "expected_fallback": False, "must_contain": []},

    # ---- 6. Quy trình đặt hàng ----
    {"id": "TC11", "category": "Đặt hàng", "user_id": "t_order_1",
     "messages": ["Mình muốn mua thì đặt hàng kiểu gì vậy shop?"],
     "expected_fallback": False, "must_contain": ["mini app", "website", "web"]},

    # ---- 7. Thanh toán ----
    {"id": "TC12", "category": "Thanh toán", "user_id": "t_pay_1",
     "messages": ["Shop có nhận chuyển khoản không?"],
     "expected_fallback": False, "must_contain": ["chuyển khoản"]},

    {"id": "TC13", "category": "Thanh toán", "user_id": "t_pay_2",
     "messages": ["Cho hỏi có ship COD không shop?"],
     "expected_fallback": False, "must_contain": []},

    # ---- 8. Vận chuyển ----
    {"id": "TC14", "category": "Vận chuyển", "user_id": "t_ship_1",
     "messages": ["Ship ngoài Hà Nội có được không shop?"],
     "expected_fallback": False, "must_contain": []},

    {"id": "TC15", "category": "Vận chuyển", "user_id": "t_ship_2",
     "messages": ["Mua bao nhiêu thì được free ship vậy shop?"],
     "expected_fallback": False, "must_contain": ["5kg", "5 kg"]},

    # ---- 9. Đổi trả / bảo quản chính sách ----
    {"id": "TC16", "category": "Đổi trả/Chính sách", "user_id": "t_faq_1",
     "messages": ["Chính sách đổi trả của shop như thế nào?"],
     "expected_fallback": False, "must_contain": []},

    {"id": "TC17", "category": "Đổi trả/Chính sách", "user_id": "t_faq_2",
     "messages": ["Hàng đông lạnh để ngăn đá được mấy tháng shop?"],
     "expected_fallback": False, "must_contain": ["6"]},

    # ---- 10. Ngoài phạm vi dữ liệu ----
    {"id": "TC18", "category": "Ngoài phạm vi", "user_id": "t_oos_1",
     "messages": ["Shop có bán ốp lưng điện thoại không?"],
     "expected_fallback": False, "must_contain": []},

    {"id": "TC19", "category": "Ngoài phạm vi", "user_id": "t_oos_2",
     "messages": ["Shop có bán rau củ tươi không?"],
     "expected_fallback": False, "must_contain": []},

    # ---- 11. Dẫn khách đặt hàng (thay cho "Chốt đơn" cũ – từ tháng 8 hệ
    # thống không tự nhận đặt đơn qua chat nữa mà dẫn khách ra web/Mini App,
    # xem mục 4.4.6 báo cáo) ----
    {"id": "TC20", "category": "Dẫn khách đặt hàng", "user_id": "t_checkout_1",
     "messages": [
         "Mình lấy 1 gói chả vịt Vân Đình với 1 gói tai heo ủ xì dầu.",
     ],
     "expected_fallback": False, "must_contain": ["mini app", "website", "web"]},

    # ---- 12. Fallback thật – khiếu nại ----
    {"id": "TC21", "category": "Fallback: khiếu nại", "user_id": "t_fb_1",
     "messages": ["Shop ơi hàng em nhận bị có mùi lạ, đồ ăn không ổn, muốn đổi trả gấp."],
     "expected_fallback": True, "must_contain": []},

    {"id": "TC22", "category": "Fallback: khiếu nại", "user_id": "t_fb_2",
     "messages": ["Đơn hàng của em bị giao nhầm sản phẩm khác rồi shop ơi."],
     "expected_fallback": True, "must_contain": []},

    {"id": "TC23", "category": "Fallback: khiếu nại", "user_id": "t_fb_3",
     "messages": ["Em đặt hàng 5 ngày rồi mà chưa nhận được, có bị mất hàng không vậy?"],
     "expected_fallback": True, "must_contain": []},

    # ---- 13. Fallback thật – giá sỉ ----
    {"id": "TC24", "category": "Fallback: giá sỉ", "user_id": "t_fb_4",
     "messages": ["Shop cho em hỏi giá sỉ nhập 50 gói chả vịt thì bao nhiêu?"],
     "expected_fallback": True, "must_contain": []},

    {"id": "TC25", "category": "Fallback: giá sỉ", "user_id": "t_fb_5",
     "messages": ["Bên em muốn hợp tác làm đại lý phân phối, ai phụ trách vậy shop?"],
     "expected_fallback": True, "must_contain": []},

    # ---- 14. False positive – câu hỏi chính sách chứa từ khóa nhạy cảm ----
    # Kỳ vọng SAU KHI nâng cấp bằng Gemini classification (tháng 7), các case
    # này KHÔNG fallback dù chứa từ khóa "hàng lỗi/hư hỏng".
    {"id": "TC26", "category": "False positive (đã fix)", "user_id": "t_fp_1",
     "messages": ["Nếu hàng lỗi thì đổi trả thế nào shop?"],
     "expected_fallback": False, "must_contain": []},

    {"id": "TC27", "category": "False positive (đã fix)", "user_id": "t_fp_2",
     "messages": ["Đồ đông lạnh bị hỏng thì xử lý sao ạ?"],
     "expected_fallback": False, "must_contain": []},

    {"id": "TC28", "category": "False positive (đã fix)", "user_id": "t_fp_3",
     "messages": ["Cho em hỏi mua sỉ với mua lẻ giá có khác nhau không shop, hay đồng giá luôn?"],
     "expected_fallback": None, "must_contain": []},
]


def evaluate_case(case: dict, final_result: dict) -> dict:
    reply_lower = final_result["reply"].lower()
    fallback_ok = (
        case["expected_fallback"] is None
        or final_result["needs_human"] == case["expected_fallback"]
    )
    contains_ok = (
        not case["must_contain"]
        or any(kw.lower() in reply_lower for kw in case["must_contain"])
    )
    passed = fallback_ok and contains_ok and bool(final_result["reply"].strip())
    return {"fallback_ok": fallback_ok, "contains_ok": contains_ok, "passed": passed}


def run_suite():
    print("=" * 70)
    print("  BỘ KIỂM THỬ MỞ RỘNG – AI Zalo OA Chatbot")
    print(f"  Tổng số kịch bản: {len(TEST_CASES)}")
    print("=" * 70)

    results = []

    for case in TEST_CASES:
        # Gemini free tier giới hạn số request/phút khá thấp; nghỉ giữa các ca
        # để tránh bị rate-limit (429) làm sai lệch kết quả đo latency.
        time.sleep(2.0)

        reset(case["user_id"])
        last_result, last_latency = None, None
        try:
            for msg in case["messages"]:
                last_result, last_latency = send(case["user_id"], msg)
        except Exception as e:
            results.append({
                "id": case["id"], "category": case["category"],
                "message": case["messages"][-1], "error": str(e),
                "passed": False, "latency_sec": None,
            })
            print(f"  ❌ {case['id']} [{case['category']}] — LỖI: {e}")
            continue

        evaluation = evaluate_case(case, last_result)
        status = "✅" if evaluation["passed"] else "❌"

        print(f"\n  {status} {case['id']} [{case['category']}]")
        print(f"     Hỏi : {case['messages'][-1]}")
        print(f"     Đáp : {last_result['reply'][:100]}{'...' if len(last_result['reply']) > 100 else ''}")
        print(f"     Fallback: {last_result['needs_human']} (kỳ vọng: {case['expected_fallback']})")
        print(f"     Thời gian phản hồi: {last_latency:.2f}s")

        results.append({
            "id": case["id"],
            "category": case["category"],
            "message": case["messages"][-1],
            "reply": last_result["reply"],
            "needs_human": last_result["needs_human"],
            "expected_fallback": case["expected_fallback"],
            "fallback_ok": evaluation["fallback_ok"],
            "contains_ok": evaluation["contains_ok"],
            "passed": evaluation["passed"],
            "latency_sec": round(last_latency, 3),
        })

    print_summary(results)
    RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  Đã lưu kết quả chi tiết vào: {RESULTS_PATH}")


def print_summary(results: list[dict]):
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    latencies = [r["latency_sec"] for r in results if r.get("latency_sec") is not None]

    print("\n" + "=" * 70)
    print("  TỔNG KẾT")
    print("=" * 70)
    print(f"  Tổng số ca kiểm thử : {total}")
    print(f"  Đạt (pass)          : {passed} ({passed / total * 100:.1f}%)")
    print(f"  Không đạt (fail)    : {total - passed}")

    if latencies:
        print(f"\n  Thời gian phản hồi trung bình : {mean(latencies):.2f}s")
        print(f"  Thời gian phản hồi trung vị   : {median(latencies):.2f}s")
        print(f"  Nhanh nhất / Chậm nhất        : {min(latencies):.2f}s / {max(latencies):.2f}s")

    # Nhóm theo category
    by_category: dict[str, list[dict]] = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r)

    print("\n  Chi tiết theo nhóm:")
    for cat, items in by_category.items():
        cat_passed = sum(1 for i in items if i["passed"])
        print(f"    - {cat}: {cat_passed}/{len(items)} đạt")

    failed = [r for r in results if not r["passed"]]
    if failed:
        print("\n  Các ca chưa đạt (cần xem lại thủ công):")
        for r in failed:
            print(f"    - {r['id']}: {r['message']}")


if __name__ == "__main__":
    run_suite()
