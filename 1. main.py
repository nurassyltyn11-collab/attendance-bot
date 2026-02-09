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
BTN_STATS = "👤 Менің профилім"
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
                      (user_id INTEGER, date TEXT, time TEXT)''')
    conn.commit()
    conn.close()

# --- ВЕБ СЕРВЕР (Render үшін) ---
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

# --- БОТ ЛОГИКАСЫ ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text=BTN_REG), types.KeyboardButton(text=BTN_MARK))
    builder.row(types.KeyboardButton(text=BTN_STATS), types.KeyboardButton(text=BTN_HELP))
    
    if message.from_user.id in ADMIN_ID:
        builder.row(types.KeyboardButton(text=BTN_TODAY))
        builder.row(types.KeyboardButton(text=BTN_REPORT))

    await message.answer(
        f"👋 Сәлем, {message.from_user.first_name}!\n\n🏫 **Attendance System**-ге қош келдіңіз. Бұл жерде сабаққа қатысуыңызды белгілей аласыз.",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == BTN_HELP)
async def help_info(message: types.Message):
    await message.answer(
        "📖 **Ботты қолдану ережесі:**\n\n"
        "1. **Тіркелу:** `Тегі Аты | Топ` форматында жазыңыз.\n"
        "2. **Белгілену:** Күнделікті сабаққа келгенде 'Мен осындамын' батырмасын басыңыз.\n"
        "3. **Профиль:** Қатысу статистикасын көре аласыз."
    )

@dp.message(F.text == BTN_REG)
async def register_info(message: types.Message):
    await message.answer("📝 Тіркелу үшін мына үлгіде хабарлама жіберіңіз:\n\n`Амангелді Айбек | ПО-2303` \n\n⚠️ *Ескерту: Тегіңіз бен атыңызды толық жазыңыз!*")

@dp.message(lambda message: "|" in (message.text or ""))
async def process_registration(message: types.Message):
    data = message.text.split('|')
    
    # ТЕКСЕРУ (VALIDATION)
    if len(data) < 2:
        return await message.answer("❌ Қате формат! '|' таңбасын қолданыңыз.")
    
    full_name = data[0].strip()
    group_name = data[1].strip()

    # Есім мен тектің бар-жоғын тексеру (минимум 2 сөз)
    if len(full_name.split()) < 2:
        return await message.answer("❌ Қате! Тегіңіз бен атыңызды толық жазыңыз (мысалы: `Амангелді Айбек`).")

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (message.from_user.id, full_name, group_name))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Мәліметтер сәтті сақталды:\n👤 **{full_name}**\n👥 Топ: **{group_name}**")

@dp.message(F.text == BTN_MARK)
async def mark_attendance(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now()
    today = now.strftime("%d.%m.%Y")
    current_time = now.strftime("%H:%M:%S")
    
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT full_name FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return await message.answer("❌ Сіз базада жоқсыз! Алдымен тіркеліңіз.")
    
    cursor.execute("SELECT * FROM attendance WHERE user_id=? AND date=?", (user_id, today))
    if cursor.fetchone():
        conn.close()
        return await message.answer("⚠️ Сіз бүгін белгіленіп қойғансыз!")
    
    cursor.execute("INSERT INTO attendance VALUES (?, ?, ?)", (user_id, today, current_time))
    conn.commit()
    conn.close()
    await message.answer(f"📍 {user[0]}, қатысуыңыз сәтті тіркелді!\n⏰ Уақыты: {current_time} ✅")

@dp.message(F.text == BTN_STATS)
async def show_stats(message: types.Message):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Соңғы 5 келу уақытын алу
    cursor.execute("SELECT date, time FROM attendance WHERE user_id=? ORDER BY date DESC LIMIT 5", (message.from_user.id,))
    history = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE user_id=?", (message.from_user.id,))
    count = cursor.fetchone()[0]
    conn.close()

    history_text = "\n".join([f"🔹 {h[0]} ({h[1]})" for h in history])
    if not history_text: history_text = "Деректер жоқ"

    await message.answer(
        f"📊 **Сіздің статистикаңыз:**\n\n"
        f"✅ Жалпы қатысу саны: {count}\n"
        f"📅 **Соңғы белгіленулер:**\n{history_text}"
    )

@dp.message(F.text == BTN_TODAY)
async def admin_today(message: types.Message):
    if message.from_user.id not in ADMIN_ID: return
    
    today = datetime.now().strftime("%d.%m.%Y")
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT users.full_name, attendance.time FROM attendance 
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
            text += f"{i}. {row[0]} ({row[1]})\n"
        await message.answer(text)

@dp.message(F.text == BTN_REPORT)
async def send_report(message: types.Message):
    if message.from_user.id not in ADMIN_ID: return
    
    conn = sqlite3.connect('attendance.db')
    query = """
        SELECT users.full_name as 'Студент', 
               users.student_group as 'Топ', 
               attendance.date as 'Күні',
               attendance.time as 'Уақыты'
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
    await message.answer_document(types.FSInputFile(path), caption="📅 Барлық уақыттағы есеп")

async def main():
    init_db()
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())


