import logging
import requests
import asyncio
from telegram import Update, Bot
import telegram
from telegram.ext import Updater, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from bs4 import BeautifulSoup

# 봇 토큰 설
token = "7374592268:AAEBLlFP5LxAIFZRwLGor71KbbmfcshkMTU" 

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 고객사 그룹 채팅 ID 리스트
customer_groups = {
    'test': '-4204147973'
}

# updater
updater = Updater(token=token, use_context=True)
dispatcher = updater.dispatcher

# 공모주 수요 예측 의견 메시지 전송 함수
async def opinionMsg():
    bot = Bot(token)수
    await bot.send_message(chat_id = "-4204147973", text = "Hello, World!")

if __name__ == "__main__":
    asyncio.run(opinionMsg())


