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
        self.check_status_task = None

    async def initialize(self):
        await self.read_config()
        self.check_status_task = asyncio.create_task(self.check_message_status())

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
        """_summary_

        Args:
            stock_name (str): _description_
            message (Message): _description_
        """
        if message is None:
            logger.warning(f"{stock_name}에 대한 메시지 트래킹을 시작할 수 없습니다. 메시지 객체가 None입니다.")
        else:
            self.tracked_messages[stock_name] = {
            'message_id': message.message_id, # '메시지 ID
            'sent_time': message.date, # 첫 의견 메시지 전송 시간
            'replied': False, # 참여내역 확인 여부
            'replied_time': None, # 참여의견 답장 시간
            'confirmed': False, # 참여내역 확인 여부
            'confirmed_time': None, # 참여내역 확인 시간
        }
        logger.info(f"{message.date}에 전송한 {stock_name}에 대한 메시지 트래킹을 시작합니다.")

    async def check_message_status(self):
        while True:
            for stock_name, info in self.tracked_messages.items():
                current_time = datetime.now(timezone.utc)
                
                if not info['replied']:
                    await self.check_reply_status(stock_name, info, current_time)
                elif not info['confirmed']:
                    await self.check_participation_status(stock_name, info, current_time)
            
            await asyncio.sleep(60)  # 1분마다 상태 확인

    # 고객사 메시지 처리
    async def process_message(self, message: Message):
        if message.from_user.id in self.mint_staff_ids:
            return # 민트 실무진의 메시지는 무시

        for stock_name, info in self.tracked_messages.items():
            if not info['replied'] and message.date > info['sent_time']:
                await self.handle_reply(stock_name, message.date)
                await self.message.reply_text("f{stock_name} 참여내역 부탁드립니다.")
            elif info['replied'] and not info['confirmed']:
                #참여내역 확인 프로세스
                await self.handle_participation(stock_name, message)
                await self.message.reply_text("f{stock_name} 참여내역 확인했습니다. 감사합니다.")

    async def handle_reply(self, stock_name: str, reply_time: datetime):
        info = self.tracked_messages[stock_name]
        info['replied'] = True
        info['replied_time'] = reply_time
        await self.application.bot.send_message(
            chat_id=self.mint_group_chat_id,
            text=f"{self.client_name}이 {stock_name} 참여의견을 확인했습니다. 참여내역을 기다립니다."
        )
        
    
    async def handle_participation(self, stock_name: str, message: Message):
        if await self.participation_process(message, stock_name):
            info = self.tracked_messages[stock_name]
            info['confirmed'] = True
            info['confirmed_time'] = message.date
            await self.application.bot.send_message(
                chat_id=self.mint_group_chat_id,
                text=f"{self.client_name}의 {stock_name} 참여내역을 확인했습니다."
            )

    async def check_reply_status(self, stock_name: str, info: dict, current_time: datetime):
        elapsed_time = (current_time - info['sent_time'].replace(tzinfo=timezone.utc)).total_seconds()
        if elapsed_time >= 900:  # 15분
            await self.send_not_replied_alert(stock_name)
        elif elapsed_time >= 300 and elapsed_time % 300 < 60:  # 5분마다
            await self.send_reply_reminder(stock_name)

    async def check_participation_status(self, stock_name: str, info: dict, current_time: datetime):
        elapsed_time = (current_time - info['replied_time'].replace(tzinfo=timezone.utc)).total_seconds()
        if elapsed_time >= 900:  # 15분
            await self.send_not_confirmed_alert(stock_name)
        elif elapsed_time >= 600 and elapsed_time % 600 < 60:  # 10분마다
            await self.send_participation_reminder(stock_name)

    async def send_reply_reminder(self, stock_name: str):
        await self.application.bot.send_message(
            chat_id=self.chat_id,
            text=f"{stock_name}에 대한 참여의견을 확인해 주시길 바랍니다."
        )

    async def send_not_replied_alert(self, stock_name: str):
        alert_message = f"""
        -----------------------------긴급-------------------------
        {self.client_name}이 {stock_name} 참여의견을 확인하지 않았습니다!
        ----------------------------------------------------------
        """
        await self.application.bot.send_message(
            chat_id=self.mint_group_chat_id,
            text=alert_message
        )
        logger.info(f"{self.client_name}이 {stock_name} 참여의견을 확인하지 않아 긴급 알림을 보냈습니다.")


    async def send_not_confirmed_alert(self, stock_name: str):
        alert_message = f"""
        -----------------------------긴급-------------------------
        {self.client_name}이 {stock_name} 참여내역을 전송하지 않았습니다!
        ----------------------------------------------------------
        """
        await self.application.bot.send_message(
            chat_id=self.mint_group_chat_id,
            text=alert_message
        )
        
        logger.info(f"{self.client_name}이 {stock_name} 참여내역을 전송하지 않아 긴급 알림을 보냈습니다.")
            

    # 참여내역 전송 리마인더
    async def send_participation_reminder(self, stock_name: str):
        await self.application.bot.send_message(
            chat_id=self.chat_id,
            text=f"{stock_name}에 대한 참여내역을 보내주시기 바랍니다."
        )

    # 참여내역 확인 프로세스
    async def participation_process(self, message: Message, stock_name: str) -> bool:
        """수요예측 참여내역을 확인하고 처리하는 함수. 참여내역은 텍스트, 이미지, 문서 형식으로 전송된다.

        Args:
            update (Update): 텔레그램 봇 업데이트 객체
            stock_name (str): 수요예측을 진행하는 주식 종목명
            stock_advisory (StockAdvisory): StockAdvisory 인스턴스

        Returns:
            Bool: 참여내역 확인 후 처리한 경우 True, 그렇지 않은 경우 False
        """
        # 여기에 참여내역 확인 로직 구현
        return True

    # 참여내역 처리 후 엑셀 파일 업데이트 로직
    async def update_participation_data(stock_name: str, client_name: str, participation_data: dict):
        # 엑셀 파일 업데이트 로직
        return


    async def stop(self):
        if self.check_status_task:
            self.check_status_task.cancel()
            try:
                await self.check_status_task
            except asyncio.CancelledError:
                pass