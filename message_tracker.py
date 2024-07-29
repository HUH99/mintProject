# 고객사가 메시지 확인했는지 트래킹하는 클래스
# message_tracker.py

import asyncio
import json
from telegram.ext import Application
import logging

class MessageTracker:
    def __init__(self, application: Application):
        self.application = application
        self.tracked_messages = {}
        self.config = self.read_config()
        self.mint_staff_ids = set(self.config['mint_staff_ids'])
        self.mint_group_chat_id = self.config['mint_group_chat_id']

    def read_config(self):
        with open('config.json', 'r') as f:
            return json.load(f)

    # 
    async def start_tracking(self, chat_id, message_id, client_name, stock_name):
        self.tracked_messages[message_id] = {
            'chat_id': chat_id,
            'confirmed': False,
            'replied': False,
            'start_time': asyncio.get_event_loop().time(),
            'client_name': client_name,
            'stock_name': stock_name
        }
        self.application.create_task(self.check_message(message_id))

    async def check_message(self, message_id):
        message_info = self.tracked_messages[message_id]
        while not message_info['confirmed']:
            await asyncio.sleep(300)  # 5분마다 확인
            
            if not message_info['replied']:
                # 답장 확인
                updates = await self.application.bot.get_updates(offset=-1, limit=1)
                for update in updates:
                    if update.message and update.message.chat_id == message_info['chat_id']:
                        if update.message.from_user.id not in self.mint_staff_ids:
                            message_info['replied'] = True
                            logging.info(f"고객사가 메시지 (ID: {message_id})에 답장했습니다.")
                            return
                
                # 30분 경과 확인
                if asyncio.get_event_loop().time() - message_info['start_time'] > 1800:
                    await self.send_alert(message_id)
                    return
                
                # 답장이 없으면 메시지 재전송
                await self.resend_message(message_id)
            
            elif message_info['replied'] and not message_info['confirmed']:
                # 참여내역 확인 대기
                pass

    async def resend_message(self, message_id):
        message_info = self.tracked_messages[message_id]
        await self.application.bot.send_message(
            chat_id=message_info['chat_id'],
            text="수요예측 의견을 다시 한 번 확인해 주시기 바랍니다."
        )

    async def send_alert(self, message_id):
        message_info = self.tracked_messages[message_id]
        alert_message = f"""
            ----------------------------------긴급------------------------------
            {message_info['client_name']}이 {message_info['stock_name']} 수요예측 메시지를 확인하지 않았습니다!
            --------------------------------------------------------------------
            """
        await self.application.bot.send_message(
            chat_id=self.mint_group_chat_id,
            text=alert_message
        )
        logging.info(f"Alert sent for message {message_id}")

    async def confirm_participation(self, chat_id):
        for message_id, info in self.tracked_messages.items():
            if info['chat_id'] == chat_id:
                info['confirmed'] = True
                logging.info(f"고객사가 메시지 (ID: {message_id})의 참여내역을 확인했습니다.")
                return True # 참여내역 확인 완료
        return False  # 해당 chat_id에 대한 메시지를 찾지 못한 경우
