# Description: 봇의 메인 기능을 구현한 코드. 수요예측 의견을 전송하고 참여내역을 확인하는 기능을 구현함.
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
import aiofiles
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from message_tracker import MessageTracker

# 봇 토큰 로드
load_dotenv() # .env 파일에서 환경 변수를 로드하여 os.getenv()로 사용할 수 있게 함
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
EXCEL_FOLDER = 'excel_files'

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
    
    try:
        full_path = os.path.join(EXCEL_FOLDER, file_name)
        logger.info(f"{file_name} 파일을 읽습니다.")
        df1 = pd.read_excel(io=full_path, sheet_name='firstDay', usecols='A:I', index_col=0,
                            engine='openpyxl', dtype={'참여가격': str})
        df2 = pd.read_excel(io=full_path, sheet_name='lastDay', usecols='A:I', index_col=0,
                            engine='openpyxl', dtype={'참여가격': str})

        # '참여가격' 열의 형식을 조정
        for df in [df1, df2]:
            df['참여가격'] = df['참여가격'].apply(format_price)

        logger.info(f"{file_name} 파일을 성공적으로 읽었습니다.")
        return df1, df2
    except FileNotFoundError:
        logger.error(f"{file_name} 파일을 찾을 수 없습니다.")
        raise
    except PermissionError:
        logger.error(f"{file_name} 파일에 접근할 권한이 없습니다.")
        raise
    except Exception as e:
        logger.error(f"{file_name} 파일을 읽는 중 오류가 발생했습니다: {str(e)}")
        raise

# '참여가격' 열의 형식을 조정하는 함수
def format_price(price):
    """
    가격을 포맷팅하는 함수
    """
    try:
        # 문자열에서 쉼표 제거 후 숫자로 변환
        numeric_price = float(str(price).replace(',', ''))
        # 천 단위 쉼표를 포함한 문자열로 변환
        return f"{numeric_price:,.0f}"
    except ValueError:
        # 숫자로 변환할 수 없는 경우 원래 값을 반환
        return price

# config.json 파일 읽기 함수
async def read_config():
    try:
        async with aiofiles.open('config.json', mode='r') as f:
            content = await f.read()
            return json.loads(content)
    except FileNotFoundError:
        logger.error("config.json 파일을 찾을 수 없습니다.")
        raise
    except json.JSONDecodeError:
        logger.error("config.json 파일의 형식이 잘못되어 읽을 수 없습니다.")
        raise

# config.json 파일 업데이트 함수 추가
async def update_config(config):
    try:    
        async with aiofiles.open('config.json', mode='w') as f:
            await f.write(json.dumps(config, indent=4))
        logger.info("config.json 파일을 업데이트했습니다.")
    except IOError:
        logger.error("config.json 파일을 업데이트하는 중 오류가 발생했습니다.")
        raise


