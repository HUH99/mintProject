from telegram.ext import Application
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

class MessageTracker:
    def __init__(self, application: Application, our_staff_ids):
        self.application = application
        self.our_staff_ids = our_staff_ids
        self.tracked_messages = {}

    async def start_tracking(self, chat_id, message_id):
        self.tracked_messages[message_id] = {
            'chat_id': chat_id,
            'confirmed': False,
            'start_time': asyncio.get_event_loop().time()
        }
        self.application.create_task(self.check_message(message_id))

    async def check_message(self, message_id):
        while not self.tracked_messages[message_id]['confirmed']:
            await asyncio.sleep(300)  # 5분마다 확인
            message = await self.application.bot.get_messages(
                self.tracked_messages[message_id]['chat_id'],
                message_id
            )
            readers = set(message.read_by) - set(self.our_staff_ids)
            if readers: # 고객사 실무진이 한 명이라도 읽었을시 readers = True
                self.tracked_messages[message_id]['confirmed'] = True
                print(f"수요예측 메시지 (ID: {message_id})를 읽었습니다.")
            elif asyncio.get_event_loop().time() - self.tracked_messages[message_id]['start_time'] > 3600: # 1시간이 지나도 읽지 않았을시
                await self.send_alert(message_id)
                break

    async def send_alert(self, message_id):
        for staff_id in self.our_staff_ids:
            await self.application.bot.send_message(
                chat_id=staff_id,
                text=f"알림: 수요예측 메시지 (ID:{message_id})를 한 시간 동안 읽지 않았습니다."
            )
        print(f"Alert sent for message {message_id}")