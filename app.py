# Description: 엑셀 파일을 읽어서 텔레그램 봇을 통해 메시지를 전송하는 함수.
# MAIN 함수
import json
import pandas as pd
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import os
import logging
import asyncio
import aiohttp
import requests
from openpyxl import load_workbook
from message_tracker import MessageTracker

# 봇 토큰 로드
load_dotenv() # .env 파일에서 환경 변수를 로드하여 os.getenv()로 사용할 수 있게 함
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 엑셀 파일 읽기 함수
def read_advise_excel(file_name):
    """수요예측 엑셀 파일의 두 개의 시트: 수요예측 첫날 의견과 마지막날 의견을 읽어서 data frame으로 반환합니다.
,
    Args:
        file_name ( .xlsx file ): 파일이름이 수요예측하는 종목 이름인 엑셀 파일 

    Returns:
        _type_: 첫날에 대한 dataframe과 마지막날에 대한 dataframe
    """
    df1 = pd.read_excel(io=file_name, sheet_name='firstDay', usecols='A:I', index_col=0)
    df2 = pd.read_excel(io=file_name, sheet_name='lastDay', usecols='A:I', index_col=0)
    return df1, df2

# 엑셀 파일 업데이트 함수
def save_dataframe_to_excel(df, file_name, sheet_name):
    try:
        # 기존 엑셀 파일 로드
        book = load_workbook(file_name)

        # 기존 시트 삭제 (있는 경우)
        if sheet_name in book.sheetnames:
            book.remove(book[sheet_name])
        
        # 새로운 시트 생성
        writer = pd.ExcelWriter(file_name, engine='openpyxl')
        writer.book = book

        # DataFrame을 새 시트에 저장
        df.to_excel(writer, sheet_name=sheet_name, index=True)

        # 변경사항 저장
        writer.save()
        print(f"{file_name}.xlsx 파일의 {sheet_name} 시트를 업데이트했습니다.")

    except Exception as e:
        print(f"엑셀 파일 저장 중 오류 발생: {str(e)}")


# config.json 파일 읽기 함수
def read_config():
    try:
        with open('config.json') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        logger.error("config.json 파일을 찾을 수 없습니다.")
        raise
    except json.JSONDecodeError:
        logger.error("config.json 파일의 형식이 잘못되어 읽을 수 없습니다.")
        raise

# config.json 파일 업데이트 함수 추가
def update_config(config):
    try:    
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        logger.info("config.json 파일을 업데이트했습니다.")
    except IOError:
        logger.error("config.json 파일을 업데이트하는 중 오류가 발생했습니다.")
        raise


