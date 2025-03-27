import requests
import datetime
import re
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from note import handle_important_tasks, complete_task, load_completed_tasks, save_completed_tasks
from note import send_calendar, generate_calendar, handle_date_selection, change_month, add_note, save_note, delete_note, view_notes, load_notes, save_notes, notes, handle_main_menu, handle_category_selection
from API import API_KEY, WEATHER_API_KEY, MODEL, TELEGRAM_TOKEN, STABILITY_API_KEY, STABILITY_API_URL, client
from func import passwords, save_passwords, save_diary_entries, diary_entries, personal_diary, add_diary_entry, view_diary_entries, generate_captcha, generate_image
from func import get_weather, plot_forecast, send_reminder, get_psychologist_response, generate_schedule
import speech_recognition as sr
from pydub import AudioSegment
from note import completed_tasks
import time
from telegram.ext import ContextTypes
AudioSegment.ffmpeg = "C:/Users/MAX/Desktop/ffmpeg/ffmpeg-master-latest-win64-gpl-shared/bin/ffmpeg.exe"

API_KEY_ID = "O7TpzThsMpM36eJh"
API_KEY_SECRET = "VDCPvDGgheOYf0dG"
LANG = "ru"
RESULT_TYPE = 1
headers = {"keyId": API_KEY_ID, "keySecret": API_KEY_SECRET}

