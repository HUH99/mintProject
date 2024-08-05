import asyncio
import aiohttp
import json
import logging
from typing import Dict, Optional
import os
from dotenv import load_dotenv
import sys

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

class ChatIDCollector:
    def __init__(self, token: str, config_file: str):
        self.token = token
        self.config_file = config_file
        self.config: Dict = {}
        self.last_update_id = 0
        self.is_running = True

    async def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Loaded config: {self.config}")
        except FileNotFoundError:
            self.config = {"client_group_chat_id": {}}
        except json.JSONDecodeError:
            logger.error(f"{self.config_file} 파일의 형식이 잘못되었습니다.")
            self.config = {"client_group_chat_id": {}}

    async def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    async def get_updates(self) -> Dict:
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 60}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    return await resp.json()
        except asyncio.CancelledError:
            logger.info("getUpdates 요청이 취소되었습니다.")
            return {"ok": True, "result": []}

    # 새로운 그룹이 발견되면 config에 추가하고 그룹 이름을 반환
    async def process_updates(self, updates: Dict) -> Optional[str]:
        new_groups = []
        for update in updates.get("result", []):
            self.last_update_id = max(self.last_update_id, update["update_id"])
            if "message" in update and "chat" in update["message"]:
                chat = update["message"]["chat"]
                if chat["type"] in ["group", "supergroup"]:
                    group_name = chat["title"]
                    chat_id = chat["id"]
                    if group_name.startswith("민트-") and group_name not in self.config["client_group_chat_id"]:
                        self.config["client_group_chat_id"][group_name] = chat_id
                        logger.info(f"새로운 그룹 발견: {group_name} (ID: {chat_id})")
                        new_groups.append(group_name)

        if new_groups:
            await self.save_config()
        return new_groups


    async def run(self):
        await self.load_config()
        print("Chat ID 수집을 시작합니다. 종료하려면 'q'를 입력하세요.")
        while self.is_running:
            try:
                updates = await self.get_updates()
                new_groups = await self.process_updates(updates)
                if new_groups:
                    logger.info(f"새로운 그룹이 config.json 파일에 추가되었습니다: {', '.join(new_groups)}")
            except asyncio.CancelledError:
                logger.info("Chat ID 수집이 취소되었습니다.")
                break
            except Exception as e:
                logger.error(f"Chat ID 업데이트 처리 중 오류 발생: {e}")
            await asyncio.sleep(1)
        logger.info("Chat ID 수집이 종료되었습니다.")

    def stop(self):
        self.is_running = False
        logger.info("프로그램을 종료합니다.")

async def main():
    
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        return

    config_file = "config.json"
    collector = ChatIDCollector(TOKEN, config_file)
    
    # 키보드 입력을 처리하는 함수
    def handle_input():
        while True:
            if sys.stdin.readline().strip().lower() == 'q':
                collector.stop()
                break
    
     # 비동기로 입력 처리 실행
    input_task = asyncio.create_task(asyncio.to_thread(handle_input))
    
    # ChatIDCollector 실행
    collector_task = asyncio.create_task(collector.run())
    
    # 두 태스크 중 하나라도 완료되면 종료
    try:
        done, pending = await asyncio.wait(
            [input_task, collector_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # 남은 태스크 취소
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {e}")
    finally:
        logger.info("프로그램이 종료되었습니다.")

if __name__ == "__main__":
    asyncio.run(main())