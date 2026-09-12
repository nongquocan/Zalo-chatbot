"""
Quản lý lịch sử hội thoại theo user_id.
Sử dụng SQLite để lưu trữ bền vững + in-memory cache cho hiệu suất.
Tự động xóa session không hoạt động sau session_timeout_minutes.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict
from app.models import ChatMessage, MessageRole
from app.config import get_settings
from app import database as db

settings = get_settings()


class ConversationManager:
    def __init__(self):
        # In-memory cache cho session đang hoạt động (truy cập nhanh)
        self._cache: Dict[str, List[ChatMessage]] = defaultdict(list)
        # Thời gian hoạt động cuối cùng của mỗi user
        self._last_active: Dict[str, datetime] = {}
        # user_id đã được hydrate từ DB ít nhất 1 lần trong process này.
        # Dùng để chỉ auto-load từ DB sau khi server restart (cache trống thật sự),
        # KHÔNG load lại sau khi session hết hạn (nếu không thì timeout sẽ vô nghĩa
        # vì lịch sử cũ sẽ được nạp lại y nguyên ngay sau khi vừa "xóa").
        self._loaded_from_db: set = set()

    def _is_expired(self, user_id: str) -> bool:
        """Kiểm tra session đã hết hạn chưa."""
        if user_id not in self._last_active:
            return False
        timeout = timedelta(minutes=settings.session_timeout_minutes)
        return datetime.now() - self._last_active[user_id] > timeout

    def _touch(self, user_id: str):
        """Cập nhật thời gian hoạt động của user."""
        self._last_active[user_id] = datetime.now()

    def _load_from_db(self, user_id: str):
        """
        Load lịch sử hội thoại từ database vào cache.
        Chỉ load 1 lần cho mỗi user_id trong vòng đời process (ví dụ sau khi
        restart server) – KHÔNG load lại sau khi session hết hạn, để việc hết
        hạn thực sự bắt đầu một ngữ cảnh hội thoại mới với Gemini.
        """
        if user_id in self._loaded_from_db:
            return
        max_messages = settings.max_history_turns * 2
        rows = db.get_conversation_history(user_id, limit=max_messages)
        self._cache[user_id] = [
            ChatMessage(role=MessageRole(row["role"]), content=row["content"])
            for row in rows
        ]
        self._loaded_from_db.add(user_id)
        if self._cache[user_id]:
            self._touch(user_id)

    def add_message(self, user_id: str, role: MessageRole, content: str):
        """Thêm một tin nhắn vào lịch sử hội thoại (cache + database)."""
        # Xóa session cũ nếu hết hạn
        if self._is_expired(user_id):
            self.clear(user_id)

        msg = ChatMessage(role=role, content=content)

        # Lưu vào database (bền vững)
        db.save_message(user_id, role.value, content)

        # Cập nhật cache
        self._cache[user_id].append(msg)

        # Giữ tối đa max_history_turns * 2 message trong cache
        max_messages = settings.max_history_turns * 2
        if len(self._cache[user_id]) > max_messages:
            self._cache[user_id] = self._cache[user_id][-max_messages:]

        self._touch(user_id)

    def get_history(self, user_id: str) -> List[ChatMessage]:
        """Lấy lịch sử hội thoại (trừ tin nhắn cuối cùng đang xử lý)."""
        if self._is_expired(user_id):
            # Session hết hạn → bắt đầu ngữ cảnh mới, KHÔNG nạp lại lịch sử cũ
            # từ DB (nếu không thì session_timeout_minutes sẽ vô tác dụng).
            self.clear(user_id)
            return []

        # Load từ DB nếu cache chưa từng được nạp trong process này
        # (ví dụ sau khi restart server).
        self._load_from_db(user_id)

        return self._cache.get(user_id, [])

    def clear(self, user_id: str):
        """Xóa lịch sử hội thoại của user khỏi cache (DB giữ lại cho analytics)."""
        self._cache.pop(user_id, None)
        self._last_active.pop(user_id, None)

    def clear_all(self, user_id: str):
        """Xóa hoàn toàn lịch sử hội thoại (cả cache lẫn database)."""
        self._cache.pop(user_id, None)
        self._last_active.pop(user_id, None)
        self._loaded_from_db.discard(user_id)
        db.clear_conversation(user_id)

    def get_history_length(self, user_id: str) -> int:
        return len(self._cache.get(user_id, []))

    def cleanup_expired_sessions(self):
        """Dọn dẹp tất cả session đã hết hạn trong cache."""
        expired_users = [uid for uid in self._last_active if self._is_expired(uid)]
        for uid in expired_users:
            self.clear(uid)
        return len(expired_users)


# Singleton – dùng chung toàn ứng dụng
conversation_manager = ConversationManager()