# Словарь для хранения истории диалогов пользователей
conversation_context = {}

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Заметки", callback_data="notes")],
        [InlineKeyboardButton("📊 Результаты", callback_data="show_results")],
        [InlineKeyboardButton("❓ Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton("🧠 Личный психолог", callback_data="psychologist")],
        [InlineKeyboardButton("📆 Составить расписание", callback_data="schedule")],
        [InlineKeyboardButton("⏰ Установить напоминание", callback_data="set_reminder")],
        [InlineKeyboardButton("🌤 Узнать погоду", callback_data="weather")],
        [InlineKeyboardButton("📖 Личный дневник", callback_data="personal_diary")],
        [InlineKeyboardButton("🖼 Сгенерировать изображение", callback_data="generate_image")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: CallbackContext):
    """Приветственное сообщение"""
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_main_menu())

async def button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    reset_ai_context(context)
    context.user_data["waiting_for_captcha"] = False

    user_ip = str(update.effective_user.id)

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
        await query.message.reply_text("Введите задачи для составления расписания.")
        context.user_data["waiting_for_schedule_answers"] = True

    elif query.data == "set_reminder":
        await query.message.reply_text("Введите задачу для напоминания:")
        context.user_data["waiting_for_reminder_task"] = True

    elif query.data == "weather":
        await query.message.reply_text("Введите название города для получения погоды:")
        context.user_data["waiting_for_city"] = True

    elif query.data == "personal_diary":
        captcha_text, captcha_image = generate_captcha()
        context.user_data["captcha_text"] = captcha_text
        context.user_data["waiting_for_captcha"] = True
        await query.message.reply_photo(photo=captcha_image, caption="Введите цифры с изображения для подтверждения:")

    elif query.data == "generate_image":
        await query.message.reply_text("Введите текстовое описание для генерации изображения:")
        context.user_data["waiting_for_prompt"] = True

def split_message(text, max_length=4096):
    parts = []
    while len(text) > max_length:
        split_index = text[:max_length].rfind(". ")
        if split_index == -1:
            split_index = max_length
        parts.append(text[:split_index + 1])
        text = text[split_index + 1:]
    parts.append(text)
    return parts

def reset_ai_context(context):
    """Сбрасывает состояния общения с ИИ (психолог, вопросы и т. д.)."""
    context.user_data["waiting_for_psychologist"] = False
    context.user_data["waiting_for_question"] = False
    context.user_data.pop("question_history", None)
    context.user_data.pop("conversation_context", None)

def remove_markdown(text):
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Убираем жирный текст
    text = re.sub(r"\*(.*?)\*", r"\1", text)  # Убираем курсив
    text = re.sub(r"(.*?)", r"\1", text)  # Убираем моноширинный текст
    text = re.sub(r"_(.*?)_", r"\1", text)  # Убираем подчёркивание
    return text

async def weather_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Введите название города для получения погоды:")
    context.user_data["waiting_for_city"] = True

async def image_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Введите текстовое описание для генерации изображения:")
    context.user_data["waiting_for_prompt"] = True

async def handle_manual_command(update: Update, context: CallbackContext, command_type: str):
    if command_type == "ask_question":
        await update.message.reply_text("Введите ваш вопрос:")
        context.user_data["waiting_for_question"] = True
    elif command_type == "psychologist":
        await update.message.reply_text("🧠 Привет! Я твой личный психолог. Напиши, что тебя беспокоит.")
        context.user_data["waiting_for_psychologist"] = True

async def handle_reminder_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Введите задачу для напоминания:")
    context.user_data["waiting_for_reminder_task"] = True

async def weather_command(update: Update, context: CallbackContext):
    if "waiting_for_city" not in context.user_data:
        await update.message.reply_text("Введите название города для получения погоды:")
        context.user_data["waiting_for_city"] = True
    else:
        await update.message.reply_text("Вы уже в процессе получения погоды. Пожалуйста, подождите.")


async def show_results(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    count = completed_tasks.get(user_id, 0)

    # Генерация мотивации через ИИ
    motivation = await generate_motivation(context, count)

    await query.edit_message_text(
        f"🎯 Ваш прогресс:\nВыполнено важных задач: {count}\n\n{motivation}",
        reply_markup=get_main_menu()
    )


async def generate_motivation(context: CallbackContext, count: int):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": MODEL,
            "messages": [
                {"role": "system",
                 "content": "Ты - мотивационный тренер. Сгенерируй короткое вдохновляющее сообщение на русском языке, основываясь на количестве выполненных задач."},
                {"role": "user",
                 "content": f"Я выполнил {count} важных задач за все время. Напиши мотивационный ответ длиной до 3 предложений."}
            ]
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        result = response.json()
        return result['choices'][0]['message']['content'].strip()

    except Exception as e:
        print(f"Ошибка генерации мотивации: {e}")
        return "Ты молодец! Продолжай в том же духе! 💪"

# Функция для создания задачи на транскрипцию
def create_task(file_path):
    create_data = {
        "lang": LANG,
    }
    files = {}
    create_url = "https://api.speechflow.io/asr/file/v1/create"

    if file_path.startswith('http'):
        create_data['remotePath'] = file_path
        print('Submitting a remote file')
        response = requests.post(create_url, data=create_data, headers=headers)
    else:
        print('Submitting a local file')
        create_url += "?lang=" + LANG
        files['file'] = open(file_path, "rb")
        response = requests.post(create_url, headers=headers, files=files)

    if response.status_code == 200:
        create_result = response.json()
        print(create_result)
        if create_result["code"] == 10000:
            task_id = create_result["taskId"]
        else:
            print("Create error:")
            print(create_result["msg"])
            task_id = ""
    else:
        print('Create request failed: ', response.status_code)
        task_id = ""
    return task_id


# Функция для получения результата транскрипции
def query_task(task_id):
    query_url = f"https://api.speechflow.io/asr/file/v1/query?taskId={task_id}&resultType={RESULT_TYPE}"
    print('Querying transcription result')

    while True:
        response = requests.get(query_url, headers=headers)
        if response.status_code == 200:
            query_result = response.json()
            if query_result["code"] == 11000:
                print('Transcription result:')
                print(query_result)
                return query_result
            elif query_result["code"] == 11001:
                print('Waiting...')
                time.sleep(3)
                continue
            else:
                print("Transcription error:")
                print(query_result['msg'])
                return None
        else:
            print('Query request failed: ', response.status_code)
            return None


async def handle_voice_message(update: Update, context: CallbackContext):
    """Обрабатывает голосовое сообщение и транскрибирует его."""
    voice_file = await context.bot.get_file(update.message.voice.file_id)
    file_path = f"voice_{update.message.message_id}.ogg"
    await voice_file.download_to_drive(file_path)
    print(f"File saved to {file_path}")

    task_id = create_task(file_path)
    if task_id:
        result = query_task(task_id)
        if result:
            try:
                transcription_data = json.loads(result.get("result", "{}"))
                sentences = transcription_data.get("sentences", [])
                if sentences:
                    transcription = sentences[0].get("s", "Текст не найден.")
                else:
                    transcription = "Текст не найден."

                # Сохраняем текст в context.user_data
                context.user_data["transcribed_note"] = transcription

                await update.message.reply_text(f"Расшифровка: {transcription}")

                # Передаем транскрибированный текст в обработку
                await handle_message(update, context, transcription)

            except json.JSONDecodeError:
                await update.message.reply_text("Ошибка при обработке результата.")
        else:
            await update.message.reply_text("Не удалось выполнить расшифровку.")
    else:
        await update.message.reply_text("Ошибка при создании задачи для расшифровки.")

    os.remove(file_path)  # Удаляем файл после обработки

# Функция обработки сообщений (текстовых и транскрибированных голосовых)
async def handle_message(update: Update, context: CallbackContext, user_message: str = None):
    if user_message is None:  # Если текст не передан явно, берем его из context или update.message.text
        user_message = context.user_data.get("transcribed_note", update.message.text)

    if not user_message:
        await update.message.reply_text("❌ Не удалось получить текст сообщения.")
        return

    user_ip = str(update.effective_user.id)

    # Команда выхода из диалога с ИИ
    if user_message.lower() == "/exit":
        context.user_data["waiting_for_psychologist"] = False
        context.user_data["waiting_for_question"] = False
        context.user_data.pop("question_history", None)
        context.user_data.pop("conversation_context", None)
        await update.message.reply_text(remove_markdown("🛑 Диалог завершен. Чем еще могу помочь?"), reply_markup=get_main_menu())
        return

    # Проверка капчи
    if context.user_data.get("waiting_for_captcha"):
        if user_message == context.user_data.get("captcha_text"):
            await update.message.reply_text("Капча пройдена. Теперь введите пароль для доступа к дневнику:")

            context.user_data["waiting_for_captcha"] = False
            context.user_data["waiting_for_diary_password"] = user_ip

            if user_ip not in passwords:
                await update.message.reply_text(
                    "У вас нет установленного пароля. Введите новый пароль для доступа к дневнику:")
                context.user_data["setting_diary_password"] = user_ip
        else:
            await update.message.reply_text("❌ Неверная капча! Попробуйте снова.", reply_markup=get_main_menu())
            context.user_data["waiting_for_captcha"] = False
        return

    # Установка нового пароля для дневника
    if context.user_data.get("setting_diary_password") == user_ip:
        passwords[user_ip] = user_message
        save_passwords()
        del context.user_data["setting_diary_password"]
        await update.message.reply_text("Пароль установлен! Теперь вы можете открыть личный дневник.")
        return

    # Проверка пароля (если ожидаем пароль)
    if context.user_data.get("waiting_for_diary_password") == user_ip:
        if passwords.get(user_ip) == user_message:
            context.user_data["authenticated_diary"] = user_ip
            del context.user_data["waiting_for_diary_password"]
            await update.message.reply_text("✅ Доступ разрешен. Выберите действие:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Добавить запись", callback_data="add_diary_entry")],
                [InlineKeyboardButton("📜 Просмотреть записи", callback_data="view_diary_entries")]
            ]))
        else:
            await update.message.reply_text("❌ Неверный пароль! Попробуйте снова.")
        return

    # Работа с дневником: добавление записи
    if context.user_data.get("writing_diary") == user_ip:
        reset_ai_context(context)
        if user_ip not in diary_entries:
            diary_entries[user_ip] = []
        diary_entries[user_ip].append({"date": str(datetime.date.today()), "entry": user_message})
        save_diary_entries()
        del context.user_data["writing_diary"]
        await update.message.reply_text("Запись сохранена!")

    # Проверка и продолжение обработки в других случаях
    if context.user_data.get("waiting_for_reminder_task"):
        context.user_data["waiting_for_reminder_task"] = False
        context.user_data["reminder_task"] = user_message
        await update.message.reply_text(remove_markdown("Введите время напоминания в минутах:"))
        context.user_data["waiting_for_reminder_time"] = True
        return

    # Работа с напоминаниями
    if context.user_data.get("waiting_for_reminder_time"):
        context.user_data["waiting_for_reminder_time"] = False
        try:
            delay_minutes = int(user_message)
            task = context.user_data.get("reminder_task", "Напоминание")
            chat_id = update.message.chat.id
            context.job_queue.run_once(send_reminder, delay_minutes * 60, chat_id=chat_id, data=task)
            await update.message.reply_text(
                remove_markdown(f"⏰ Напоминание установлено! Я напомню вам через {delay_minutes} минут."))
        except ValueError:
            await update.message.reply_text(remove_markdown("Пожалуйста, введите корректное число минут."))
        return

    # Проверяем, если бот ждет заметку
    if context.user_data.get("waiting_for_note"):
        reset_ai_context(context)
        context.user_data["waiting_for_note"] = False
        await save_note(update, context)
        return

    # Получаем погоду
    if context.user_data.get("waiting_for_city"):
        weather_info, weather_image = get_weather(user_message)
        await update.message.reply_text(weather_info)
        if weather_image:
            await update.message.reply_photo(photo=open(weather_image, 'rb'))
        context.user_data["waiting_for_city"] = False
        return

    # Генерация изображений
    if context.user_data.get("waiting_for_prompt"):
        prompt = update.message.text
        await update.message.reply_text("Генерация изображения... Пожалуйста, подождите.")

        image_bytes = await generate_image(update, context, prompt)

        if image_bytes:
            image_bytes.seek(0)
            await update.message.reply_photo(photo=image_bytes, caption=f"Ваше изображение по описанию: '{prompt}'")
        else:
            await update.message.reply_text("Не удалось сгенерировать изображение. Попробуйте еще раз.")

        context.user_data["waiting_for_prompt"] = False
        await update.message.reply_text("Что бы вы хотели сделать дальше?", reply_markup=get_main_menu())  # Main menu after image
        return

    if context.user_data.get("waiting_for_schedule_answers"):
        reset_ai_context(context)
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

    if context.user_data.get("waiting_for_question"):
        question_history = context.user_data.get("question_history", [])
        question_history.append({"role": "user", "content": user_message})

        try:
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            data = {
                "model": MODEL,
                "messages": [{"role": "system",
                              "content": "Ты — интеллектуальный помощник, отвечающий на вопросы пользователей."}] + question_history,
                "stream": False
            }

            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
            response_json = response.json()
            bot_reply = response_json.get("choices", [{}])[0].get("message", {}).get("content", "Не удалось получить ответ.")

            bot_reply = remove_markdown(bot_reply)
            for part in split_message(bot_reply):
                await update.message.reply_text(part)

            question_history.append({"role": "assistant", "content": bot_reply})
            context.user_data["question_history"] = question_history

        except Exception as e:
            await update.message.reply_text(remove_markdown(f"Ошибка: {str(e)}"))
        return

    # Начало нового диалога с ИИ
    if user_message.lower() == "задать вопрос":
        context.user_data["waiting_for_question"] = True
        if "question_history" not in context.user_data:
            context.user_data["question_history"] = []
        await update.message.reply_text(remove_markdown("📝 Задайте ваш вопрос:"))
        return

    # Психолог
    if context.user_data.get("waiting_for_psychologist", False):
        reset_ai_context(context)
        bot_reply = get_psychologist_response(user_message, update.message.chat_id)
        await update.message.reply_text(remove_markdown(bot_reply))
        return

    await update.message.reply_text(remove_markdown("Я не понял ваш запрос. Используйте кнопки."), reply_markup=get_main_menu())


