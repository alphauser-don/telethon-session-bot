from telegram.ext import Application
from config.settings import Config
from bot.handlers import commands, session_gen

def main():
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(commands.start_handler)
    app.add_handler(commands.cmds_handler)
    app.add_handler(session_gen.conv_handler)
    app.add_handler(commands.owner_handlers)
    
    app.run_polling()

if __name__ == "__main__":
    main()
