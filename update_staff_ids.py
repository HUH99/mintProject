# 코드 다시 체크해야함
# 실무진 ID를 업데이트하는 봇 코드. 
# 실무진 ID를 업데이트하려면 그룹에서 /update_staff_ids 명령어를 사용하면 됨.

import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

# 환경 변수 로드
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# 그룹 멤버의 user ID를 가져오는 함수
async def get_group_member_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = await context.bot.get_chat(update.effective_chat.id)
    members = await chat.get_administrators()
    member_ids = [str(member.user.id) for member in members]
    
    # .env 파일 업데이트
    update_env_file(member_ids)
    
    await update.message.reply_text("실무진 ID가 업데이트되었습니다.")

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
    
    # OUR_STAFF_IDS 라인 찾기 또는 추가하기
    staff_ids_line = f"OUR_STAFF_IDS={staff_ids_str}\n"
    staff_ids_found = False
    
    for i, line in enumerate(lines):
        if line.startswith('OUR_STAFF_IDS='):
            lines[i] = staff_ids_line
            staff_ids_found = True
            break
    
    if not staff_ids_found:
        lines.append(staff_ids_line)
    
    # 업데이트된 내용을 .env 파일에 쓰기
    with open(env_path, 'w') as file:
        file.writelines(lines)

# 메인 함수
async def main():
    application = Application.builder().token(TOKEN).build()
    
    # /update_staff_ids 명령어 핸들러 추가
    application.add_handler(CommandHandler("update_staff_ids", get_group_member_ids))
    
    # 봇 실행
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("봇이 실행 중입니다. 그룹에서 /update_staff_ids 명령어를 사용하여 실무진 ID를 업데이트하세요.")
    print("종료하려면 Ctrl+C를 누르세요.")
    
    # 봇을 계속 실행 상태로 유지
    await application.updater.stop_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())