import together
import requests
import calendar
import datetime
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from note import send_calendar, generate_calendar, handle_date_selection, change_month, add_note, save_note, delete_note, view_notes, load_notes, save_notes, notes

# API-ключи
API_KEY = "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"
MODEL = "google/gemini-2.0-flash-001"
TELEGRAM_TOKEN = "7718727642:AAHLO2l4lZT1QSkG9_GgfhhDs5OptcciW6o"
OPENWEATHER_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzM5MzU1OTk3LCJpYXQiOjE3MzkzNTU2OTcsImp0aSI6IjY0MDViY2Q1MTQ0ZTQxN2U5NWZkNjE3ZDA4MTc2OGIzIiwidXNlcl9pZCI6MTQxfQ.uQ_y5UdYDSRC4J3NxhpfAHVDVE9ZMwGWDQk0GnvI2Rw"

client = together.Client(api_key=API_KEY)

# Словарь для хранения истории диалогов пользователей
conversation_context = {}

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Заметки", callback_data="notes")],
        [InlineKeyboardButton("❓ Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton("🧠 Личный психолог", callback_data="psychologist")],
        [InlineKeyboardButton("📆 Составить расписание", callback_data="schedule")],
        [InlineKeyboardButton("⏰ Установить напоминание", callback_data="set_reminder")],
    ]
    return InlineKeyboardMarkup(keyboard)



async def start(update: Update, context: CallbackContext):
    """Приветственное сообщение"""
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_main_menu())


async def button_click(update: Update, context: CallbackContext):
    """Обработка кнопок"""
    query = update.callback_query
    await query.answer()

    if query.data == "notes":
        today = datetime.date.today()
        await send_calendar(update, context, today.year, today.month)
    elif query.data == "ask_question":
        await query.message.reply_text("Введите ваш вопрос:")
        context.user_data["waiting_for_question"] = True
    elif query.data == "psychologist":
        await query.message.reply_text("🧠 Привет! Я твой личный психолог. Напиши, что тебя беспокоит.")
        context.user_data["waiting_for_psychologist"] = True
    elif query.data == "schedule":
        await generate_schedule(update, context)
    elif query.data == "set_reminder":
        await query.message.reply_text("Введите задачу для напоминания:")
        context.user_data["waiting_for_reminder_task"] = True

def split_message(text, max_length=4096):
    """Разбивает длинный текст на части, чтобы он не превышал лимит Telegram"""
    parts = []
    while len(text) > max_length:
        split_index = text[:max_length].rfind(". ")  # Разбиваем по предложениям
        if split_index == -1:
            split_index = max_length
        parts.append(text[:split_index + 1])
        text = text[split_index + 1:]
    parts.append(text)
    return parts

def remove_markdown(text):
    """Удаляет Markdown-форматирование (**жирный**, *курсив*, _подчеркнутый_, `код`)"""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Убираем жирный текст
    text = re.sub(r"\*(.*?)\*", r"\1", text)  # Убираем курсив
    text = re.sub(r"`(.*?)`", r"\1", text)  # Убираем моноширинный текст
    text = re.sub(r"_(.*?)_", r"\1", text)  # Убираем подчёркивание
    return text

