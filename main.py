import asyncio
import logging
import os
import threading
from datetime import datetime
import pytz  # <--- Vaqt mintaqasi bilan ishlash uchun
from flask import Flask
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "STARTMIX Bot ishlamoqda!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- BOT SOZLAMALARI ---
TOKEN = "8989441824:AAEPUJd6Mww5lr4ICP56P73rOosY_wrjNec"
MY_ID = 8830345316

PRICES = {
    "Kafel yelimi StartMix (kuchaytirilgan) - 25kg": 30000,
    "Kafel yelimi StartMix (kuchaytirilgan) - 20kg": 27000,
    "Kafel yelimi StrongHause - 25kg": 32000,
    "Kafel yelimi Güçlü - 25kg": 32000,
    "Rotband - 25kg": 37000,
    "Fuga - 1kg": 12000,
    "Fuga - 2kg": 24000,
    "Fuga - 5kg": 45000,
    "Dojdik 0.25 - 20kg": 44000,
    "Dojdik 0.35 - 20kg": 44000,
    "Nalivnoy pol - 25kg": 55000,
    "Zajim-klin 1.2": 21000,
    "Zajim-klin 1.4": 21000,
    "PVA 900 - 800g": 29000,
    "Gruntovka - 3L": 57000,
    "Azilitlyuks - 0.600g": 26000,
    "Oyna tozalagich - 0.600g": 20000,
    "Shpaklyovka 01 - 20kg": 40000,
    "Gidroizolyatsiya - 4kg": 365000,
    "Emulsiya - 25l": 320000,
    "Beton kontakt - 10kg": 206000,
    "Mozaika yelimi - 25kg": 78000,
    "Kafel yelimi SOLIDEX 707 - 25kg": 37000,
    "Kafel yelimi SOLIDEX 701 - 25kg": 35000,
}

order_number = 1
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class FullOrder(StatesGroup):
    waiting_company = State()
    waiting_inn = State()
    waiting_phone = State()
    waiting_passport = State()
    waiting_geo = State()
    waiting_product = State()
    waiting_quantity = State()

def main_menu():
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="🆕 Yangi buyurtma")]], resize_keyboard=True)

def product_menu():
    builder = ReplyKeyboardBuilder()
    for product in PRICES.keys():
        builder.add(types.KeyboardButton(text=product))
    builder.adjust(2)
    builder.row(types.KeyboardButton(text="✅ Yakunlash"))
    return builder.as_markup(resize_keyboard=True)

# --- HANDLERLAR ---
@dp.message(Command("start"))
@dp.message(F.text == "🆕 Yangi buyurtma")
async def start_order(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(basket=[])
    await message.answer("🚀 Buyurtma berishni boshladik.\nTashkilot nomini kiriting:", reply_markup=main_menu())
    await state.set_state(FullOrder.waiting_company)

@dp.message(FullOrder.waiting_company)
async def get_company(message: types.Message, state: FSMContext):
    await state.update_data(company=message.text)
    await message.answer("🔢 Tashkilot INN raqamini kiriting (9 ta raqam):")
    await state.set_state(FullOrder.waiting_inn)

@dp.message(FullOrder.waiting_inn)
async def get_inn(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or len(message.text) != 9:
        return await message.answer("⚠️ Xato! INN 9 ta raqamdan iborat bo'lishi kerak:")
    await state.update_data(inn=message.text)
    await message.answer("📞 Mijoz telefon raqamini kiriting (9 ta raqam):")
    await state.set_state(FullOrder.waiting_phone)

@dp.message(FullOrder.waiting_phone)
async def get_phone(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or len(message.text) != 9:
        return await message.answer("⚠️ Telefon raqami 9 ta raqam bo'lishi kerak!")
    await state.update_data(phone=message.text)
    await message.answer("📸 Mijoz pasporti yoki shartnoma rasmini yuboring:")
    await state.set_state(FullOrder.waiting_passport)

@dp.message(FullOrder.waiting_passport, F.photo)
async def get_passport(message: types.Message, state: FSMContext):
    await state.update_data(passport_id=message.photo[-1].file_id)
    kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="📍 Lokatsiya yuborish", request_location=True)]], resize_keyboard=True)
    await message.answer("📍 Obyekt lokatsiyasini tugma orqali yuboring:", reply_markup=kb)
    await state.set_state(FullOrder.waiting_geo)

@dp.message(FullOrder.waiting_geo, F.location)
async def get_geo(message: types.Message, state: FSMContext):
    geo_url = f"https://www.google.com/maps?q={message.location.latitude},{message.location.longitude}"
    await state.update_data(geo_url=geo_url)
    await message.answer("📦 Tovarlarni tanlang:", reply_markup=product_menu())
    await state.set_state(FullOrder.waiting_product)

@dp.message(FullOrder.waiting_product, F.text.in_(PRICES.keys()))
async def get_product(message: types.Message, state: FSMContext):
    await state.update_data(current_product=message.text)
    await message.answer(f"{message.text} miqdorini kiriting:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(FullOrder.waiting_quantity)

@dp.message(FullOrder.waiting_quantity)
async def get_quantity(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("⚠️ Raqam kiriting!")
    data = await state.get_data()
    basket = data.get('basket', [])
    basket.append({'name': data['current_product'], 'qty': int(message.text), 'price': PRICES[data['current_product']]})
    await state.update_data(basket=basket)
    await message.answer("✅ Qo'shildi. Yana tovar qo'shasizmi?", reply_markup=product_menu())
    await state.set_state(FullOrder.waiting_product)

@dp.message(FullOrder.waiting_product, F.text == "✅ Yakunlash")
async def finish_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data['basket']: return await message.answer("⚠️ Savat bo'sh!")

    # --- VAQTNI TO'G'IRLASH ---
    tashkent_tz = pytz.timezone('Asia/Tashkent')
    current_time = datetime.now(tashkent_tz).strftime('%H:%M %d.%m.%Y')

    global order_number
    order_number += 1
    total_sum = 0
    items_text = ""
    for item in data['basket']:
        total_sum += item['qty'] * item['price']
        items_text += f"• {item['name']}\n  └ {item['qty']} dona x {item['price']:,} = {item['qty'] * item['price']:,} so'm\n"

    report = (
        f"✅ <b>Yangi buyurtma #d0_{order_number}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Agent:</b> {message.from_user.full_name}\n"
        f"🏢 <b>Mijoz:</b> {data['company']}\n"
        f"🆔 <b>INN:</b> <code>{data['inn']}</code>\n"
        f"📞 <b>Tel:</b> +998{data['phone']}\n"
        f"📍 <a href='{data['geo_url']}'>Lokatsiya (Google Maps)</a>\n"
        f"🕒 <b>Vaqt:</b> {current_time}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{items_text}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>JAMI: {total_sum:,} so'm</b>".replace(',', ' ')
    )

    await message.answer_photo(photo=data['passport_id'], caption=report, parse_mode="HTML", reply_markup=main_menu())
    await bot.send_photo(chat_id=MY_ID, photo=data['passport_id'], caption=f"🚀 <b>OFFICE COPY</b>\n\n{report}", parse_mode="HTML")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
