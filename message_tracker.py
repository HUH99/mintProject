# 고객사가 메시지 확인했는지 트래킹하는 클래스
# message_tracker.py

import asyncio
import json
import aiofiles
from telegram import Message, Bot
import telegram
from telegram.ext import Application
import typing
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
class MessageTracker:
    def __init__(self, application: Application, client_name: str, chat_id: int):
        self.application = application
        self.client_name = client_name
        self.chat_id = chat_id
        self.tracked_messages = {} # 트래킹 중인 메시지 정보 = {stock_name: message_info}
        self.config = None
        self.mint_staff_ids = None
        self.mint_group_chat_id = None


    async def initialize(self, stock_name: str):
        await self.read_config()
        self.tracked_messages[stock_name] = {}


    async def read_config(self):
        try:
            async with aiofiles.open('config.json', mode='r', encoding="UTF-8") as f:
                content = await f.read()
                self.config = json.loads(content)
                self.mint_staff_ids = set(self.config['mint_staff_ids'].values())
                self.mint_group_chat_id = self.config['mint_group_chat_id']

        except Exception as e:
            logger.error(f"설정 파일을 읽는 중 오류 발생: {str(e)}")
            raise

    # 메시지 트래킹 시작
    async def start_tracking(self, stock_name: str, message: Message):
        """특정 주식 종목의 수요예측에 참여하는 특정 고객사의 메시지 트래킹

        Args:
            stock_name (str): _description_
            message (Message): _description_
        """
        
        self.tracked_messages[stock_name] = {
        'message_id': message.message_id, # '메시지 ID
        'sent_time': message.date, # 첫 의견 메시지 전송 시간
        'replied': False, # 참여내역 확인 여부
        'replied_time': None, # 참여의견 답장 시간
        'confirmed': False, # 참여내역 확인 여부
        'confirmed_time': None, # 참여내역 확인 시간
        'timeout': False # 메시지 트래킹 타임아웃 여부
        }
        logger.info(f"시각: {message.date} | {stock_name}에 대한 {self.client_name}의 메시지 트래킹을 시작합니다.")


    async def check_message_status(self, stock_name: str):
        while True:
            info = self.tracked_messages[stock_name]
            if info is None:
                logger.error(f"{stock_name}에 대한 트래킹 정보가 없습니다.")
                return True


            current_time = datetime.now(timezone.utc)
            
            if not info['replied']:
                await self.check_reply_status(stock_name, info, current_time)
                
            elif not info['confirmed']:
                await self.check_participation_status(stock_name, info, current_time)

            if info['replied'] and info['confirmed']:
                logger.info(f"{stock_name}에 대한 {self.client_name}의 메시지 트래킹이 완료되었습니다.")
                return True

            if info['timeout']:
                logger.info(f"{stock_name}에 대한 {self.client_name}의 메시지 트래킹이 타임아웃되었습니다.")
                return True

            await asyncio.sleep(0.2)

    # 고객사 메시지 처리
    async def process_message(self, message: Message):
        if message.from_user and  message.from_user.id in self.mint_staff_ids:
            logger.info(f"민트 실무진의 메시지는 무시합니다.")
            return # 민트 실무진의 메시지는 무시

        for stock_name, info in list(self.tracked_messages.items()):
            if not info['replied'] and message.date > info['sent_time']:
                await self.handle_reply(stock_name, message)
                await self.message.reply_text("f{stock_name} 참여내역 확인해주시면 감사하겠습니다.")
                return
            elif info['replied'] and not info['confirmed'] and message.date > info['replied_time']:
                # 참여내역 확인 프로세스
                await self.handle_participation(stock_name, message)
                await self.message.reply_text("f{stock_name} 참여내역 확인했습니다. 감사합니다.")
                return
        
        logger.info(f"처리할 수 없는 메시지를 받았습니다: {message.text}")
        
        # 모든 종목에 대해 replied와 confirmed가 True인지 확인
        # all_completed = all(info['replied'] and info['confirmed'] for info in self.tracked_messages.values())
        # if all_completed:
        #    logger.info(f"{self.client_name}의 모든 종목에 대한 처리가 완료되었습니다.")

    async def handle_reply(self, stock_name: str, message: Message):
        self.tracked_messages[stock_name]['replied'] = True
        self.tracked_messages[stock_name]['replied_time'] = message.date
        logger.info(f"{self.client_name}이 {stock_name} 참여의견을 확인했습니다. 참여내역을 기다립니다.")
        await self.application.bot.send_message(
            chat_id=self.mint_group_chat_id,
            text=f"{self.client_name}이 {stock_name} 참여의견을 확인했습니다. 참여내역을 기다립니다."
        )
        
    
    async def handle_participation(self, stock_name: str, message: Message):
        if await self.process_participation(message, stock_name):
            logger.info(f"\"{self.client_name}\"의 \"{stock_name}\" 참여내역을 확인했습니다.")
            await self.application.bot.send_message(
                chat_id=self.mint_group_chat_id,
                text=f"\"{self.client_name}\"의 \"{stock_name}\" 참여내역을 확인했습니다."
            )
            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=f"네. \"{stock_name}\" 참여내역 확인했습니다. 감사합니다."
            )
            self.tracked_messages[stock_name]['confirmed'] = True
            self.tracked_messages[stock_name]['confirmed_time'] = message.date

    async def check_reply_status(self, stock_name: str, info: dict, current_time: datetime):
        elapsed_time = (current_time - info['sent_time'].replace(tzinfo=timezone.utc)).total_seconds()
        if 61 >= elapsed_time >= 60:  # 15분 (900초) 경과
            await self.send_not_replied_alert(stock_name)
            self.tracked_messages[stock_name]['timeout'] = True
        elif elapsed_time >= 30 and elapsed_time % 30 < 1:  # 5분마다
            await self.send_reply_reminder(stock_name)

    async def check_participation_status(self, stock_name: str, info: dict, current_time: datetime):
        elapsed_time = (current_time - info['replied_time'].replace(tzinfo=timezone.utc)).total_seconds()
        if elapsed_time >= 60:  # 15분 (900초) 경과
            await self.send_not_confirmed_alert(stock_name)
            self.tracked_messages[stock_name]['timeout'] = True
        elif 30 <= elapsed_time <= 31:  # 10분 지나면
            await self.send_participation_reminder(stock_name)

    async def send_reply_reminder(self, stock_name: str):
        logger.info(f"\"{self.client_name}\"이 {stock_name} 참여의견을 확인하지 않아 리마인더를 보냅니다.")
        await self.application.bot.send_message(
            chat_id=self.chat_id,
            text=f"\"{stock_name}\" 참여의견을 확인해 주시면 감사하겠습니다."
        )

    async def send_not_replied_alert(self, stock_name: str):
        alert_message = f"""
        -----------------------------긴급-------------------------
        \"{self.client_name}\"이 \"{stock_name}\" 참여의견을 확인하지 않았습니다!
----------------------------------------------------------
        """
        await self.application.bot.send_message(
            chat_id=self.mint_group_chat_id,
            text=alert_message
        )
        logger.info(f"\"{self.client_name}\"이 \"{stock_name}\" 참여의견을 확인하지 않아 긴급 알림을 보냈습니다.")


    async def send_not_confirmed_alert(self, stock_name: str):
        alert_message = f"""
        -----------------------------긴급-------------------------
        \"{self.client_name}\"이 \"{stock_name}\" 참여내역을 전송하지 않았습니다!
----------------------------------------------------------
        """
        await self.application.bot.send_message(
            chat_id=self.mint_group_chat_id,
            text=alert_message
        )
        
        logger.info(f"\"{self.client_name}\"이 \"{stock_name}\" 참여내역을 전송하지 않아 긴급 알림을 보냈습니다.")
            

    # 참여내역 전송 리마인더
    async def send_participation_reminder(self, stock_name: str):
        await self.application.bot.send_message(
            chat_id=self.chat_id,
            text=f"{stock_name} 참여내역 확인해주시면 감사하겠습니다."
        )

    # 참여내역 확인 프로세스
    async def process_participation(self, message: Message, stock_name: str) -> bool:
        """수요예측 참여내역을 확인하고 처리하는 함수. 참여내역은 텍스트, 이미지, 문서 형식으로 전송된다.

        Args:
            update (Update): 텔레그램 봇 업데이트 객체
            stock_name (str): 수요예측을 진행하는 주식 종목명
            stock_advisory (StockAdvisory): StockAdvisory 인스턴스

        Returns:
            Bool: 참여내역 확인 후 처리한 경우 True, 그렇지 않은 경우 False
        """
        # 여기에 참여내역 확인 로직 구현
        if message.text or message.photo or message.document:
            return True

    # 참여내역 처리 후 엑셀 파일 업데이트 로직
    async def update_participation_data(stock_name: str, client_name: str, participation_data: dict):
        # 기존 엑셀 파일과 참여내역 비교 후 업데이트 로직
        return