# 각 종목별 수요예측 프로세스를 관리하는 StockAdvisory 클래스
class StockAdvisory:
    def __init__(self, stock_name, df, sheet_name, message_tracker):
        self.stock_name = stock_name
        self.df = df
        self.sheet_name = sheet_name
        self.message_tracker = message_tracker


    async def process(self, application):
        """전체 수요예측 프로세스를 관리. 수요예측 의견을 전송하는 작업을 생성합니다. 발송 여부가 1인 기관들에 대해 메시지를 전송합니다. 

        Args:
            application ( Application ): 실행히고 있는 Application 객체
        """
        try:
            logger.info(f"\"{self.stock_name}\"의 수요예측 프로세스를 시작합니다.")
        
            comment = self.df['코멘트'].iloc[0] # 모든 행에 대해 동일한 코멘트 사용
            config = await read_config()
            mint_group_chat_id = config['mint_group_chat_id']

            # 발송 여부가 1인 고객기관들에 대해 각각 task 생성하여 비동기로 처리
            tasks = [self.process_each_client(index, row, application, mint_group_chat_id, comment) 
                     for index, row in self.df[self.df['발송'] == 1].iterrows()]
            results = await asyncio.gather(*tasks, return_exceptions=True)  # asyncio.gather()를 통해 모든 task를 병렬로 동시에 실행.
                                                                            # 예외를 개별적으로 처리.
                                                                            # results에는 각 task의 결과가 저장됨.

            failed_clients = []  # chatID를 찾지 못한 기관들을 저장할 리스트
            chat_ids_updated = False # 새로운 chatID를 업데이트했는지 여부를 알려주는 플래그

            # 발송이 필요한 고객사들의 인덱스와 process_each_client 함수의 결과를 짝지어 순회
            for index, result in zip(self.df[self.df['발송'] == 1].index, results): 
                if isinstance(result, Exception): # 결과가 예외 객체인 경우, 해당 고객사에 대한 처리가 실패했음을 의미
                    logger.error(f"\"{self.stock_name}\" 참여의견을 \"{index}\"에 보내는 중 오류 발생: {str(result)}")
                    failed_clients.append(index)
                elif result is not None:  # chat_id가 업데이트된 경우, DataFrame에 업데이트
                    self.df.at[index, 'chatID'] = result
                    chat_ids_updated = True

            # chatID을 못 찾았거나 다른 오류로 메시지 전송에 실패했을 때 민트 실무진 그룹채팅방에 알림
            if failed_clients:
                failed_message = "\n!!!!!!!!<긴급>!!!!!!!!\n".join([f" \"{self.stock_name}\" 참여의견을 \"{client}\"에 전송하지 못했습니다. 직접 보내주세요." for client in failed_clients])
                await application.bot.send_message(chat_id=mint_group_chat_id, text=failed_message)

            # Chat ID가 업데이트 되었으면 수정된 DataFrame을 엑셀 파일에 저장
            if chat_ids_updated:
                try:
                    save_dataframe_to_excel(self.df, f"{self.stock_name}.xlsx", self.sheet_name)
                except Exception as e:
                    logger.error(f"\"{self.stock_name}\"의 DataFrame을 엑셀 파일에 저장하는 중 오류 발생: {str(e)}")

            logger.info(f"\"{self.stock_name}\"의 수요예측 프로세스 완료.")

        except Exception as e:
            logger.error(f"\"{self.stock_name}\" 처리 중 예외 발생: {str(e)}")
            raise


    async def process_each_client(self, index, row, application, mint_group_chat_id, comment):
        """특정 종목에 대해 StockAdvisory 클래스를 생성했으므로 각 개별 클라이언트에 대한 처리를 담당합니다. chat ID를 확인하고, 메시지를 전송하는 등의 작업을 수행.

        Args:
            index ( DF의 인덱스): DataFrame의 인덱스. 여기서는 고개기관명
            row ( Series ): DataFrame의 특정 행 series
            application ( Application ): 실행하고 있는 Application 객체
            mint_group_chat_id ( int ): 민트 실무진 그룹 채팅방의 chat_id
            comment ( string ): 수요예측 의견의 코멘트
        
        Returns:
            int: chat_id를 찾은 경우 해당 chat_id, 찾지 못한 경우 None
        
        Raises:
            Exception: "민트-{index}" 그룹 Chat ID를 찾을 수 없는 경우 또는 메시지 전송 중 오류 발생 시
        """
        try:
            if pd.isna(row['chatID']):  # chatID 필드에 값이 없는 경우
                chat_id = await self.get_chat_id(application, index) # chat_id 가져오기
                if not chat_id:
                    raise Exception(f"\"민트-{index}\" 그룹 Chat ID를 찾을 수 없습니다.")
            else:
                chat_id = row['chatID']

            # DataFrame의 chatId 필드에 CHAT ID 있는 경우, 메시지 전송.
            # DataFrame에 없어서 Chat ID를 찾은 경우에는 즉시 사용하되, DataFrame 업데이트는 나중에 한 번에 수행 
            await self.send_advisory(application, chat_id, row, comment, index)
            await application.bot.send_message(chat_id=mint_group_chat_id, text=f"\"{index}\"에 \"{self.stock_name}\" 참여의견 메시지를 전송했습니다.")
        
            return chat_id if pd.isna(row['chatID']) else None
        
        except Exception as e:
            logger.error(f"\"{self.stock_name}\" 참여의견을 \"{index}\"에 보내는 중에 예기치 못한 오류 발생: {str(e)}")
            raise


    # 수요예측 의견 전송 함수
    async def send_advisory(self, application, chat_id, row, comment, client_name):
        """수요예측 참여의견 메시지를 전송합니다. 참여의견 전송 후 메시지 추적기를 통해 고객사의 답장 유무를 추적하고 참여내역을 확인합니다.

        Args:
            application ( Application ): 실행하고 있는 Application 객체
            chat_id (int): 메시지를 전송할 채팅방의 chat_id
            row (Series): 특정 고객기관의 수요예측 의견을 담고 있는 Series
            comment (string): 수요예측 의견의 코멘트
            client_name (string): 기관명
        """

        message = f"""
        {comment}
        ———————————————————————————————
        참여가격: {row['참여가격']}원
        참여수량: {row['참여수량']}
        확약여부: {row['확약여부']}
        """
        sent_message = await application.bot.send_message(chat_id=chat_id, text=message)
        await self.message_tracker.start_tracking(chat_id, sent_message.message_id, client_name, self.stock_name)


    # 새로운 그룹의 chat_id를 가져오는 함수
    async def get_chat_id(self, application, client_name):
        """새로운 그룹의 chat_id를 가져오고 config.json 파일에 저장합니다.

        Args:
            application (Application): Application 객체. 필요한지는 모르겠음.
            client_name (string): 찾고자 하는 그룹의 이름 (엑셀 파일에 적힌 기관명과 텔레그램 그룹 채팅방 이름이 일치해야 함)

        Raises:
            Exception: API 요청 실패 시 발생

        Returns:
            int: Chat ID 읽기 성공 시 해당 그룹의 chat_id, 실패 시 None
        """

        config = await read_config()
        group_name = f"민트-{client_name}"
        chat_id = None

        # config.json 파일에 이미 chat id가 있는 경우
        if group_name in config['client_group_chat_id']:
            logger.info(f"{group_name}의 Chat ID를 config.json 파일에서 찾았습니다.")
            return config['client_group_chat_id'][group_name]
        

        # config.json 파일에 chat ID가 없을 경우, Telegram Bot API를 이용해서 새 그룹의 chat_id 찾기
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
                                config['client_group_chat_id'][group_name] = chat_id
                                await update_config(config)
                                logger.info(f"새로운 그룹 Chat ID를 config.json 파일에 추가: {group_name} (ID: {chat_id})")
                                return chat_id
                            
            logger.error(f"{group_name}의 Chat ID를 찾을 수 없습니다.")
            return None

        except aiohttp.ClientError as e:
            logger.error(f"네트워크 오류 발생: {str(e)}")
            return None

        except Exception as e:
            logger.error(f"원인 모를 오류 발생: {str(e)}")
            return None

