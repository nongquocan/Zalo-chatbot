import asyncio
from app import database as db
from app.gemini_client import extract_order_async
from app.models import ChatMessage, MessageRole

async def test():
    db.init_db()
    # Get history of test_order_01
    raw_history = db.get_conversation_history("test_order_01", limit=20)
    history = [ChatMessage(role=MessageRole.USER if r["role"] == "user" else MessageRole.ASSISTANT, content=r["content"]) for r in raw_history]
    
    print("Testing extraction on history...")
    result = await extract_order_async(history)
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(test())
