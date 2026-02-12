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
API_TOKEN = '7798122260:AAH0FlGe3cNKFyt5yJ-VHD1CaTR1NDRnoIs'
ADMIN_ID = [7951069138, 6713005636]

BTN_REG = "📝 Тіркелу / Өзгерту"
BTN_MARK = "✅ Мен осындамын!"
BTN_STATS = "📊 Менің сабаққа қатысуларым"
BTN_HELP = "❓ Көмек / Нұсқаулық"
BTN_TODAY = "📋 Бүгінгі тізім (Админ)"
BTN_REPORT = "📊 Есеп (Excel)"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- МӘЛІМЕТТЕР БАЗАСЫ ---
def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, full_name TEXT, student_group TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance 
                      (user_id INTEGER, date TEXT)''')
    conn.commit()
    conn.close()

# --- ВЕБ СЕРВЕР ---
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

# --- БОТ ЛОГИКАСЫ (HANDLER ORDER MATTERS) ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text=BTN_REG), types.KeyboardButton(text=BTN_MARK))
    builder.row(types.KeyboardButton(text=BTN_STATS), types.KeyboardButton(text=BTN_HELP))
    if message.from_user.id in ADMIN_ID:
        builder.row(types.KeyboardButton(text=BTN_TODAY))
        builder.row(types.KeyboardButton(text=BTN_REPORT))

    await message.answer(
        "👋 Сәлем! Төмендегі батырмаларды қолданыңыз немесе тіркелу үшін `Тегі Аты | Топ` форматында хабарлама жіберіңіз.",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# 1. АДМИН БАТЫРМАЛАРЫ (БІРІНШІ ТҰРУЫ КЕРЕК)
@dp.message(F.text == BTN_TODAY)
async def admin_today(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return await message.answer("❌ Бұл функция тек админдерге қолжетімді.")
    
    today = datetime.now().strftime("%d.%m.%Y")
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.full_name, u.student_group 
        FROM attendance a 
        JOIN users u ON a.user_id = u.user_id 
        WHERE a.date = ?
    """, (today,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer(f"📅 {today}: Әзірге ешкім белгіленбеді.")
    else:
        text = f"📅 **Бүгін келгендер ({today}):**\n\n"
        for i, row in enumerate(rows, 1):
            text += f"{i}. {row[0]} ({row[1]})\n"
        await message.answer(text)

@dp.message(F.text == BTN_REPORT)
async def send_report(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return await message.answer("❌ Рұқсат жоқ.")
    
    conn = sqlite3.connect('attendance.db')
    query = """
        SELECT u.full_name as 'Студент', u.student_group as 'Топ', a.date as 'Күні' 
        FROM attendance a 
        JOIN users u ON a.user_id = u.user_id 
        ORDER BY a.date ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return await message.answer("📊 Есеп бос.")
    
    path = "report.xlsx"
    df.to_excel(path, index=False)
    await message.answer_document(types.FSInputFile(path), caption="📅 Барлық уақыттағы толық есеп")

# 2. ПАЙДАЛАНУШЫ БАТЫРМАЛАРЫ
@dp.message(F.text == BTN_HELP)
async def help_info(message: types.Message):
    await message.answer("📖 **Үлгі:** `Тегі Аты | Топ` \n\nМысалы: `Ахметов Әли | ПО-2401` \nБелгілену үшін 'Мен осындамын!' батырмасын басыңыз.")

@dp.message(F.text == BTN_REG)
async def register_info(message: types.Message):
    await message.answer("📝 Тіркелу үшін мына үлгіде жазыңыз:\n\n`Тегі Аты | Топ` \n(Ортасында '|' сызығы болуы міндетті)")

@dp.message(F.text == BTN_MARK)
async def mark_attendance(message: types.Message):
    user_id = message.from_user.id
    today = datetime.now().strftime("%d.%m.%Y")
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT full_name FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    
    if user is None:
        conn.close()
        return await message.answer("❌ Сіз базада жоқсыз! Алдымен тіркеліңіз.")
    
    cursor.execute("SELECT * FROM attendance WHERE user_id=? AND date=?", (user_id, today))
    if cursor.fetchone():
        conn.close()
        return await message.answer("⚠️ Бүгін белгіленіп қойғансыз!")
    
    cursor.execute("INSERT INTO attendance VALUES (?, ?)", (user_id, today))
    conn.commit()
    conn.close()
    await message.answer(f"📍 {user[0]}, қатысуыңыз тіркелді! ✅")

@dp.message(F.text == BTN_STATS)
async def show_stats(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT full_name FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return await message.answer("❌ Алдымен тіркеліңіз!")
    
    cursor.execute("SELECT date FROM attendance WHERE user_id=? ORDER BY date DESC", (user_id,))
    history = cursor.fetchall()
    conn.close()
    history_text = "\n".join([f"✅ {h[0]}" for h in history]) if history else "Белгіленулер жоқ."
    await message.answer(f"📊 **{user[0]}** қатысу тарихы:\n\n{history_text}")

# 3. ТІРКЕЛУ ЖӘНЕ КЕЗ КЕЛГЕН МӘТІНДІ ӨҢДЕУ (ЕҢ СОҢЫНДА)
@dp.message(F.text)
async def handle_registration(message: types.Message):
    if "|" in message.text:
        data = message.text.split('|')
        if len(data) < 2:
            return await message.answer("❌ **Қате формат!** \n\nҮлгі: `Тегі Аты | Топ`")
        
        full_name = data[0].strip()
        group_name = data[1].strip()

        if len(full_name.split()) < 2:
            return await message.answer("❌ **Қате!** Тегіңіз бен атыңызды толық жазыңыз.")
        
        if not group_name:
            return await message.answer("❌ **Қате!** Топ атауын жазыңыз.")

        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (message.from_user.id, full_name, group_name))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Тіркелдіңіз: {full_name} ({group_name})")
    else:
        # Егер пайдаланушы батырма емес, кез келген басқа нәрсе жазса
        await message.answer(
            "❓ Түсінбедім. Егер тіркелгіңіз келсе, мына үлгіде жазыңыз:\n\n`Тегі Аты | Топ` \n\nМысалы: `Амангелді Айбек | ПО-2303`"
        )

async def main():
    init_db()
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