# 각 종목별 수요예측 프로세스를 관리하는 StockAdvisory 클래스
class StockAdvisory:
    def __init__(self, stock_name, df, sheet_name):
        self.stock_name = stock_name
        self.df = df
        self.sheet_name = sheet_name
        self.message_tracker = None

    async def process(self, application):
        """수요예측 의견을 전송하는 작업을 생성합니다. 발송 여부가 1인 기관들에 대해 메시지를 전송합니다. chatID가 없는 기관들은 getChatId 함수를 통해 chatID를 가져옵니다.

        Args:
            application ( Application ): 실행히고 있는 Application 객체
        """

        self.message_tracker = MessageTracker(application)
        comment = self.df['코멘트'].iloc[0] # 모든 행에 대해 동일한 코멘트 사용
        config = read_config()
        mint_group_chat_id = config['mint_group_chat_id']
        
        failed_clients = []  # chatID를 찾지 못한 기관들을 저장할 리스트
        for index, row in self.df.iterrows():
            if row['발송'] == 1:
                if pd.isna(row['chatID']):  # chatID 필드에 값이 없는 경우
                    chat_id = await self.getChatId(application, index) # chat_id 가져오기
                    if chat_id: # chat_id를 찾은 경우
                        self.df.at[index, 'chatID'] = chat_id
                    else: # chat_id를 찾지 못한 경우
                        failed_clients.append(index)
                        continue
                
                try: # chatID가 있는 경우 메시지 전송 
                    await self.send_advisory(application, row['chatID'], row, comment, index)
                    logger.info(f"{index}에 {self.stock_name}에 대한 의견 메시지를 전송했습니다.")
                    await application.bot.send_message(chat_id=mint_group_chat_id, text=f"{index}에 {self.stock_name} 대한 의견 메시지를 전송했습니다.")
                except Exception as e:
                    logger.error(f"{index}에 {self.stock_name}에 대한 의견 메시지 전송 중 오류 발생: {str(e)}")
                    failed_clients.append(index)

        # chatID을 못 찾았거나 다른 오류로 메시지 전송에 실패했을 때 민트 실무진 그룹채팅방에 알림
        if failed_clients:
            failed_message = "!!!!!!!!!!\n".join([f"{client}의 {self.stock_name}에 대한 의견 메시지를 전송하지 못했습니다. 직접 보내주세요." for client in failed_clients])
            await application.bot.send_message(chat_id=mint_group_chat_id, text=failed_message)

        # 수정된 DataFrame을 엑셀 파일에 저장
        save_dataframe_to_excel(self.df, f"{self.stock_name}.xlsx", self.sheet_name)

    # 수요예측 의견 전송 함수
    async def send_advisory(self, application, chat_id, row, comment, client_name):
        """수요예측 의견 메시지를 전송합니다. 메시지 전송 후 메시지 추적기를 통해 참여내역을 확인합니다.

        Args:
            application ( Application ): 실행하고 있는 Application 객체
            chat_id (int): 메시지를 전송할 채팅방의 chat_id
            row (Series): 수요예측 의견을 담고 있는 Series
            comment (string): 수요예측 의견의 코멘트
            client_name (string): 기관명
            stock_name (string): 주식 종목명
        """

        message = f"""
        {comment}
        참여가격: {row['참여가격']}
        참여수량: {row['참여수량']}
        확약여부: {row['확약여부']}
        """
        sent_message = await application.bot.send_message(chat_id=chat_id, text=message)
        await self.message_tracker.start_tracking(chat_id, sent_message.message_id, client_name, self.stock_name)

    # 새로운 그룹의 chat_id를 가져오는 함수 (비동기 처리)
    async def getChatId(application, client_name):
        """새로운 그룹의 chat_id를 가져오고 config.json 파일에 저장합니다.

        Args:
            application (Application): Application 객체. 필요한지는 모르겠음.
            client_name (string): 찾고자 하는 그룹의 이름 (엑셀 파일에 적힌 기관명과 텔레그램 그룹 채팅방 이름이 일치해야 함)

        Raises:
            Exception: API 요청 실패 시 발생

        Returns:
            int: chat id 읽기 성공 시 해당 그룹의 chat_id, 실패 시 None
        """
        config = read_config()
        group_name = f"민트-{client_name}"

        # config.json 파일에 이미 chat_id 있는 경우
        if group_name in config['client_group_chat_id']:
            logger.info(f"{group_name}의 chat_id를 config.json 파일에서 찾았습니다.")
            return config['client_group_chat_id'][group_name]
        
        # 새 그룹의 chat_id 찾기 로직
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()

                    if not data.get("ok"):
                        logger.error(f"API 요청 실패: {data.get('description')}")
                        raise Exception(f"API 요청 실패: {data.get('description')}")
                    
                    for item in data.get("result", []):
                        message = item.get("message")
                        if message and "chat" in message:
                            chat = message["chat"]
                            if chat.get("type") in ["group", "supergroup"] and chat.get("title") == group_name:
                                chat_id = chat.get("id")

                    # chat_id를 찾은 경우
                    if chat_id: 
                        config['client_group_chat_id'][group_name] = chat_id
                        update_config(config)
                        logger.info(f"새로운 그룹 chat id를 config.json 파일에 추가: {group_name} (ID: {chat_id})")
                        return chat_id
                    # chat_id를 찾지 못한 경우
                    else:
                        logger.error(f"{group_name}의 chat_id를 찾을 수 없습니다.")
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"네트워크 오류 발생: {str(e)}")
            return None

        except Exception as e:
            logger.error(f"원인 모를 오류 발생: {str(e)}")
            return None
        
#### StockAdvisory 클래스 끝 ####


# 수신 메시지 처리 함수 (수요예측 참여내역 확인)
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message.document or message.photo or message.text:
        for stock_advisory in active_stocks.values():
            if await stock_advisory.message_tracker.confirm_participation(message.chat_id):
                await update.message.reply_text("수요예측 참여내역이 확인되었습니다. 감사합니다.")
                return


# main 함수
async def main():
    config = read_config()
    
    # 봇 생성
    application = Application.builder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_response))

    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    global active_stocks
    active_stocks = {}

    try:
        while True:
            stock_name = input("수요예측을 진행할 주식 종목명을 입력하세요 (종료하려면 'q' 입력): ")
            if stock_name.lower() == 'q':
                break

            sheet_name = input("수요예측 첫날이면 '1', 마지막날이면 '2'를 입력하세요: ")
            if sheet_name not in ['1', '2']:
                print("잘못된 입력입니다. '1' 또는 '2'를 입력해주세요.")
                continue

            file_name = f"{stock_name}.xlsx"
            try:
                df_first_day, df_last_day = read_advise_excel(file_name)
                df = df_first_day if sheet_name == '1' else df_last_day
                sheet_name = 'firstDay' if sheet_name == '1' else 'lastDay'
            except FileNotFoundError:
                print(f"{file_name} 파일이 존재하지 않습니다.")
                continue

            stock_advisory = StockAdvisory(stock_name, df, sheet_name)
            active_stocks[stock_name] = stock_advisory # 현재 활성화된 모든 종목의 StockAdvisory 인스턴스 저장
            asyncio.create_task(stock_advisory.process(application))

            print(f"{stock_name}의 수요예측 의견 전송 작업이 시작되었습니다.")
            print("다음 종목의 수요예측 의견을 전송하려면 새로운 종목명을 입력하세요.")
            print("모든 처리를 마치고 봇을 종료하려면 'q'를 입력하세요.")

    finally:
        await application.stop()
        await application.shutdown()

    print("프로그램을 종료합니다.")

if __name__ == "__main__":
    asyncio.run(main())