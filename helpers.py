import asyncio
import os
from pyrogram.types import Message
from config import MAX_FILE_SIZE_MB

async def check_size_okay(file_size_bytes: int) -> bool:
    mb = file_size_bytes / (1024 * 1024)
    return mb <= MAX_FILE_SIZE_MB

async def delete_message_safe(message: Message):
    try:
        await message.delete()
    except Exception:
        pass
