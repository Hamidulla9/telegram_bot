import asyncio
import logging
import os
import csv
from datetime import datetime
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, ReplyKeyboardMarkup, KeyboardButton
import pandas as pd
import pytz

# --- НАСТРОЙКИ ---
TOKEN = "8989441824:AAFQYciElk7wV-_XAr-Epg5fclvdxO6P3LY"
MY_ID = 8830345316
DB_FILE = "orders_database.csv"
UZ_TZ = pytz.timezone('Asia/Tashkent')

PRICES = {
    "Кафельный клей усиленный StartMix - 25kg": 30000,
    "Кафельный клей усиленный StartMix - 20kg": 27000,
    "Кафельный клей усиленный StrongHause - 25kg": 32000,
    "Кафельный клей усиленный Güçlü - 25kg": 32000,
    "Ротбанд - 25kg": 37000,
    "Фуга - 1kg": 12000,
    "Фуга - 2kg": 24000,
    "Фуга - 5kg": 45000,
    "Дождик 0.25 - 20kg": 44000,
    "Дождик 0.35 - 20kg": 44000,
    "Наливной пол - 25kg": 55000,
    "зажим-клин 1.2": 21000,
    "зажим-клин 1.4": 21000,
    "ПВА 900 - 800g": 29000,
    "грунтовка - 3L": 57000,
    "Азилитлюкс - 0.600г": 26000,
    "Окно очиститель - 0.600г": 20000,
    "Шпаклёвка 01 - 20k": 40000,
    "гидроизоляция - 4k": 365000,
    "Эмульсия - 25l": 320000,
    "Бетон контакт - 10k": 206000,
    "Клей для мозаики - 25k": 78000,
    "Кафельный клей усиленный SOLIDEX 707 - 25k": 37000,
    "Кафельный клей усиленный SOLIDEX 701 - 25k": 35000,
}

# --- FLASK SERVER ---
app = Flask('')


@app.route('/')
def home(): return "STARTMIX Bot is running!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    Thread(target=run_flask).start()


# --- КЛАВИАТУРЫ ---
main_menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🆕 Новый заказ")]], resize_keyboard=True)


class FullOrder(StatesGroup):
    waiting_company, waiting_inn, waiting_passport = State(), State(), State()
    waiting_geo, waiting_product, waiting_quantity = State(), State(), State()


bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---
def get_next_order_number():
    """CSV fayldan oxirgi raqamni o'qiydi va keyingisini qaytaradi"""
    if not os.path.exists(DB_FILE):
        return 1
    try:
        df = pd.read_csv(DB_FILE)
        if df.empty:
            return 1
        # Oxirgi qatordagi 'ID_Заказа' ustunidan raqamni ajratib olish (d0_5 -> 5)
        last_id = str(df.iloc[-1]['ID_Заказа'])
        num = int(last_id.split('_')[-1])
        return num + 1
    except:
        return 1


def save_to_db(data):
    file_exists = os.path.isfile(DB_FILE)
    with open(DB_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Дата", "ID_Заказа", "Агент", "Организация",
            "ИНН", "Товар", "Количество", "Цена_ед", "Итого", "Локация"
        ])
        if not file_exists: writer.writeheader()
        writer.writerow(data)


async def track_msg(message, state):
    data = await state.get_data()
    msg_ids = data.get("messages_to_delete", [])
    msg_ids.append(message.message_id)
    await state.update_data(messages_to_delete=msg_ids)


async def delete_history(state, chat_id):
    data = await state.get_data()
    for msg_id in data.get("messages_to_delete", []):
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass
    await state.update_data(messages_to_delete=[])


# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
@dp.message(F.text == "🆕 Новый заказ")
async def start_order(message: types.Message, state: FSMContext):
    await state.clear()
    kb = ReplyKeyboardBuilder()
    kb.add(KeyboardButton(text="🆕 Новый заказ"))
    if message.from_user.id == MY_ID:
        kb.add(KeyboardButton(text="📊 Выгрузить Excel"))
    kb.adjust(1)
    m = await message.answer("🚀 Введите название организации:", reply_markup=kb.as_markup(resize_keyboard=True))
    await track_msg(message, state);
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_company)


