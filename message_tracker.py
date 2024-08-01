# 고객사가 메시지 확인했는지 트래킹하는 클래스
# message_tracker.py

import asyncio
import json
import aiofiles
from telegram.ext import Application
import logging

logger = logging.getLogger(__name__)
class MessageTracker:
    def __init__(self, application: Application):
        self.application = application
        self.tracked_messages = {} # 트래킹 중인 메시지 정보
        self.config = None
        self.mint_staff_ids = None
        self.mint_group_chat_id = None

    async def initialize(self):
        await self.read_config()

    async def read_config(self):
        try:
            async with aiofiles.open('config.json', mode='r') as f:
                content = await f.read()
                self.config = json.loads(content)
                self.mint_staff_ids = set(self.config['mint_staff_ids'])
                self.mint_group_chat_id = self.config['mint_group_chat_id']

        except Exception as e:
            logger.error(f"설정 파일을 읽는 중 오류 발생: {str(e)}")
            raise

    # 메시지 트래킹 시작
    async def start_tracking(self, chat_id, message_id, client_name, stock_name):
        key = (chat_id, stock_name) # (민트-고객기관 채팅 ID, 종목명) 튜플을 트래킹 키로 사용
        self.tracked_messages[key] = {
            'message_id': message_id, # '메시지 ID
            'confirmed': False, # 참여내역 확인 여부
            'replied': False, # 답장 여부
            'start_time': asyncio.get_event_loop().time(), # 첫 의견 메시지 전송 시간
            'client_name': client_name, # 고객사 이름
            'waiting_for_confirm': False, # 의견 답장 줬는지 여부
            'waiting_begin_time': None # 의견 답장 준 시간
        }
        self.application.create_task(self.check_message(key))

    # 메시지 확인 후 처리 작업
    async def check_message(self, key):
        """ 고객기관 실무진이 민트 의견 메시지에 답장을 했는지 확인하는 함수.
            5분 간격으로 답장을 확인하고, 답장이 없을 시 메시지를 재전송한다.
            30분 경과 시 민트-고객사 그룹 채팅에 알림을 보낸다.
        Args:
            message_id ( INT ): 민트에서 발송한 의견 메시지 ID
        """
        message_info = self.tracked_messages[key]
        chat_id, stock_name = key
        while not message_info['confirmed']: # 참여내역 확인이 완료될 때까지 반복
            await asyncio.sleep(300)  # 5분마다 확인
            
            if not message_info['replied']: # 답장이 없는 경우
                # 답장 확인
                updates = await self.application.bot.get_updates(offset=-1, limit=1, timeout=60) # 가장 최근 업데이트 확인
                for update in updates:
                    if update.message and update.message.chat_id == chat_id:
                        if update.message.from_user.id not in self.mint_staff_ids: # 고객사 실무진인 경우
                            message_info['replied'] = True
                            message_info['waiting_for_confirm'] = True # 답장 왔음. 참여내역 확인 대기
                            message_info['waiting_begin_time'] = asyncio.get_event_loop().time()
                            waiting_message = f"{message_info['client_name']}가 {stock_name} 의견 메시지에 답장했습니다. 참여내역을 기다립니다."
                            logging.info(waiting_message)
                            await self.application.bot.send_message(chat_id=self.mint_group_chat_id ,text=waiting_message)
                
                # 첫 의견 메시지 전송 시간에서부터 15분 경과한 경우, 긴급 알림 전송
                if asyncio.get_event_loop().time() - message_info['start_time'] > 900:
                    await self.send_alert(key)
                    return
                
                # 5분 동안 답장이 없으면 메시지 재전송
                await self.resend_message(key)
            
            # 답장을 했지만 참여내역 확인이 완료되지 않은 경우
            elif message_info['replied'] and not message_info['confirmed']:
                # 참여내역 확인 대기
                if asyncio.get_event_loop().time() - message_info['participation_wait_start'] > 900:  # 15분 경과
                    await self.send_not_confirmed_alert(key)
                    return

    # 5분 간격으로 답장 없을 시 메시지 재전송하는 함수
    async def resend_message(self, key):
        """ 참여의견을 보내고 고객사로부터 답장이 안 오면 5분 간격으로 고객사에게 메시지를 재전송하는 함수.

        Args:
            key ( Tuple ): (민트-고객기관 채팅 ID, 종목명)
        """
        chat_id, stock_name = key
        message_info = self.tracked_messages[key]
        await self.application.bot.send_message(
            chat_id=chat_id,
            text=f"{stock_name}에 대한 참여의견을 확인해 주시길 바랍니다."
        )

    async def send_alert(self, key):
        """
        고객사가 첫 의견 메시지 전송 후 15분이 지나도 답장을 하지 않은 경우, 민트-고객사 그룹 채팅에 긴급 알림을 보낸다.

        Args: key ( Tuple ): (민트-고객기관 채팅 ID, 종목명)
        """
        chat_id, stock_name = key
        message_info = self.tracked_messages[key]
        alert_message = f"""
            -----------------------------긴급-------------------------
            {message_info['client_name']}이 {stock_name} 의견 메시지를 확인하지 않았습니다!
            ----------------------------------------------------------
            """
        await self.application.bot.send_message(
            chat_id=self.mint_group_chat_id,
            text=alert_message
        )
        logging.info(f"{message_info['client_name']}이 {stock_name} 의견 메시지를 확인하지 않아 긴급 알림을 보냈습니다.")

    # 고객사가 참여내역을 전송했는지 확인하는 함수
    async def confirm_participation(self, chat_id, stock_name):
        """고객사가 참여내역 확인을 환료했는지 확인하는 함수.

        Args:
            chat_id ( INT ): 민트-고객기관 그룹채팅 ID
            stock_name ( STRING ): 수요예측 종목명

        Returns:
            BOOL : 참여내역 전송 확인 여부
        """
        key = (chat_id, stock_name)
        if key in self.tracked_messages and self.tracked_messages[key]['waiting_for_confirm']:
            self.tracked_messages[key]['confirmed'] = True
            message = f"{self.tracked_messages[key]['client_name']}의 {stock_name} 참여내역을 확인했습니다."
            logging.info(message)
            await self.application.bot.send_message(
                chat_id=self.mint_group_chat_id,
                text=message)
            return True # 참여내역 전송 확인
        return False  # 해당 chat_id (고객기관)이 참여내역을 전송하지 않은 경우

    # 고객사가 참여내역을 전송하지 않은 경우 알림을 보내는 함수
    async def send_not_confirmed_alert(self, key):
        chat_id, stock_name = key
        message_info = self.tracked_messages[key]
        alert_message = f"""
            -----------------------------긴급-------------------------
            {message_info['client_name']}이 {stock_name} 참여내역을 전송하지 않았습니다!
            ----------------------------------------------------------
            """
        await self.application.bot.send_message(
            chat_id=self.mint_group_chat_id,
            text=alert_message
        )
        logging.info(f"{message_info['client_name']}이 {stock_name} 참여내역을 전송하지 않아 긴급 알림을 보냈습니다.")

    # 고객사가 참여의견 메시지에 답장을 했는지 확인하는 함수
    def is_waiting_for_confirm (self, chat_id, stock_name):
        """고객사가 참여의견 메시지에 답장을 한 뒤, 참여내역 확인 대기 상태인지 확인하는 함수.

        Args:
            chat_id ( INT ): 민트-고객기관 그룹채팅 ID
            stock_name ( STRING ): 수요예측 종목명

        Returns:
            BOOL : 참여내역 확인 대기 상태인지 여부 (고객사가 참여의견 메시지에 답장했는지 여부)
        """
        key = (chat_id, stock_name)
        return key in self.tracked_messages and self.tracked_messages[key]['waiting_for_confirm']