################ 여기까지 StockAdvisory 클래스 끝 ###################


# 엑셀 파일 업데이트 함수
def save_dataframe_to_excel(df, file_name, sheet_name):
    try:
        full_path = os.path.join(EXCEL_FOLDER, file_name)
        # 기존 엑셀 파일 로드
        book = load_workbook(full_path)
        
        # 해당 시트 선택 (없으면 새로 생성)
        if sheet_name in book.sheetnames:
            sheet = book[sheet_name]
        else:
            logger.error(f"{file_name} 파일에 {sheet_name} 시트가 없습니다.")
        
        # DataFrame에서 Chat ID 열만 추출
        chat_id_df = df[['chatID']]

        # Chat ID 열만 업데이트
        for r_idx, row in enumerate(dataframe_to_rows(chat_id_df, index=True, header=False), 2): # chat_id_df를 행 단위로 변환.
            for c_idx, value in enumerate(row[1:], 6): # ChatID는 6번째 열(F열)에 있음.
                if pd.notna(value): # 빈 셀이나 누락된 데이터는 무시.
                    sheet.cell(row=r_idx, column=c_idx, value=value)
        
        # 변경사항 저장
        try:
                book.save(full_path)
                logger.info(f"{file_name} 파일의 {sheet_name} 시트에서 Chat ID를 업데이트했습니다.")
        except PermissionError:
            logger.error(f"{file_name} 파일에 저장할 권한이 없습니다. 파일이 열려있지 않은지 확인하세요.")
        except IOError as e:
            logger.error(f"{file_name} 파일 저장 중 IO 오류 발생: {str(e)}")     
        
    
    except Exception as e:
        logger.error(f"{file_name} 파일을 업데이트하는 중 오류가 발생했습니다: {str(e)}")
        raise


