import asyncio
import logging
import csv
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardMarkup, KeyboardButton

# --- НАСТРОЙКИ ---
TOKEN = "ВАШ_ТОКЕН_БОТА"
ADMIN_ID = 123456789  # ВАШ ТЕЛЕГРАМ ID

DB_ORDERS = "orders.csv"
DB_USERS = "users.csv"
DB_CLIENTS = "clients.csv"

# Прайс-лист STARTMIX (фиксированные цены)
PRODUCTS = {
    "Плиточный клей Standard": 25000,
    "Плиточный клей Premium": 45000,
    "Наливной пол": 38000,
    "Сатин гипс": 32000,
    "Декоративная штукатурка": 55000
}

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# Состояния
class RegState(StatesGroup): name = State(); role = State()


class OrderState(StatesGroup):
    inn = State()
    company = State()
    phone = State()
    choosing_product = State()
    entering_qty = State()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_user(user_id):
    if not os.path.exists(DB_USERS): return None
    with open(DB_USERS, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if int(row['id']) == user_id and row['status'] == 'active': return row
    return None


def check_inn_owner(inn):
    if not os.path.exists(DB_CLIENTS): return None
    with open(DB_CLIENTS, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['inn'] == inn:
                expiry = datetime.strptime(row['date'], "%Y-%m-%d") + timedelta(days=30)
                if datetime.now() < expiry: return row['agent_name']
    return None


def save_client(inn, agent_name):
    clients = []
    exists = False
    if os.path.exists(DB_CLIENTS):
        with open(DB_CLIENTS, 'r', encoding='utf-8') as f: clients = list(csv.DictReader(f))
    for c in clients:
        if c['inn'] == inn:
            c['date'] = datetime.now().strftime("%Y-%m-%d");
            c['agent_name'] = agent_name;
            exists = True
    if not exists: clients.append({"inn": inn, "agent_name": agent_name, "date": datetime.now().strftime("%Y-%m-%d")})
    with open(DB_CLIENTS, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=["inn", "agent_name", "date"]);
        w.writeheader();
        w.writerows(clients)


def log_order(data):
    exists = os.path.isfile(DB_ORDERS)
    with open(DB_ORDERS, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=["date", "id", "agent", "client", "phone", "items", "sum", "status"])
        if not exists: w.writeheader()
        w.writerow(data)


# --- РЕГИСТРАЦИЯ И СТАРТ ---
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if message.from_user.id == ADMIN_ID:
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="📊 Отчет за сегодня"), KeyboardButton(text="📅 Итоги месяца")],
            [KeyboardButton(text="💸 Должники"), KeyboardButton(text="👥 Управление штатом")]
        ], resize_keyboard=True)
        await message.answer("⭐️ Добро пожаловать, Директор STARTMIX!", reply_markup=kb)
    elif not user:
        await message.answer("Вы не зарегистрированы в STARTMIX. Введите ваше ФИО для заявки:")
        await state.set_state(RegState.name)
    else:
        btn = "🆕 Новый заказ" if user['role'] == 'agent' else "📦 Мои доставки"
        await message.answer(f"Приветствуем, {user['name']}!",
                             reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=btn)]],
                                                              resize_keyboard=True))