@dp.message(FullOrder.waiting_company)
async def get_company(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    await state.update_data(company=message.text)
    m = await message.answer("🔢 Введите ИНН (9 цифр):")
    await track_msg(m, state);
    await state.set_state(FullOrder.waiting_inn)


@dp.message(FullOrder.waiting_inn)
async def get_inn(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    if not message.text.isdigit() or len(message.text) != 9:
        m = await message.answer("⚠️ Ошибка! Введите 9 цифр:");
        await track_msg(m, state)
        return
    await state.update_data(inn=message.text)
    m = await message.answer("📸 Пришлите фото паспорта:");
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_passport)


@dp.message(FullOrder.waiting_passport, F.photo)
async def get_passport(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    await state.update_data(passport_id=message.photo[-1].file_id)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Отправить локацию", request_location=True)]],
                             resize_keyboard=True)
    m = await message.answer("📍 Отправьте локацию кнопкой:", reply_markup=kb);
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_geo)


@dp.message(FullOrder.waiting_geo, F.location)
async def get_geo(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    geo_url = f"https://www.google.com/maps?q={message.location.latitude},{message.location.longitude}"
    await state.update_data(geo_url=geo_url)
    builder = ReplyKeyboardBuilder()
    for p in PRICES.keys(): builder.add(KeyboardButton(text=p))
    builder.adjust(1)
    m = await message.answer("📦 Выберите товар:", reply_markup=builder.as_markup(resize_keyboard=True));
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_product)


@dp.message(FullOrder.waiting_product, F.text.in_(PRICES.keys()))
async def get_product(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    await state.update_data(product=message.text)
    m = await message.answer(f"Введите количество для {message.text}:", reply_markup=main_menu);
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_quantity)


@dp.message(FullOrder.waiting_quantity)
async def finish_order(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    await track_msg(message, state)

    data = await state.get_data()
    quantity = int(message.text)
    total = quantity * PRICES[data['product']]
    now_str = datetime.now(UZ_TZ).strftime("%d.%m.%Y %H:%M")

    # YANGILANGAN QISIM: Tartib raqamini olish
    current_num = get_next_order_number()

    order_info = {
        "Дата": now_str, "ID_Заказа": f"d0_{current_num}", "Агент": message.from_user.full_name,
        "Организация": data['company'], "ИНН": data['inn'], "Товар": data['product'],
        "Количество": quantity, "Цена_ед": PRICES[data['product']], "Итого": total, "Локация": data['geo_url']
    }
    save_to_db(order_info)

    report = (
        f"<b>STARTMIX | ЗАКАЗ #d0_{current_num}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Агент:</b> {message.from_user.full_name}\n"
        f"🏢 <b>Клиент:</b> {data['company']}\n"
        f"🆔 <b>ИНН:</b> <code>{data['inn']}</code>\n"
        f"📍 <a href='{data['geo_url']}'>Локация</a>\n"
        f"🕒 <b>Время:</b> {now_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {data['product']}\n"
        f"🔢 {quantity} шт. x {PRICES[data['product']]:,} сум\n"
        f"💰 <b>ИТОГО: {total:,} сум</b>".replace(',', ' ')
    )
    await delete_history(state, message.chat.id)
    await message.answer_photo(photo=data['passport_id'], caption=report, parse_mode="HTML", reply_markup=main_menu)
    try:
        await bot.send_photo(chat_id=MY_ID, photo=data['passport_id'], caption=f"🚀 КОПИЯ ДЛЯ ОФИСА\n\n{report}",
                             parse_mode="HTML")
    except:
        pass
    await state.clear()


@dp.message(Command("export"))
@dp.message(F.text == "📊 Выгрузить Excel")
async def export_handler(message: types.Message):
    if message.from_user.id != MY_ID: return
    if not os.path.exists(DB_FILE):
        await message.answer("❌ База пуста.");
        return
    df = pd.read_csv(DB_FILE)
    df.to_excel("report.xlsx", index=False)
    await message.answer_document(types.FSInputFile("report.xlsx"), caption="📊 Отчет STARTMIX")
    os.remove("report.xlsx")


async def main():
    logging.basicConfig(level=logging.INFO)
    keep_alive()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())