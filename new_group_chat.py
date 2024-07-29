# group chat_id 확인. 수작업 용 
import logging
import os
import requests
import json
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

# 새로운 그룹의 chat_id를 수동으로 가져오는 함수
def get_chatId_oneself(group_name):
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
            if chat.get("type") in ["group", "supergroup"] and chat.get("title") == group_name:
                chat_id = chat.get("id")
                print(chat_id)
                return
            
    # chat_id를 찾은 경우
    if chat_id: 
        print(chat_id)
        logger.info(f"새로운 그룹 chat id: {group_name} (ID: {chat_id})")
        return chat_id
    # chat_id를 찾지 못한 경우
    else:
        logger.error(f"{group_name}의 chat_id를 찾을 수 없습니다. 그룹 이름을 확인해 주세요.")
        return None


if __name__ == "__main__":
    group_name = input("chat ID를 찾고자 하는 그룹채팅방 이름을 입력하세요: ")
    get_chatId_oneself(group_name)
    
    
