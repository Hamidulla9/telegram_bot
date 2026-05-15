import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# --- SOZLAMALAR ---
TOKEN = "8989441824:AAFieZm6Lpq3q3RG5mlBxEitwitfb7KQ094"
MY_ID = 8830345316

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

order_number = 96

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
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="🆕 Новый заказ")]], resize_keyboard=True)


def product_menu():
    builder = ReplyKeyboardBuilder()
    for product in PRICES.keys():
        builder.add(types.KeyboardButton(text=product))
    builder.adjust(2)
    builder.row(types.KeyboardButton(text="✅ Yakunlash (Tugatish)"))
    return builder.as_markup(resize_keyboard=True)


@dp.message(Command("start"))
@dp.message(F.text == "🆕 Новый заказ")
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
    phone = message.text.strip()
    if not phone.isdigit() or len(phone) != 9:
        return await message.answer("⚠️ Telefon raqami 9 ta raqam bo'lishi kerak!")
    await state.update_data(phone=phone)
    await message.answer("📸 Mijoz pasporti yoki shartnoma rasmini yuboring:")
    await state.set_state(FullOrder.waiting_passport)


@dp.message(FullOrder.waiting_passport, F.photo)
async def get_passport(message: types.Message, state: FSMContext):
    await state.update_data(passport_id=message.photo[-1].file_id)
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="📍 Lokatsiya yuborish", request_location=True)]], resize_keyboard=True)
    await message.answer("📍 Obyekt lokatsiyasini tugma orqali yuboring:", reply_markup=kb)
    await state.set_state(FullOrder.waiting_geo)


@dp.message(FullOrder.waiting_geo, F.location)
async def get_geo(message: types.Message, state: FSMContext):
    # TO'G'IRLANGAN HAVOLA:
    lat = message.location.latitude
    lon = message.location.longitude
    geo_url = f"https://www.google.com/maps?q={lat},{lon}"

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


@dp.message(FullOrder.waiting_product, F.text == "✅ Yakunlash (Tugatish)")
async def finish_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data['basket']: return await message.answer("⚠️ Savat bo'sh!")

    global order_number
    order_number += 1
    total_sum = 0
    items_text = ""
    for item in data['basket']:
        total_sum += item['qty'] * item['price']
        items_text += f"• {item['name']}\n  └ {item['qty']} шт. x {item['price']:,} = {item['qty'] * item['price']:,} сум\n"

    report = (
        f"✅ <b>Новый заказ #d0_{order_number}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Агент:</b> {message.from_user.full_name}\n"
        f"🏢 <b>Клиент:</b> {data['company']}\n"
        f"🆔 <b>ИНН:</b> <code>{data['inn']}</code>\n"
        f"📞 <b>Тел:</b> +998{data['phone']}\n"
        f"📍 <a href='{data['geo_url']}'>Lokatsiya (Google Maps)</a>\n"
        f"🕒 <b>Vaqt:</b> {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{items_text}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>ИТОГО: {total_sum:,} сум</b>\n"
        f"💳 <b>Ҳолати:</b> Кутилмоқда ⏳".replace(',', ' ')
    )

    await message.answer_photo(photo=data['passport_id'], caption=report, parse_mode="HTML", reply_markup=main_menu())

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ To'langan", callback_data=f"st_paid_{order_number}")
    builder.button(text="🔴 To'lanmagan", callback_data=f"st_unpaid_{order_number}")
    builder.adjust(2)

    await bot.send_photo(chat_id=MY_ID, photo=data['passport_id'], caption=f"🚀 <b>OFFICE COPY</b>\n\n{report}",
                         parse_mode="HTML", reply_markup=builder.as_markup())
    await state.clear()


@dp.callback_query(F.data.startswith("st_"))
async def update_payment_status(callback: types.CallbackQuery):
    status_type = callback.data.split("_")[1]
    payment_status = "✅ To'langan" if status_type == "paid" else "🔴 To'lanmagan"
    current_caption = callback.message.caption

    if "Ҳолати:" in current_caption:
        # To'g'ri split qilish uchun "Ҳолати:" so'zidan foydalanamiz
        base_text = current_caption.split("Ҳолати:")[0]
        new_caption = base_text + f"Ҳолати: {payment_status}"
    else:
        new_caption = current_caption + f"\n💳 Ҳолати: {payment_status}"

    await callback.message.edit_caption(caption=new_caption, parse_mode="HTML",
                                        reply_markup=callback.message.reply_markup)
    await callback.answer(f"Holat: {payment_status}")


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())