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
ADMIN_ID = [7951069138, 6713005636]

BTN_REG = "📝 Тіркелу / Өзгерту"
BTN_MARK = "✅ Мен осындамын!"
BTN_STATS = "👤 Менің статым"
BTN_TODAY = "📋 Бүгінгі тізім (Админ)"
BTN_REPORT = "📊 Есеп (Excel)"

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

async def handle(request):
    return web.Response(text="Бот белсенді!")

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
    builder.row(types.KeyboardButton(text=BTN_REG), types.KeyboardButton(text=BTN_MARK))
    builder.row(types.KeyboardButton(text=BTN_STATS))
    
    if message.from_user.id == ADMIN_ID:
        builder.row(types.KeyboardButton(text=BTN_TODAY))
        builder.row(types.KeyboardButton(text=BTN_REPORT))

    await message.answer(
        "🏫 **Сабаққа қатысуды қадағалау жүйесі**\n\nТөмендегі батырмаларды қолданыңыз:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == BTN_REG)
async def register_info(message: types.Message):
    await message.answer("Тіркелу немесе деректі өзгерту үшін мына үлгіде жазыңыз:\n\n`Аты Жөні | Топ` \n\nМысалы: `Айбек Амангелді | ПО - 2303`")

@dp.message(lambda message: "|" in (message.text or ""))
async def process_registration(message: types.Message):
    data = message.text.split('|')
    if len(data) < 2: return
    name, group = data[0].strip(), data[1].strip()
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (message.from_user.id, name, group))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Мәліметтер сақталды: {name} ({group})")

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
    
    # Бүгін белгіленіп қойған ба?
    cursor.execute("SELECT * FROM attendance WHERE user_id=? AND date=?", (user_id, today))
    if cursor.fetchone():
        conn.close()
        return await message.answer("⚠️ Сіз бүгін белгіленіп қойғансыз!")
    
    cursor.execute("INSERT INTO attendance VALUES (?, ?)", (user_id, today))
    conn.commit()
    conn.close()
    await message.answer(f"📍 {user[0]}, қатысуыңыз сәтті белгіленді! ✅")

@dp.message(F.text == BTN_STATS)
async def show_stats(message: types.Message):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE user_id=?", (message.from_user.id,))
    count = cursor.fetchone()[0]
    conn.close()
    await message.answer(f"📊 Сіздің сабаққа қатысу саны: **{count}**")

@dp.message(F.text == BTN_TODAY)
async def admin_today(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    today = datetime.now().strftime("%d.%m.%Y")
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT users.full_name FROM attendance 
        JOIN users ON attendance.user_id = users.user_id 
        WHERE attendance.date = ?
    """, (today,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer(f"📅 {today}: Әзірге ешкім жоқ.")
    else:
        text = f"📅 **Бүгін келгендер ({today}):**\n\n"
        for i, row in enumerate(rows, 1):
            text += f"{i}. {row[0]}\n"
        await message.answer(text)

@dp.message(F.text == BTN_REPORT)
async def send_report(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('attendance.db')
    query = """
        SELECT users.full_name as 'Студент', 
               users.student_group as 'Топ', 
               attendance.date as 'Күні' 
        FROM attendance 
        JOIN users ON attendance.user_id = users.user_id
        ORDER BY attendance.date ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    if df.empty:
        return await message.answer("📊 Есеп бос.")
    path = "report.xlsx"
    df.to_excel(path, index=False)
    await message.answer_document(types.FSInputFile(path), caption="📅 Толық есеп")

async def main():
    init_db()
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())