async def handle_message(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений (включая ответы для психолога и диалог с ИИ)"""
    user_message = update.message.text.strip()
    chat_id = update.message.chat_id

    # Команда выхода из диалога с ИИ
    if user_message.lower() == "/exit":
        context.user_data["waiting_for_psychologist"] = False
        context.user_data["waiting_for_question"] = False  # Завершаем диалог с ИИ
        context.user_data.pop("question_history", None)  # Очищаем историю диалога
        await update.message.reply_text(remove_markdown("🛑 Диалог завершен. Чем еще могу помочь?"), reply_markup=get_main_menu())
        return

    # Обработка учебных вопросов (поддержка диалога с ИИ)
    if context.user_data.get("waiting_for_question"):
        question_history = context.user_data.get("question_history", [])
        question_history.append({"role": "user", "content": user_message})

        try:
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": MODEL,
                "messages": [{"role": "system",
                              "content": "Ты — интеллектуальный помощник, отвечающий на вопросы пользователей."}] + question_history,
                "stream": False
            }

            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
            response_json = response.json()
            bot_reply = response_json.get("choices", [{}])[0].get("message", {}).get("content", "Не удалось получить ответ.")

            # Убираем Markdown-разметку
            bot_reply = remove_markdown(bot_reply)

            # Разбиваем длинное сообщение на части и отправляем их по очереди
            for part in split_message(bot_reply):
                await update.message.reply_text(part)

            # Сохраняем историю диалога
            question_history.append({"role": "assistant", "content": bot_reply})
            context.user_data["question_history"] = question_history

        except Exception as e:
            await update.message.reply_text(remove_markdown(f"Ошибка: {str(e)}"))
        return

    # Начало нового диалога с ИИ
    if user_message.lower() == "задать вопрос":
        context.user_data["waiting_for_question"] = True
        context.user_data["question_history"] = []  # Очищаем историю перед новым вопросом
        await update.message.reply_text(remove_markdown("📝 Задайте ваш вопрос:"))
        return

    # Остальной функционал остается без изменений:

    # Обработка заметок
    if context.user_data.get("waiting_for_note"):
        context.user_data["waiting_for_note"] = False
        await save_note(update, context)
        return

    # Обработка планирования расписания
    if context.user_data.get("waiting_for_schedule_answers"):
        context.user_data["waiting_for_schedule_answers"] = False
        user_notes = context.user_data.get("schedule_notes", [])

        try:
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "Ты — умный помощник, который помогает людям планировать день."},
                    {"role": "user",
                     "content": f"Вот мои дела: {', '.join(user_notes)}. Я предпочитаю этот порядок: {user_message}. "
                                "Составь мне расписание, чтобы всё успеть и провести день продуктивно. Дай полезные советы."}
                ],
                "stream": False
            }

            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
            response_json = response.json()
            schedule = response_json.get("choices", [{}])[0].get("message", {}).get("content",
                                                                                    "Не удалось составить расписание.")

        except Exception as e:
            schedule = f"Ошибка: {str(e)}"

        await update.message.reply_text(remove_markdown(f"📅 Ваше расписание на сегодня:\n\n{schedule}"), reply_markup=get_main_menu())
        return

    # Обработка общения с психологом (сохранение истории)
    if context.user_data.get("waiting_for_psychologist", False):
        bot_reply = get_psychologist_response(user_message, chat_id)
        await update.message.reply_text(remove_markdown(bot_reply))
        return

    # Обработка напоминаний (ввод задачи)
    if context.user_data.get("waiting_for_reminder_task"):
        context.user_data["waiting_for_reminder_task"] = False
        context.user_data["reminder_task"] = user_message
        await update.message.reply_text(remove_markdown("Введите время напоминания в минутах:"))
        context.user_data["waiting_for_reminder_time"] = True
        return

    # Обработка напоминаний (ввод времени)
    if context.user_data.get("waiting_for_reminder_time"):
        context.user_data["waiting_for_reminder_time"] = False
        try:
            delay_minutes = int(user_message)
            task = context.user_data.get("reminder_task", "Напоминание")
            context.job_queue.run_once(send_reminder, delay_minutes * 60, chat_id=chat_id, data=task)
            await update.message.reply_text(remove_markdown(f"⏰ Напоминание установлено! Я напомню вам через {delay_minutes} минут."))
        except ValueError:
            await update.message.reply_text(remove_markdown("Пожалуйста, введите корректное число минут."))
        return

    await update.message.reply_text(remove_markdown("Я не понял ваш запрос. Используйте кнопки."), reply_markup=get_main_menu())


async def send_reminder(context: CallbackContext):
    """Отправляет напоминание пользователю"""
    job = context.job
    await context.bot.send_message(job.chat_id, text=f"⏰ Напоминание: {job.data}")

conversation_context = {}  # Храним историю общения с психологом

async def handle_manual_command(update: Update, context: CallbackContext, command_type: str):
    """Обрабатывает команды /ask и /psychologist"""
    if command_type == "ask_question":
        await update.message.reply_text("Введите ваш вопрос:")
        context.user_data["waiting_for_question"] = True
    elif command_type == "psychologist":
        await update.message.reply_text("🧠 Привет! Я твой личный психолог. Напиши, что тебя беспокоит.")
        context.user_data["waiting_for_psychologist"] = True

async def handle_reminder_command(update: Update, context: CallbackContext):
    """Обрабатывает команду /reminder"""
    await update.message.reply_text("Введите задачу для напоминания:")
    context.user_data["waiting_for_reminder_task"] = True


def get_psychologist_response(user_input, chat_id):
    """Личный психолог. Отвечает на вопросы с учетом истории диалога."""

    # Если нет истории сообщений, создаем новую
    if chat_id not in conversation_context:
        conversation_context[chat_id] = []

    # Добавляем сообщение пользователя в историю
    conversation_context[chat_id].append({"role": "user", "content": user_input})

    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": MODEL,
            "messages": [
                {"role": "system",
                 "content": "Ты — дружелюбный психолог, помогающий людям решать проблемы. Отвечай с заботой и пониманием."},
                *conversation_context[chat_id],  # Передаем историю общения
            ],
            "stream": False
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response_json = response.json()

        bot_reply = response_json.get("choices", [{}])[0].get("message", {}).get("content", "Не удалось получить ответ.")

        # Добавляем ответ психолога в историю
        conversation_context[chat_id].append({"role": "assistant", "content": bot_reply})

        return bot_reply

    except Exception as e:
        print(f"Ошибка в get_psychologist_response: {e}")
        return "❌ Произошла ошибка при обработке запроса. Попробуйте позже!"

async def generate_schedule(update: Update, context: CallbackContext):
    """Начинает процесс составления расписания, анализируя заметки"""
    user = update.effective_user  # Получаем пользователя универсально
    user_id = user.id if user else None  # Проверяем, что пользователь существует

    if not user_id:
        await update.message.reply_text("Не удалось определить пользователя.")
        return

    today = datetime.date.today().strftime("%Y-%m-%d")

    # Получаем заметки пользователя на сегодня
    user_notes = [note['note'] for note in notes.get(today, []) if note['user_id'] == user_id]

    if not user_notes:
        await update.effective_message.reply_text(
            "Сегодня у вас нет записанных дел. Добавьте заметки и попробуйте снова.",
            reply_markup=get_main_menu()
        )
        return

    # Сохраняем список заметок в context.user_data
    context.user_data["schedule_notes"] = user_notes
    context.user_data["waiting_for_schedule_answers"] = True  # Включаем режим ожидания ответов

    # Отправляем первый вопрос пользователю
    await update.effective_message.reply_text(
        "Я вижу, у вас на сегодня такие задачи:\n\n" + "\n".join(user_notes) +
        "\n\nКакой порядок выполнения вам удобен? Укажите время, если это необходимо."
    )

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработка команд через /
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("notes", lambda u, c: send_calendar(u, c, datetime.date.today().year, datetime.date.today().month)))
    application.add_handler(CommandHandler("ask_question", lambda u, c: handle_manual_command(u, c, "ask_question")))
    application.add_handler(CommandHandler("psychologist", lambda u, c: handle_manual_command(u, c, "psychologist")))
    application.add_handler(CommandHandler("schedule", generate_schedule))
    application.add_handler(CommandHandler("set_reminder", handle_reminder_command))

    # Обработка кнопок
    application.add_handler(CallbackQueryHandler(button_click, pattern="^(notes|ask_question|psychologist|schedule|set_reminder)$"))
    application.add_handler(CallbackQueryHandler(handle_date_selection, pattern="^date_"))
    application.add_handler(CallbackQueryHandler(change_month, pattern="^change_month_"))
    application.add_handler(CallbackQueryHandler(add_note, pattern="^add_note$"))
    application.add_handler(CallbackQueryHandler(view_notes, pattern="^view_notes$"))
    application.add_handler(CallbackQueryHandler(delete_note, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(generate_schedule, pattern="^schedule$"))

    # Обработка текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    application.run_polling()




if __name__ == "__main__":
    main()