import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, ReplyKeyboardMarkup, KeyboardButton

# --- НАСТРОЙКИ (ОБЯЗАТЕЛЬНО ЗАПОЛНИТЬ) ---
TOKEN = "8989441824:AAFQYciElk7wV-_XAr-Epg5fclvdxO6P3LY"
MY_ID = 8830345316  # Вставьте сюда ваш ID, полученный от @userinfobot

# Прайс-лист STARTMIX (можно менять названия и цены)
PRICES = {
    "Кафельный клей усиленный  StartMix - 25kg": 30000,
    "Кафельный клей усиленный StartMix - 20kg": 27000,
    "Кафельный клей усиленный StrongHause - 25kg": 32000,
    "Кафельный клей усиленный  Güçlü - 25kg": 32000,
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
    "Кафельный клей усиленный  SOLIDEX 701 - 25k": 35000,
}

# Номер последнего заказа (будет расти во время работы бота)
order_number = 0

# --- КЛАВИАТУРЫ ---
# Маленькая, компактная кнопка для старта
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🆕 Новый заказ")]],
    resize_keyboard=True
)


# --- СОСТОЯНИЯ (FSM) ---
class FullOrder(StatesGroup):
    waiting_company = State()
    waiting_inn = State()
    waiting_passport = State()
    waiting_geo = State()
    waiting_product = State()
    waiting_quantity = State()


# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def track_msg(message: types.Message, state: FSMContext):
    """Запоминает ID сообщения для последующего удаления"""
    data = await state.get_data()
    msg_ids = data.get("messages_to_delete", [])
    msg_ids.append(message.message_id)
    await state.update_data(messages_to_delete=msg_ids)


async def delete_history(state: FSMContext, chat_id: int):
    """Удаляет все сообщения, ID которых были записаны"""
    data = await state.get_data()
    msg_ids = data.get("messages_to_delete", [])
    for msg_id in msg_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass
    await state.update_data(messages_to_delete=[])


# --- ОБРАБОТЧИКИ (ХЕНДЛЕРЫ) ---




@dp.message(FullOrder.waiting_company)
async def get_company(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    await state.update_data(company=message.text)
    m = await message.answer("🔢 Введите ИНН компании (9 цифр):")
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_inn)


@dp.message(FullOrder.waiting_inn)
async def get_inn(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    inn = message.text.strip()
    if not inn.isdigit() or len(inn) != 9:
        m = await message.answer("⚠️ Ошибка! ИНН должен содержать ровно 9 цифр. Попробуйте снова:")
        await track_msg(m, state)
        return
    await state.update_data(inn=inn)
    m = await message.answer("📸 Пришлите фото паспорта или тех. паспорта клиента:")
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_passport)


@dp.message(FullOrder.waiting_passport, F.photo)
async def get_passport(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    await state.update_data(passport_id=message.photo[-1].file_id)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Отправить геолокацию", request_location=True)]],
        resize_keyboard=True
    )
    m = await message.answer("📍 Пожалуйста, отправьте локацию объекта кнопкой ниже:", reply_markup=kb)
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_geo)


@dp.message(FullOrder.waiting_geo, F.location)
async def get_geo(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    geo_url = f"https://www.google.com/maps?q={message.location.latitude},{message.location.longitude}"
    await state.update_data(geo_url=geo_url)

    builder = ReplyKeyboardBuilder()
    for product in PRICES.keys():
        builder.add(KeyboardButton(text=product))
    builder.adjust(2)

    m = await message.answer("📦 Выберите товар из прайс-листа:", reply_markup=builder.as_markup(resize_keyboard=True))
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_product)


@dp.message(FullOrder.waiting_product, F.text.in_(PRICES.keys()))
async def get_product(message: types.Message, state: FSMContext):
    await track_msg(message, state)
    await state.update_data(product=message.text)
    m = await message.answer(f"Вы выбрали {message.text}. Введите количество (цифрами):", reply_markup=main_menu)
    await track_msg(m, state)
    await state.set_state(FullOrder.waiting_quantity)


@dp.message(FullOrder.waiting_quantity)
async def finish_order(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return
    await track_msg(message, state)

    global order_number
    order_number += 1
    data = await state.get_data()

    quantity = int(message.text)
    product_name = data['product']
    price_per_unit = PRICES[product_name]
    total_sum = quantity * price_per_unit

    agent_name = message.from_user.full_name
    order_time = datetime.now().strftime("%H:%M %d.%m.%Y")

    # Формируем отчет (как в Sales Doctor, но лучше)
    report = (
        f"<b>STARTMIX | СИСТЕМА ЗАКАЗОВ</b>\n"
        f"✅ <b>Новый заказ #d0_{order_number}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Агент:</b> {agent_name}\n"
        f"🏢 <b>Клиент:</b> {data['company']}\n"
        f"🆔 <b>ИНН:</b> <code>{data['inn']}</code>\n"
        f"📍 <a href='{data['geo_url']}'>Локация объекта</a>\n"
        f"🕒 <b>Время:</b> {order_time}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {product_name}\n"
        f"🔢 {quantity} шт. x {price_per_unit:,} сум\n"
        f"💰 <b>ИТОГО: {total_sum:,} сум</b>".replace(',', ' ')
    )

    # Очищаем историю чата
    await delete_history(state, message.chat.id)

    # Отправляем результат агенту
    await message.answer_photo(
        photo=data['passport_id'],
        caption=report,
        parse_mode="HTML",
        reply_markup=main_menu
    )

    # Отправляем копию вам (админу)
    try:
        await bot.send_photo(
            chat_id=MY_ID,
            photo=data['passport_id'],
            caption=f"🚀 <b>КОПИЯ ЗАКАЗА ДЛЯ ОФИСА</b>\n\n{report}",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить копию админу: {e}")

    await state.clear()


# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
