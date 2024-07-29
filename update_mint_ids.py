# 민트 실무진 User ID 및 실무진 그룹 Chat ID config.json에 업데이트
import asyncio
import os
import json
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
import logging

# 환경 변수 로드
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# config.json 파일 읽기 함수
def read_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("config.json 파일을 찾을 수 없습니다.")
        return {}
    except json.JSONDecodeError:
        logger.error("config.json 파일의 형식이 잘못되었습니다.")
        return {}
    
# config.json 파일 업데이트 함수
def update_config(config):
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        logger.info("config.json 파일이 업데이트되었습니다.")
    except IOError:
        logger.error("config.json 파일을 업데이트하는 중 오류가 발생했습니다.")



# 그룹 멤버의 user ID를 가져와서 config.json 업데이트하는 함수
async def update_group_member_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("이 명령어는 그룹에서만 사용할 수 있습니다.")
        return

    try:
        member_ids = [member.user.id for member in await chat.get_administrators()]
    except Exception as e:
        await update.message.reply_text(f"멤버 정보를 가져오는 데 실패했습니다: {str(e)}")
        return
    
    # config.json 파일 업데이트
    config = read_config()
    config['mint_staff_ids'] = member_ids
    config['mint_group_chat_id'] = chat.id
    update_config(config)

    await update.message.reply_text(f'''
                        Mint Staff ID가 업데이트되었습니다:
                                    {member_ids}
                                    Mint Staff Group Chat ID도 업데이트되었습니다:
                                    {chat.id}
                        ''')


def main():
    # 애플리케이션 빌드
    application = Application.builder().token(TOKEN).build()
    
    # /update_staff_ids 명령어 핸들러 추가
    application.add_handler(CommandHandler("update_staff_ids", update_group_member_ids))
    
    print("봇이 실행 중입니다. 그룹에서 /update_staff_ids 명령어를 사용하여 실무진 ID를 업데이트하세요.")
    print("종료하려면 Ctrl+C를 누르세요.")
    
    # 봇 실행
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()