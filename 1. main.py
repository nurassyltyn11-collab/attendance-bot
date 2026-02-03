import os
import asyncio
import sqlite3
import logging
import pandas as pd
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiohttp import web

# --- БАПТАУЛАР ---
API_TOKEN = '7798122260:AAHpPh_J3OOgc0yY2f-6Wlbh0CNVgoTPZ9Q'
ADMIN_ID = 7951069138 

BTN_REG = "📝 Тіркелу"
BTN_MARK = "✅ Мен осындамын! (Белгілену)"
BTN_REPORT = "📊 Есепті жүктеу (Excel)"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, full_name TEXT, student_group TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance 
                      (user_id INTEGER, date TEXT)''')
    conn.commit()
    conn.close()

# Веб-сервер Render үшін
async def handle(request):
    return web.Response(text="Бот жұмыс істеп тұр!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text=BTN_REG))
    builder.row(types.KeyboardButton(text=BTN_MARK))
    if message.from_user.id == ADMIN_ID:
        builder.row(types.KeyboardButton(text=BTN_REPORT))

    await message.answer(
        f"👋 Сәлем!\nБот интернетте іске қосылды.",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == BTN_REG)
async def register_info(message: types.Message):
    await message.answer("Тіркелу үшін мына үлгіде жауап қайтар:\n\n**Аты Жөні | Топ**")

@dp.message(lambda message: "|" in message.text)
async def process_registration(message: types.Message):
    data = message.text.split('|')
    if len(data) < 2: return
    name, group = data[0].strip(), data[1].strip()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (message.from_user.id, name, group))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Тіркелдіңіз: {name}")

@dp.message(F.text == BTN_MARK)
async def mark_attendance(message: types.Message):
    user_id = message.from_user.id
    today = datetime.now().strftime("%d.%m.%Y")
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT full_name FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return await message.answer("❌ Алдымен тіркеліңіз!")
    
    cursor.execute("INSERT INTO attendance VALUES (?, ?)", (user_id, today))
    conn.commit()
    conn.close()
    await message.answer(f"📍 {user[0]}, қатысуыңыз сәтті белгіленді! ✅")

@dp.message(F.text == BTN_REPORT)
async def send_report(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('attendance.db')
    df = pd.read_sql_query("SELECT users.full_name, users.student_group, attendance.date FROM attendance JOIN users ON attendance.user_id = users.user_id", conn)
    conn.close()
    df.to_excel("report.xlsx", index=False)
    await message.answer_document(types.FSInputFile("report.xlsx"), caption="📅 Қатысу есебі")

async def main():
    init_db()
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
