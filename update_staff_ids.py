import os
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

# 그룹 멤버의 user ID를 가져와서 .env 업데이트하는 함수
async def update_group_member_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("이 명령어는 그룹에서만 사용할 수 있습니다.")
        return

    try:
        member_ids = [str(member.user.id) for member in await chat.get_administrators()]
    except Exception as e:
        await update.message.reply_text(f"멤버 정보를 가져오는 데 실패했습니다: {str(e)}")
        return
    
    # .env 파일 업데이트
    update_env_file(member_ids)
    load_dotenv() # .env 파일 다시 로드
    mint_staff_ids = os.getenv('MINT_STAFF_IDS')

    await update.message.reply_text(f'''
                        실무진 ID가 업데이트되었습니다:
                        {mint_staff_ids}
                        ''')

# .env 파일 업데이트 함수
def update_env_file(member_ids):
    env_path = '.env'
    staff_ids_str = ','.join(member_ids)
    
    # 기존 .env 파일 내용 읽기
    if os.path.exists(env_path):
        with open(env_path, 'r') as file:
            lines = file.readlines()
    else:
        lines = []
    
    # MINT_STAFF_IDS 라인 찾기 또는 추가하기
    staff_ids_line = f"MINT_STAFF_IDS={staff_ids_str}\n"
    staff_ids_found = False
    
    for i, line in enumerate(lines):
        if line.startswith('MINT_STAFF_IDS='):
            lines[i] = staff_ids_line
            staff_ids_found = True
            break
    
    if not staff_ids_found:
        lines.append(staff_ids_line)
    
    # 업데이트된 내용을 .env 파일에 쓰기
    with open(env_path, 'w') as file:
        file.writelines(lines)

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