@dp.message(RegState.name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    kb = InlineKeyboardBuilder()
    kb.button(text="Агент", callback_data="role_agent")
    kb.button(text="Водитель", callback_data="role_driver")
    await message.answer("Выберите вашу роль:", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("role_"))
async def reg_role(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    data = await state.get_data()
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Одобрить", callback_data=f"approve_{callback.from_user.id}_{role}_{data['name']}")
    kb.button(text="❌ Отказать", callback_data=f"deny_{callback.from_user.id}")
    await bot.send_message(ADMIN_ID, f"👤 <b>Новая заявка</b>\nИмя: {data['name']}\nРоль: {role}", parse_mode="HTML",
                           reply_markup=kb.as_markup())
    await callback.message.edit_text("Заявка отправлена директору. Ожидайте подтверждения.")
    await state.clear()


# --- ЛОГИКА ЗАКАЗА (МУЛЬТИ-ТОВАР + ТЕЛЕФОН) ---
@dp.message(F.text == "🆕 Новый заказ")
async def start_order(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user or user['role'] != 'agent': return
    await message.answer("Введите ИНН организации (9 цифр):")
    await state.set_state(OrderState.inn)


@dp.message(OrderState.inn)
async def order_inn(message: types.Message, state: FSMContext):
    inn = message.text.strip()
    owner = check_inn_owner(inn)
    user = get_user(message.from_user.id)
    if owner and owner != user['name']:
        await message.answer(f"❌ Этот ИНН закреплен за: {owner}. Вы не можете создать заказ.")
        await state.clear()
        return
    await state.update_data(inn=inn)
    await message.answer("Введите название компании:")
    await state.set_state(OrderState.company)


@dp.message(OrderState.company)
async def order_company(message: types.Message, state: FSMContext):
    await state.update_data(company=message.text)
    await message.answer("📞 Введите номер телефона клиента (только 9 цифр):\nНапример: 901234567")
    await state.set_state(OrderState.phone)


@dp.message(OrderState.phone)
async def order_phone(message: types.Message, state: FSMContext):
    digits = message.text.strip()
    if not digits.isdigit() or len(digits) != 9:
        await message.answer("❌ Введите ровно 9 цифр номера!")
        return
    await state.update_data(phone="+998" + digits, cart=[])
    await show_cart_menu(message)


async def show_cart_menu(message: types.Message):
    kb = InlineKeyboardBuilder()
    for p in PRODUCTS: kb.button(text=f"{p} ({PRODUCTS[p]:,} сум)".replace(',', ' '), callback_data=f"add_{p}")
    kb.button(text="✅ ОФОРМИТЬ ЗАКАЗ", callback_data="cart_finish")
    kb.adjust(1)
    await message.answer("📦 Добавьте товары в корзину:", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("add_"))
async def cart_add(callback: types.CallbackQuery, state: FSMContext):
    prod = callback.data.replace("add_", "")
    await state.update_data(cur_p=prod)
    await callback.message.answer(f"Введите количество для {prod}:")
    await state.set_state(OrderState.entering_qty)


@dp.message(OrderState.entering_qty)
async def cart_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    qty = int(message.text)
    data = await state.get_data()
    cart = data.get('cart', [])
    cart.append(
        {"item": data['cur_p'], "qty": qty, "price": PRODUCTS[data['cur_p']], "sum": qty * PRODUCTS[data['cur_p']]})
    await state.update_data(cart=cart)
    await show_cart_menu(message)


@dp.callback_query(F.data == "cart_finish")
async def cart_done(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('cart'): return
    total = sum(i['sum'] for i in data['cart'])
    items_str = "\n".join([f"• {i['item']}: {i['qty']} шт." for i in data['cart']])
    save_client(data['inn'], get_user(callback.from_user.id)['name'])

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Оплачено", callback_data=f"adm_pay_{callback.from_user.id}")
    kb.button(text="🚛 В долг", callback_data=f"adm_debt_{callback.from_user.id}")
    kb.button(text="❌ Отмена", callback_data="adm_cancel")

    msg = (
        f"📋 <b>НОВЫЙ ЗАКАЗ</b>\nАгент: {get_user(callback.from_user.id)['name']}\nКлиент: {data['company']}\nТел: {data['phone']}\n"
        f"ИНН: {data['inn']}\n---\n{items_str}\n---\nИТОГО: <b>{total:,} сум</b>").replace(',', ' ')

    # Сохраняем черновик в БД со статусом "WAIT"
    log_order({"date": datetime.now().strftime("%d.%m.%Y"), "id": callback.from_user.id,
               "agent": get_user(callback.from_user.id)['name'],
               "client": data['company'], "phone": data['phone'], "items": items_str.replace('\n', '; '), "sum": total,
               "status": "WAIT"})

    await bot.send_message(ADMIN_ID, msg, parse_mode="HTML", reply_markup=kb.as_markup())
    await callback.message.answer("Заказ отправлен на проверку.")
    await state.clear()


# --- ПОДТВЕРЖДЕНИЕ И ЧЕК ---
@dp.callback_query(F.data.startswith("adm_pay_"))
async def admin_pay(callback: types.CallbackQuery):
    # Логика: находим последний заказ этого юзера и ставим "ОПЛАЧЕНО"
    # Формируем чек
    ticket = (f"🧾 <b>STARTMIX - ЭЛЕКТРОННЫЙ ЧЕК</b>\n--------------------------\n"
              f"Статус: ОПЛАЧЕНО ✅\nДата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\nБлагодарим за доверие!")
    await callback.message.answer(ticket, parse_mode="HTML")
    # Здесь также должна быть логика уведомления свободного водителя
    await callback.answer()


# --- ОТЧЕТЫ (2% ЗАРПЛАТА) ---
@dp.message(F.text == "📅 Итоги месяца")
async def report_month(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    prefix = datetime.now().strftime(".%m.%Y")
    total_s = 0;
    agents_stats = {}
    with open(DB_ORDERS, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if prefix in row['date'] and row['status'] in ['ОПЛАЧЕНО', 'ДОЛГ']:
                s = int(row['sum']);
                total_s += s
                agents_stats[row['agent']] = agents_stats.get(row['agent'], 0) + s

    res = f"🗓 <b>ИТОГИ ЗА МЕСЯЦ</b>\nОбщие продажи: {total_s:,} сум\n---\n<b>ЗАРПЛАТЫ (2%):</b>\n".replace(',', ' ')
    for a, s in agents_stats.items():
        res += f"• {a}: {(s * 0.02):,} сум (от {s:,} сум)\n".replace(',', ' ')
    await message.answer(res, parse_mode="HTML")


# --- ВОДИТЕЛЬ И ГЕО ---
@dp.message(F.location)
async def handle_geo(message: types.Message):
    user = get_user(message.from_user.id)
    if user and user['role'] == 'driver':
        await bot.send_message(ADMIN_ID, f"🚚 <b>ВОДИТЕЛЬ В ПУТИ: {user['name']}</b>", parse_mode="HTML")
        await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())