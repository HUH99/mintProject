#### help 명령어, test 명령어, chat_id 확인 기능 추가
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

# update된 chat ID 확인
def getChatId():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    r = requests.get(url)
    data = r.json()

    if not data.get("ok"):
        logger.error(f"API 요청 실패: {data.get('description')}")
        return

    for item in data.get("result", []):
        message = item.get("message")
        if message and "chat" in message:
            chat = message["chat"]
            if chat.get("type") in ["group", "supergroup"]:
                group_name = chat.get("title")
                chat_id = chat.get("id")
                
                # .env 파일에서 해당 그룹의 chat_id가 이미 있는지 확인
                if not is_chat_id_in_env(group_name, chat_id):
                    append_to_env(group_name, chat_id)
                    logger.info(f"새로운 그룹 추가: {group_name} (ID: {chat_id})")
                else:
                    logger.info(f"기존 그룹 확인: {group_name} (ID: {chat_id})")

def is_chat_id_in_env(group_name, chat_id):
    env_key = f"{group_name}_CHAT_ID"
    return os.getenv(env_key) == str(chat_id)

def append_to_env(group_name, chat_id):
    with open(".env", "a") as f:
        f.write(f"\n{group_name}_CHAT_ID={chat_id}\n")
    # 환경 변수 다시 로드
    load_dotenv()

if __name__ == "__main__":
    getChatId()
    # application = Application.builder().token(TOKEN).build()
    # application.add_handler(CommandHandler("help", help_command))
    # application.add_handler(CommandHandler("test", test))
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    # application.run_polling(allowed_updates = Update.ALL_TYPES)
