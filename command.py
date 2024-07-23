import logging
import os
import requests
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 봇 토큰 로드
load_dotenv() # 이걸 써줘야 환경을 읽어들여서 os.getenv()로 사용 가능
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def help_command(update, context):
    await update.message.reply_text("민트투자자문 수요예측 봇입니다.")

async def test(update, context):
    await update.message.reply_text("테스트 메시지입니다.")

async def echo(update, context):
    await update.message.reply_text(update.message.text)

if __name__ == "__main__":
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.run_polling(allowed_updates = Update.ALL_TYPES)