import together
import requests
import calendar
import datetime
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext


NOTES_FILE = "notes.json"

def load_notes():
    """Загружает заметки из JSON-файла"""
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_notes():
    """Сохраняет заметки в JSON-файл"""
    with open(NOTES_FILE, "w", encoding="utf-8") as file:
        json.dump(notes, file, ensure_ascii=False, indent=4)

notes = load_notes()

async def send_calendar(update: Update, context: CallbackContext, year, month):
    """Отправка календаря"""
    user_id = None
    if update.message:
        user_id = update.message.from_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id

    keyboard = generate_calendar(year, month, user_id)
    query = update.callback_query
    if query:
        await query.edit_message_text(f"📅 Выберите дату ({month}/{year}):", reply_markup=keyboard)
    else:
        await update.message.reply_text(f"📅 Выберите дату ({month}/{year}):", reply_markup=keyboard)


def generate_calendar(year, month, user_id):
    """Создание календаря с возможностью листания"""
    cal = calendar.monthcalendar(year, month)
    keyboard = []

    # Получаем сегодняшнюю дату
    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")  # Форматируем в "YYYY-MM-DD"

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                text = f"**{day}**" if date_str in notes and any(
                    note['user_id'] == user_id for note in notes[date_str]) else str(day)

                # Выделяем сегодняшний день
                button_style = {"text": text, "callback_data": f"date_{date_str}"}
                if date_str == today_str:
                    button_style["text"] = f"📅 {day}"  # Добавляем эмодзи для сегодняшнего дня
                    # Можно изменить цвет, если используешь кастомные кнопки (например, для BotFather)
                    # button_style["text"] = f"<b>{day}</b>"  # Или просто выделить жирным шрифтом

                row.append(InlineKeyboardButton(**button_style))
        keyboard.append(row)

    # Листание месяцев (исправлено)
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)

    keyboard.append([
        InlineKeyboardButton("⬅️ Назад", callback_data=f"change_month_{prev_year}_{prev_month}"),
        InlineKeyboardButton("➡️ Вперед", callback_data=f"change_month_{next_year}_{next_month}")
    ])

    return InlineKeyboardMarkup(keyboard)



async def handle_date_selection(update: Update, context: CallbackContext):
    """Обработка выбора даты"""
    query = update.callback_query
    await query.answer()

    date = query.data.split("_")[1]
    context.user_data["selected_date"] = date

    keyboard = [
        [InlineKeyboardButton("📝 Добавить заметку", callback_data="add_note")],
        [InlineKeyboardButton("📖 Посмотреть заметки", callback_data="view_notes")],
        [InlineKeyboardButton("🔙 Назад", callback_data="notes")]
    ]
    await query.edit_message_text(f"📅 Вы выбрали {date}. Выберите действие:",
                                  reply_markup=InlineKeyboardMarkup(keyboard))


async def change_month(update: Update, context: CallbackContext):
    """Обработка смены месяца"""
    query = update.callback_query
    await query.answer()

    print(f"DEBUG: Получены данные: {query.data}")  # Логируем данные в консоль

    try:
        parts = query.data.split("_")  # Разбиваем строку
        if len(parts) == 4 and parts[0] == "change" and parts[1] == "month":
            year, month = int(parts[2]), int(parts[3])  # Теперь корректно разбираем
            print(f"DEBUG: Переключаемся на {year}-{month}")
            await send_calendar(update, context, year, month)
        else:
            raise ValueError(f"Неверный формат change_month: {query.data}")
    except Exception as e:
        print(f"Ошибка: {e}")  # Логируем ошибку в консоль
        await query.message.reply_text("Ошибка при обработке смены месяца. Попробуйте снова.")


async def add_note(update: Update, context: CallbackContext):
    """Запрос на ввод заметки"""
    query = update.callback_query
    await query.answer()

    date = context.user_data.get("selected_date")
    if not date:
        await query.message.reply_text("Ошибка: дата не выбрана.")
        return

    await query.message.reply_text(f"✏️ Напишите заметку для {date}:")
    context.user_data["waiting_for_note"] = True

async def save_note(update: Update, context: CallbackContext):
    """Сохранение заметки"""
    from main import get_main_menu
    note = update.message.text
    date = context.user_data.get("selected_date")
    user_id = update.message.from_user.id  # Получаем идентификатор пользователя

    if not date:
        await update.message.reply_text("Ошибка: дата не выбрана.")
        return

    # Если для этой даты еще нет заметок, создаем список заметок
    if date not in notes:
        notes[date] = []

    # Добавляем заметку с привязкой к user_id
    notes[date].append({"user_id": user_id, "note": note})

    # Сохраняем заметки в JSON-файл
    save_notes()

    await update.message.reply_text(f"✅ Заметка добавлена на {date}!", reply_markup=get_main_menu())

async def delete_note(update: Update, context: CallbackContext):
    """Удаление заметки"""
    from main import get_main_menu
    query = update.callback_query
    await query.answer()

    # Получаем индекс заметки для удаления
    index = int(query.data.split("_")[1]) - 1  # Индексы начинаются с 1, поэтому вычитаем 1
    date = context.user_data.get("selected_date")
    user_id = query.from_user.id

    if date and date in notes:
        # Удаляем заметку по индексу
        user_notes = [note for note in notes[date] if note['user_id'] == user_id]
        if 0 <= index < len(user_notes):
            # Удаляем заметку
            del notes[date][notes[date].index(user_notes[index])]

            # Сохраняем изменения
            save_notes()

            await query.edit_message_text(f"✅ Заметка удалена с {date}.", reply_markup=get_main_menu())
        else:
            await query.edit_message_text("❌ Ошибка: заметка не найдена.", reply_markup=get_main_menu())
    else:
        await query.edit_message_text("❌ Ошибка: не удалось найти заметку.", reply_markup=get_main_menu())


async def view_notes(update: Update, context: CallbackContext):
    """Просмотр заметок на выбранную дату"""
    from main import get_main_menu
    user_id = None
    if update.message:
        user_id = update.message.from_user.id
        message = update.message
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        message = update.callback_query.message  # Используем сообщение из callback_query

    date = context.user_data.get("selected_date")
    if not date:
        await message.reply_text("Ошибка: дата не выбрана.")
        return

    # Проверяем наличие заметок для этого пользователя
    if date in notes:
        user_notes = [note for note in notes[date] if note['user_id'] == user_id]
        if user_notes:
            notes_text = "\n".join([f"{idx+1}. {note['note']}" for idx, note in enumerate(user_notes)])
            keyboard = [
                [InlineKeyboardButton(f"❌ Удалить {idx+1}", callback_data=f"delete_{idx+1}") for idx in range(len(user_notes))],
                [InlineKeyboardButton("🔙 Назад", callback_data="notes")]
            ]
            await message.reply_text(f"📖 Заметки на {date}:\n{notes_text}", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await message.reply_text(f"📖 На {date} нет ваших заметок.", reply_markup=get_main_menu())
    else:
        await message.reply_text(f"📖 На {date} нет заметок.", reply_markup=get_main_menu())
