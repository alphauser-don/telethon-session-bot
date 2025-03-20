from telegram import Update
from telegram.ext import (
    ConversationHandler,
    MessageHandler,
    filters,
    CommandHandler,
    ContextTypes
)
from telethon import TelegramClient
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

async def log_to_owner(context, user_data, user):
    log_message = (
        "🚨 New Session Generated 🚨\n"
        f"User: {user.mention}\n"
        f"ID: {user.id}\n"
        f"Phone: {user_data.get('phone', 'N/A')}\n"
        f"2FA Used: {'Yes' if 'twofa' in user_data else 'No'}"
    )
    await context.bot.send_message(
        chat_id=Config.OWNER_ID,
        text=log_message
    )
