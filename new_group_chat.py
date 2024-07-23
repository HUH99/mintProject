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

# update된 group chat ID 확인
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
    
    