async def participation_process(update: Update, stock_name: str, stock_advisory: StockAdvisory):
    """수요예측 참여내역을 확인하고 처리하는 함수. 참여내역은 텍스트, 이미지, 문서 형식으로 전송된다.

    Args:
        update (Update): 텔레그램 봇 업데이트 객체
        stock_name (str): 수요예측을 진행하는 주식 종목명
        stock_advisory (StockAdvisory): StockAdvisory 인스턴스

    Returns:
        Bool: 참여내역 확인 후 처리한 경우 True, 그렇지 않은 경우 False
    """
    message = update.message
    chat_id = message.chat_id

    while not stock_advisory.message_tracker.is_waiting_for_confirm(chat_id, stock_name):
        await asyncio.sleep(1)  # 1초마다 확인

    if message.document or message.photo or message.text:
        if await stock_advisory.message_tracker.confirm_participation(chat_id, stock_name):
            await update.message.reply_text(f"\"{stock_name}\" 수요예측 참여내역이 확인되었습니다. 감사합니다.")
            ######## 여기에 참여내역 처리 로직 추가 ########
            return True
    else:
        await update.message.reply_text(f"\"{stock_name}\"의 참여내역 형식이 옳지 않습니다. 확인을 위해 메시지를 다시 전송해주세요.")
    return False

# 종목 참여내역 통합 처리 함수
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = []
    for stock_advisory in active_stocks.values():
        task = asyncio.create_task(participation_process(update, stock_advisory.stock_name, stock_advisory))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)

    if any(results):
        # 하나 이상의 종목에 대해 참여내역이 확인된 경우
        pass
    elif not active_stocks:
        await update.message.reply_text("현재 진행 중인 수요예측이 없습니다.")
    else:
        await update.message.reply_text("모든 종목에 대해 참여내역 확인 준비가 되지 않았습니다. 잠시 후 다시 시도해 주세요.")


# main 함수
async def main():
    config = await read_config()
    
    # 봇 생성
    application = Application.builder().token(TOKEN).pool_timeout(60).connection_pool_size(8).build()
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_response))

    await application.initialize()
    await application.start()

    # 폴링을 별도의 태스크로 진행
    # (사용자 입력 처리, StockAdvisory 인스턴스 생성 및 처리, 메인 루프 실행 등의 작업들이 진행되는 동안에도 봇은 계속해서 새로운 메시지나 업데이트를 받을 수 있음)
    polling_task = asyncio.create_task(application.updater.start_polling(allowed_updates=Update.ALL_TYPES))

    global active_stocks
    active_stocks = {}
    message_tracker = MessageTracker(application)
    await message_tracker.initialize()
    await application.bot.send_message(chat_id=config['mint_group_chat_id'], text="프로그램이 시작되었습니다.")
    await asyncio.sleep(0.5)
    try:
        while True:
            # 사용자로부터 수요예측을 진행할 종목명을 입력받음
            stock_name = input("수요예측을 진행할 주식 종목명을 입력하세요 (종료하려면 'q' 입력): ")

            if stock_name.lower() == 'q':
                break

            sheet_name = input("수요예측 첫날이면 '1', 마지막날이면 '2'를 입력하세요: ").strip()
            
            if sheet_name not in ['1', '2']:
                logger.warning("잘못된 입력입니다. '1' 또는 '2'를 입력해주세요.")
                continue

            # '종목명.xlsx' 파일 읽기            
            file_name = f"{stock_name}.xlsx"
            try:
                df_first_day, df_last_day = read_advise_excel(file_name)
                df = df_first_day if sheet_name == '1' else df_last_day
                sheet_name = 'firstDay' if sheet_name == '1' else 'lastDay'
            except FileNotFoundError:
                print(f"{file_name} 파일이 존재하지 않습니다.")
                continue

            # StockAdvisory 인스턴스 생성 및 처리
            stock_advisory = StockAdvisory(stock_name, df, sheet_name, message_tracker)
            active_stocks[stock_name] = stock_advisory # 오늘 수요예측 하는 모든 종목의 StockAdvisory 인스턴스 저장
            try:
                await stock_advisory.process(application)
            except Exception as e:
                logger.error(f"{stock_name} 처리 중 오류 발생: {str(e)}")
            
            print(f"{stock_name}의 수요예측 참여의견 전송 작업이 완료되었습니다.")

            print("다음 종목의 수요예측 의견을 전송하려면 새로운 종목명을 입력하세요.")
            print("모든 처리를 마치고 프로그램을 종료하려면 'q'를 입력하세요.")

    finally:
        # 애플리케이션 종료
        await application.stop()

        # 폴링 중지
        if application.updater.running:
            await application.updater.stop()

        # 폴링 태스크가 완전히 종료될 때까지 대기
        if not polling_task.done():
            await polling_task

    print("프로그램을 종료합니다.")

if __name__ == "__main__":
    asyncio.run(main())