# Основная функция
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обработка команд через /
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("notes", lambda u, c: send_calendar(u, c, datetime.date.today().year, datetime.date.today().month)))
    application.add_handler(CommandHandler("ask_question", lambda u, c: handle_manual_command(u, c, "ask_question")))
    application.add_handler(CommandHandler("psychologist", lambda u, c: handle_manual_command(u, c, "psychologist")))
    application.add_handler(CommandHandler("schedule", generate_schedule))
    application.add_handler(CommandHandler("set_reminder", handle_reminder_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(CommandHandler("personal_diary", personal_diary))
    application.add_handler(CommandHandler("add_diary_entry", add_diary_entry))
    application.add_handler(CommandHandler("view_diary_entries", view_diary_entries))
    application.add_handler(CommandHandler("generate_image", image_command))

    # Обработка кнопок
    application.add_handler(CallbackQueryHandler(button_click,
                                                 pattern="^(notes|ask_question|psychologist|schedule|set_reminder|personal_diary|weather|generate_image)$"))
    application.add_handler(CallbackQueryHandler(handle_date_selection, pattern="^date_"))
    application.add_handler(CallbackQueryHandler(change_month, pattern="^change_month_"))
    application.add_handler(CallbackQueryHandler(add_note, pattern="^add_note$"))
    application.add_handler(CallbackQueryHandler(view_notes, pattern="^view_notes$"))
    application.add_handler(CallbackQueryHandler(delete_note, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(generate_schedule, pattern="^schedule$"))
    application.add_handler(CallbackQueryHandler(handle_main_menu, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(add_diary_entry, pattern="^add_diary_entry$"))
    application.add_handler(CallbackQueryHandler(view_diary_entries, pattern="^view_diary_entries$"))
    application.add_handler(CallbackQueryHandler(handle_category_selection, pattern="^category_"))
    application.add_handler(CallbackQueryHandler(handle_important_tasks, pattern="^important_tasks$"))
    application.add_handler(CallbackQueryHandler(complete_task, pattern="^complete_task_"))
    application.add_handler(CallbackQueryHandler(show_results, pattern="^show_results$"))

    # Обработка текстовых и голосовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))


    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()