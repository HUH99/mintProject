# Description: 엑셀 파일을 읽어서 텔레그램 봇을 통해 메시지를 전송하는 함수.
# MAIN 함수
import pandas as pd
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from dotenv import load_dotenv
import os
import logging
import asyncio
from message_tracker import MessageTracker

# 봇 토큰 로드
load_dotenv() # .env 파일에서 환경 변수를 로드하여 os.getenv()로 사용할 수 있게 함
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 엑셀 파일 읽기 함수
def read_excel(file_name):
    df1 = pd.read_excel(io=file_name, sheet_name='firstDay', usecols='A:I', index_col=0)
    df2 = pd.read_excel(io=file_name, sheet_name='lastDay', usecols='A:I', index_col=0)
    return df1, df2

# 자문의견 전송을 위한 작업 생성 함수
async def process_advisory(application, df):
    comment = df['코멘트'].iloc[0]  # 모든 행에 대해 동일한 코멘트 사용
    async with application:
        for index, row in df.iterrows():
            if row['발송'] == 1:
                if pd.isna(row['chatID']):
                    print(f"{index}의 chatID가 없습니다.")
                else:
                    await send_advisory(application, row['chatID'], row, comment)
                    print(f"{index}의 수요예측 의견을 전송했습니다.")

# 수요예측 의견 전송 함수
async def send_advisory(context, chat_id, row, comment):
    message = f"""
    {comment}
    참여가격: {row['참여가격']}
    참여수량: {row['참여수량']}
    확약여부: {row['확약여부']}
    """
    sent_message = await context.bot.send_message(chat_id=chat_id, text=message)
    await tracker.start_tracking(chat_id, sent_message.message_id)

# 수신 메시지 처리 함수
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message.document:
        # PDF 파일 처리
        file = await context.bot.get_file(message.document.file_id)
        # PDF 파일 다운로드 및 OCR 처리 로직 구현
    elif message.photo:
        # 이미지 파일 처리
        file = await context.bot.get_file(message.photo[-1].file_id)
        # 이미지 파일 다운로드 및 OCR 처리 로직 구현
    elif message.text:
        # 텍스트 메시지 처리
        # 텍스트 분석 로직 구현
        return
    # 처리 결과에 따른 응답 로직 구현
    # await update.message.reply_text("수요예측 확인내역이 접수되었습니다.")

# main 함수
async def main():
    # 수요예측 주식 종목명 입력
    stocks = input("주식 종목명을 입력하세요: ")
    file_name = f"{stocks}.xlsx"

    # 해당 주식 수요예측 엑셀 파일 읽기
    try:
        df_first_day, df_last_day = read_excel(file_name)
    except FileNotFoundError:
        print(f"{file_name} 파일이 존재하지 않습니다.")
        return

    our_staff_ids = [int(id) for id in os.getenv('OUR_STAFF_IDS').split(',')]
    
    # 봇 생성
    application = Application.builder().token(TOKEN).build()

    # 메시지 추적기 생성
    global tracker
    tracker = MessageTracker(application, our_staff_ids)
    
    #메시지 처리를 위한 핸들러 추가
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_response))
    
    # 비동기로 자문 의견 처리 및 봇 실행
    async with application:
        await application.initialize()
        await process_advisory(application, df_first_day)
        await process_advisory(application, df_last_day)
        await application.start()
        await application.updater.start_polling()
        
        print("봇이 실행 중입니다. 종료하려면 Ctrl+C를 누르세요.")
        
        # 봇을 계속 실행 상태로 유지
        await application.updater.stop_polling()  # 봇이 종료될 때까지 대기

if __name__ == "__main__":
    asyncio.run(main())