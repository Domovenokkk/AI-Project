from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
import json
from datetime import datetime
from pathlib import Path
import re

DATA_FILE = Path("finance_data.json")


def load_finance_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_finance_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_current_month():
    return datetime.now().strftime("%Y-%m")


def get_user_data(user_id: str, global_data: dict):
    current_month = datetime.now().strftime("%Y-%m")

    if user_id not in global_data:
        global_data[user_id] = {
            "current_month": current_month,
            "months": {},
            "expenses": {},
            "income": {}
        }

    user_data = global_data[user_id]

    # Автоматический сброс при смене месяца
    if user_data["current_month"] != current_month:
        # Сохраняем предыдущий месяц
        user_data["months"][user_data["current_month"]] = {
            "expenses": user_data.get("expenses", {}).copy(),
            "income": user_data.get("income", {}).copy()
        }
        # Сбрасываем текущие данные
        user_data["current_month"] = current_month
        user_data["expenses"] = {}
        user_data["income"] = {}

    return user_data


async def finance_menu(update: Update, context: CallbackContext):
    # Определяем откуда пришел запрос - из callback или команды
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        msg = query.message
    else:
        msg = update.message

    keyboard = [
        [InlineKeyboardButton("📈 Учет расходов", callback_data="track_expenses")],
        [InlineKeyboardButton("💵 Учет доходов", callback_data="track_income")],
        [InlineKeyboardButton("📊 Итоги за месяц", callback_data="monthly_summary")],
        [InlineKeyboardButton("💡 Советы по экономии", callback_data="saving_tips")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]

    # Если это команда, отправляем новое сообщение, если callback - редактируем существующее
    if update.callback_query:
        await msg.edit_text("💰 Финансовый помощник:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg.reply_text("💰 Финансовый помощник:", reply_markup=InlineKeyboardMarkup(keyboard))

async def track_expenses(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🍔 Еда", callback_data="expense_food")],
        [InlineKeyboardButton("🚕 Транспорт", callback_data="expense_transport")],
        [InlineKeyboardButton("🎉 Развлечения", callback_data="expense_entertainment")],
        [InlineKeyboardButton("📦 Другое", callback_data="expense_other")],
        [InlineKeyboardButton("🔙 Назад", callback_data="finance")]
    ]
    await query.edit_message_text("Выберите категорию расхода:", reply_markup=InlineKeyboardMarkup(keyboard))

async def track_income(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("💼 Зарплата", callback_data="income_salary")],
        [InlineKeyboardButton("📈 Доп. доход", callback_data="income_extra")],
        [InlineKeyboardButton("🎁 Другое", callback_data="income_other")],
        [InlineKeyboardButton("🔙 Назад", callback_data="finance")]
    ]
    await query.edit_message_text("Выберите категорию дохода:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_expense_category(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    category = query.data.split("_")[1]  # Получаем категорию из callback_data
    context.user_data["finance_state"] = {"waiting_for": "expense", "category": category}
    await query.edit_message_text(f"Введите сумму расхода для категории '{category}':")

async def handle_income_category(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    category = query.data.split("_")[1]  # Получаем категорию из callback_data
    context.user_data["finance_state"] = {"waiting_for": "income", "category": category}
    await query.edit_message_text(f"Введите сумму дохода для категории '{category}':")

async def handle_finance_input(update: Update, context: CallbackContext):
    if "finance_state" not in context.user_data:
        return False  # Пропускаем обработку, если не в режиме ввода финансовых данных

    finance_state = context.user_data["finance_state"]
    text = update.message.text.replace(',', '.').strip()

    try:
        if not re.match(r'^\d+([.]\d{1,2})?$', text):
            raise ValueError()

        amount = float(text)
        if amount <= 0:
            raise ValueError()

        user_id = str(update.message.from_user.id)
        all_data = load_finance_data()
        user_data = get_user_data(user_id, all_data)

        if finance_state["waiting_for"] == "expense":
            user_data["expenses"][finance_state["category"]] = user_data["expenses"].get(finance_state["category"], 0) + amount
            message = f"✅ Расход {amount:.2f}₽ в категории '{finance_state['category']}' добавлен!"
        else:
            user_data["income"][finance_state["category"]] = user_data["income"].get(finance_state["category"], 0) + amount
            message = f"✅ Доход {amount:.2f}₽ в категории '{finance_state['category']}' добавлен!"

        save_finance_data(all_data)
        del context.user_data["finance_state"]

        keyboard = [
            [InlineKeyboardButton("📥 Добавить еще", callback_data=f"track_{finance_state['waiting_for']}")],
            [InlineKeyboardButton("📊 Главное меню", callback_data="finance")]
        ]

        await update.message.reply_text(
            message + "\nВыберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return True

    except (ValueError, TypeError):
        await update.message.reply_text(
            "❌ Пожалуйста, введите положительное число\n"
            "Примеры: 1500, 99.95, 2500.50"
        )
        return True


async def monthly_summary(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    all_data = load_finance_data()
    user_data = get_user_data(user_id, all_data)

    current_month = user_data["current_month"]
    expenses = user_data["expenses"]
    income = user_data["income"]

    total_expenses = sum(expenses.values())
    total_income = sum(income.values())
    balance = total_income - total_expenses

    response = (
        f"📊 Отчет за {current_month}:\n\n"
        f"🟢 Доходы: {total_income}₽\n"
        f"🔴 Расходы: {total_expenses}₽\n"
        f"⚖️ Баланс: {balance}₽\n\n"
        "📈 Детализация расходов:\n"
    )

    for category, amount in expenses.items():
        response += f"• {category.capitalize()}: {amount}₽\n"

    await query.message.reply_text(response)