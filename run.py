"""
Script khởi động nhanh chatbot: chạy cả FastAPI và Ngrok cùng lúc.
Tạo public URL để cấu hình Webhook trên Zalo OA.
"""
import sys
import os
import multiprocessing
import uvicorn
import time

from app.config import get_settings
from app.logger import get_logger, setup_logging

settings = get_settings()

def run_server():
    """Chạy FastAPI server (Uvicorn)."""
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,  # Ngrok không thích hợp dùng chung với reload
    )

def _find_ngrok_binary():
    """
    Tìm file ngrok.exe đã cài qua winget (khuyến nghị), thay vì để pyngrok tự
    tải bản riêng — bản pyngrok tự tải hay bị Windows Defender chặn nhầm là
    virus. Thứ tự ưu tiên: PATH hệ thống -> thư mục cài của winget.
    """
    import shutil
    import glob

    found = shutil.which("ngrok")
    if found:
        return found

    winget_glob = os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Ngrok.Ngrok_*\ngrok.exe"
    )
    matches = glob.glob(winget_glob)
    if matches:
        return matches[0]

    return None


def run_ngrok():
    """Chạy Ngrok để tạo tunnel (Localhost -> Internet)."""
    try:
        from pyngrok import ngrok
        import pyngrok.conf

        # Chỉ log error cho ngrok để console không bị nhiễu
        pyngrok.conf.get_default().log_event_callback = None

        # Dùng ngrok.exe đã cài qua winget thay vì để pyngrok tự tải (hay bị
        # Windows Defender chặn nhầm). Nếu không tìm thấy, để pyngrok tự lo
        # như mặc định (sẽ báo lỗi rõ ràng nếu vẫn bị chặn).
        ngrok_bin = _find_ngrok_binary()
        if ngrok_bin:
            pyngrok.conf.get_default().ngrok_path = ngrok_bin
            print(f"[INFO] Dùng ngrok tại: {ngrok_bin}")
        else:
            print(
                "\n[LƯU Ý] Không tìm thấy ngrok.exe đã cài qua winget — pyngrok "
                "sẽ tự tải bản riêng (có thể bị Windows Defender chặn). Nếu lỗi, "
                "chạy 'winget install ngrok.ngrok' trước."
            )

        # Mở tunnel HTTP tới port của FastAPI. Nếu đã cấu hình NGROK_DOMAIN
        # (domain tĩnh miễn phí) thì dùng luôn domain đó -> URL cố định, không
        # đổi mỗi lần chạy lại, khỏi phải vào Zalo cấu hình lại Webhook.
        if settings.ngrok_domain:
            tunnel = ngrok.connect(settings.port, domain=settings.ngrok_domain)
        else:
            tunnel = ngrok.connect(settings.port)
            print(
                "\n[LƯU Ý] Chưa cấu hình NGROK_DOMAIN trong .env -> URL bên dưới "
                "sẽ đổi mỗi lần chạy lại. Lấy domain tĩnh miễn phí tại "
                "dashboard.ngrok.com -> Domains -> New Domain, rồi điền vào .env."
            )
        public_url = tunnel.public_url

        print("\n" + "="*60)
        print("🚀 SERVER ĐANG CHẠY - ZALO WEBHOOK SẴN SÀNG")
        print("="*60)
        print(f"👉 NGROK URL: {public_url}")
        print(f"👉 Cấu hình Zalo Webhook bằng URL này: {public_url}/webhook")
        print("="*60)
        print("💡 Hướng dẫn cấu hình Zalo OA:")
        print("1. Vào Zalo OA Admin -> Quản lý -> Thiết lập ứng dụng")
        print("2. Paste URL trên vào ô 'Webhook URL'")
        print("3. Chọn các sự kiện: 'user_send_text', 'user_send_image', ...")
        print("4. Lưu lại và nhắn tin thử vào Zalo OA của bạn")
        print("="*60 + "\n")
        
        # Giữ thread sống
        while True:
            time.sleep(1)

    except ImportError:
        print("\n[ERROR] Không tìm thấy thư viện 'pyngrok'.")
        print("Vui lòng chạy: pip install pyngrok")
    except Exception as e:
        print(f"\n[ERROR] Không thể khởi động Ngrok: {e}")
        print("Bạn có thể cần cấu hình NGROK_AUTHTOKEN bằng cách chạy:")
        print("ngrok config add-authtoken <YOUR_TOKEN>")


if __name__ == "__main__":
    setup_logging()
    
    # Chạy server trong process riêng
    server_process = multiprocessing.Process(target=run_server)
    server_process.start()

    # Chờ server khởi động 2 giây
    time.sleep(2)

    # Chạy ngrok trong process chính
    try:
        run_ngrok()
    except KeyboardInterrupt:
        print("\nĐang tắt server...")
        server_process.terminate()
        server_process.join()
        sys.exit(0)
