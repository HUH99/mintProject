# 각 종목에 대한 수요예측 의견을 기록한 엑셀 파일 읽기
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
import os
import logging
import asyncio

# 봇 토큰 로드
load_dotenv() # .env 파일에서 환경 변수를 로드하여 os.getenv()로 사용할 수 있게 함
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TEST_CHAT_ID')

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 엑셀 파일 읽기 함수
def read_excel(file_name):
    # first day 시트를 데이터프레임으로 읽기
    df1 = pd.read_excel(io = file_name,
                        sheet_name = 'firstDay',
                        usecols= 'A:I',
                        index_col = 0,
                        skiprows = None)
    # last day 시트를 데이터프레임으로 읽기
    df2 = pd.read_excel(io = file_name,
                        sheet_name = 'lastDay',
                        usecols= 'A:I',
                        index_col = 0,
                        skiprows = None)
    # print(df1.head())
    # print(df2.head())
    return df1, df2

# 수요예측 의견 전송 함수
async def send_advisory(context, chat_id, row):
    # 보낼 메시지 구성
    message = f"""
    {row['코멘트']}
    참여가격: {row['참여가격']}
    참여수량: {row['참여수량']}
    확약여부: {row['확약여부']}
    """
    # 메시지 비동기 전송
    await context.bot.send_message(chat_id = chat_id, text = message)

# 자문의견 전송을 위한 작업 생성 함수
async def process_advisory(application, df):
    # 애플리케이션 컨텍스트 내에서 작업 수행
    async with application:
        for index, row in df.iterrows():
            if row['발송'] == 1:
                if pd.isna(row['chatID']): # chatID가 없는 경우 예외 처리
                    print(f"{index}의 chatID가 없습니다.")
                else:
                    await send_advisory(application, row['chatID'], row)

# main 함수
async def main():
    stocks = input("주식 종목명을 입력하세요: ")
    file_name = f"{stocks}.xlsx"

    # 엑셀 파일 읽기
    try:
        df_first_day, df_last_day = read_excel(file_name)
    except FileNotFoundError:
        print(f"{file_name} 파일이 존재하지 않습니다.")
        return

    # 텔레그램 봇 초기화
    application = Application.builder().token(TOKEN).build()

    # firstDay와 lastDay sheet 처리
    await process_advisory(application, df_first_day)
    # await process_advisory(application, df_last_day)

# 비동기 메인 함수 실행
if __name__ == "__main__":
    asyncio.run(main())
    Application.run_polling(allowed_updates = Update.ALL_TYPES)
    