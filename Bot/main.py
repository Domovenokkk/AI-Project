import requests
import datetime
import re
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from note import handle_important_tasks, complete_task, load_completed_tasks, save_completed_tasks
from note import send_calendar, generate_calendar, handle_date_selection, change_month, add_note, save_note, \
    delete_note, view_notes, load_notes, save_notes, notes, handle_main_menu, handle_category_selection
from API import API_KEY, WEATHER_API_KEY, MODEL, TELEGRAM_TOKEN, STABILITY_API_KEY, STABILITY_API_URL, client
from func import passwords, save_passwords, save_diary_entries, diary_entries, personal_diary, add_diary_entry, \
    view_diary_entries, generate_captcha, generate_image
from func import get_weather, plot_forecast, send_reminder, get_psychologist_response, generate_schedule
from news import *
import speech_recognition as sr
from pydub import AudioSegment
from note import completed_tasks
import time
from datetime import date, datetime, timedelta
from telegram.ext import ContextTypes
from finance import *

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
        [InlineKeyboardButton("📅 Заметки", callback_data="notes"),
         InlineKeyboardButton("📊 Результаты", callback_data="show_results"),
         InlineKeyboardButton("❓ Вопросы", callback_data="ask_question")],
        [InlineKeyboardButton("🧠 Психолог", callback_data="psychologist"),
         InlineKeyboardButton("📆 Расписание", callback_data="schedule"),
         InlineKeyboardButton("⏰ Напоминания", callback_data="set_reminder")],
        [InlineKeyboardButton("🌤 Погода", callback_data="weather"),
         InlineKeyboardButton("📖 Дневник", callback_data="personal_diary"),
         InlineKeyboardButton("📰 Новости", callback_data="news_menu")],
        [InlineKeyboardButton("🖼 Генератор изображений", callback_data="generate_image"),
         InlineKeyboardButton("🎬 Фильмы", callback_data="movies")],
        [InlineKeyboardButton("📚 Книги", callback_data="books"),
         InlineKeyboardButton("💰 Финансы", callback_data="finance")]
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
        today = date.today()  # Используем date вместо datetime.date
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

    elif query.data == "movies":
        await query.message.reply_text(
            "Введите подробное описание того, что вы хотите посмотреть (жанр, настроение и т. д.):")
        context.user_data["waiting_for_movies_description"] = True

    elif query.data == "books":
        await query.message.reply_text("Введите подробное описание книги, которую вы хотите прочитать:")
        context.user_data["waiting_for_books_description"] = True

    # Обработка кнопки "Финансы"
    elif query.data == "finance":
        await finance_menu(update, context)
    # Остальные кнопки
    elif query.data == "track_expenses":
        await track_expenses(update, context)
    elif query.data == "track_income":
        await track_income(update, context)
    elif query.data.startswith("expense_"):
        await handle_expense_category(update, context)
    elif query.data.startswith("income_"):
        await handle_income_category(update, context)
    elif query.data == "monthly_summary":
        await monthly_summary(update, context)
    elif query.data == "saving_tips":
        await saving_tips(update, context)

async def saving_tips(update: Update, context: CallbackContext):
    try:
        # Получаем объект сообщения в зависимости от источника
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            msg = query.message
        else:
            msg = update.message

        # Генерация ответа через API
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты — финансовый консультант. Дай 5 практических советов по экономии денег на русском языке. Ответ должен быть структурированным с нумерованным списком."
                },
                {
                    "role": "user",
                    "content": "Сгенерируй советы по экономии денег"
                }
            ],
            "stream": False
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response_json = response.json()

        if response.status_code == 200:
            ai_reply = response_json.get("choices", [{}])[0].get("message", {}).get("content",
                                                                                    "Не удалось получить советы.")
            await msg.reply_text(ai_reply)
        else:
            error_msg = response_json.get("error", {}).get("message", "Неизвестная ошибка API")
            await msg.reply_text(f"Ошибка API: {error_msg}")

    except Exception as e:
        error_message = f"Ошибка генерации советов: {str(e)}"
        print(error_message)
        if update.callback_query:
            await update.callback_query.message.reply_text("⚠️ Произошла ошибка, попробуйте позже")
        elif update.message:
            await update.message.reply_text("⚠️ Произошла ошибка, попробуйте позже")

    except Exception as e:
        error_message = f"Ошибка генерации советов: {str(e)}"
        print(error_message)
        if update.callback_query:
            await update.callback_query.message.reply_text("⚠️ Произошла ошибка, попробуйте позже")
        elif update.message:
            await update.message.reply_text("⚠️ Произошла ошибка, попробуйте позже")

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

async def movies_command(update: Update, context: CallbackContext):
    """Обработчик команды /movies"""
    await update.message.reply_text(
        "Введите подробное описание того, что вы хотите посмотреть (жанр, настроение и т. д.):"
    )
    context.user_data["waiting_for_movies_description"] = True

async def books_command(update: Update, context: CallbackContext):
    """Обработчик команды /books"""
    await update.message.reply_text(
        "Введите подробное описание книги, которую вы хотите прочитать:"
    )
    context.user_data["waiting_for_books_description"] = True

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


async def get_movie_recommendations(description: str):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "Ты — помощник, который рекомендует фильмы на основе описания."},
                {"role": "user",
                 "content": f"Вот описание фильма, который я ищу: {description}. Дай мне 7-10 вариантов, которые могут мне подойти."}
            ],
            "stream": False
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response_json = response.json()
        movie_recommendations = response_json.get("choices", [{}])[0].get("message", {}).get("content",
                                                                                             "Не удалось найти подходящие фильмы.")

        return movie_recommendations
    except Exception as e:
        return f"Ошибка при получении рекомендаций для фильмов: {e}"


async def get_book_recommendations(description: str):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "Ты — помощник, который рекомендует книги на основе описания."},
                {"role": "user",
                 "content": f"Вот описание книги, которую я ищу: {description}. Дай мне 7-10 вариантов, которые могут мне подойти."}
            ],
            "stream": False
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response_json = response.json()
        book_recommendations = response_json.get("choices", [{}])[0].get("message", {}).get("content",
                                                                                            "Не удалось найти подходящие книги.")

        return book_recommendations
    except Exception as e:
        return f"Ошибка при получении рекомендаций для книг: {e}"


# Функция обработки сообщений (текстовых и транскрибированных голосовых)
async def handle_message(update: Update, context: CallbackContext, user_message: str = None):
    if user_message is None:  # Если текст не передан явно, берем его из context или update.message.text
        user_message = context.user_data.get("transcribed_note", update.message.text)

    if not user_message:
        await update.message.reply_text("❌ Не удалось получить текст сообщения.")
        return

    if await handle_finance_input(update, context):
        return

    if user_message.startswith('/finance'):
        await finance_menu(update, context)
        return

    user_ip = str(update.effective_user.id)

    # Команда выхода из диалога с ИИ
    if user_message.lower() == "/exit":
        context.user_data["waiting_for_psychologist"] = False
        context.user_data["waiting_for_question"] = False
        context.user_data.pop("question_history", None)
        context.user_data.pop("conversation_context", None)
        await update.message.reply_text(remove_markdown("🛑 Диалог завершен. Чем еще могу помочь?"),
                                        reply_markup=get_main_menu())
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

    # Обработка запроса на советы по экономии
    if user_message.lower() == "советы по экономии":
        await saving_tips(update, context)
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
        await update.message.reply_text("Что бы вы хотели сделать дальше?",
                                        reply_markup=get_main_menu())  # Main menu after image
        return

        # Обработка описания для фильмов
    if context.user_data.get("waiting_for_movies_description"):
        context.user_data["waiting_for_movies_description"] = False
        await update.message.reply_text("Поиск фильмов... Пожалуйста, подождите.")

        # Генерация запроса для ИИ
        movie_recommendations = await get_movie_recommendations(user_message)
        await update.message.reply_text(f"Вот несколько фильмов, которые могут вам подойти:\n{movie_recommendations}")

        # Обработка описания для книг
    if context.user_data.get("waiting_for_books_description"):
        context.user_data["waiting_for_books_description"] = False
        await update.message.reply_text("Поиск книг... Пожалуйста, подождите.")

        # Генерация запроса для ИИ
        book_recommendations = await get_book_recommendations(user_message)
        await update.message.reply_text(f"Вот несколько книг, которые могут вам подойти:\n{book_recommendations}")

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

        await update.message.reply_text(remove_markdown(f"📅 Ваше расписание на сегодня:\n\n{schedule}"),
                                        reply_markup=get_main_menu())
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
            bot_reply = response_json.get("choices", [{}])[0].get("message", {}).get("content",
                                                                                     "Не удалось получить ответ.")

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

    await update.message.reply_text(remove_markdown("Что хотите на этот раз?"), reply_markup=get_main_menu())


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Ошибка: {context.error}")
    if update.message:
        await update.message.reply_text("😞 Произошла ошибка, попробуйте позже")


def main():
    # Создаем приложение Telegram бота
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_error_handler(error_handler)

    # Регистрируем обработчики команд
    command_handlers = [
        CommandHandler("start", start),
        CommandHandler("notes", lambda u, c: send_calendar(u, c, date.today().year, date.today().month)),
        CommandHandler("ask_question", lambda u, c: handle_manual_command(u, c, "ask_question")),
        CommandHandler("psychologist", lambda u, c: handle_manual_command(u, c, "psychologist")),
        CommandHandler("schedule", generate_schedule),
        CommandHandler("set_reminder", handle_reminder_command),
        CommandHandler("weather", weather_command),
        CommandHandler("personal_diary", personal_diary),
        CommandHandler("add_diary_entry", add_diary_entry),
        CommandHandler("view_diary_entries", view_diary_entries),
        CommandHandler("generate_image", image_command),
        CommandHandler("finance", finance_menu),
        CommandHandler("movies", movies_command),
        CommandHandler("books", books_command)
    ]

    for handler in command_handlers:
        application.add_handler(handler)

    # Регистрируем обработчики callback-запросов
    callback_handlers = [
        CallbackQueryHandler(button_click, pattern="^(notes|ask_question|psychologist|schedule|"
                                                   "set_reminder|personal_diary|weather|"
                                                   "generate_image|movies|books)$"),
        CallbackQueryHandler(handle_date_selection, pattern="^date_"),
        CallbackQueryHandler(change_month, pattern="^change_month_"),
        CallbackQueryHandler(add_note, pattern="^add_note$"),
        CallbackQueryHandler(view_notes, pattern="^view_notes$"),
        CallbackQueryHandler(delete_note, pattern="^delete_"),
        CallbackQueryHandler(generate_schedule, pattern="^schedule$"),
        CallbackQueryHandler(handle_main_menu, pattern="^main_menu$"),
        CallbackQueryHandler(add_diary_entry, pattern="^add_diary_entry$"),
        CallbackQueryHandler(view_diary_entries, pattern="^view_diary_entries$"),
        CallbackQueryHandler(handle_category_selection, pattern="^category_"),
        CallbackQueryHandler(handle_important_tasks, pattern="^important_tasks$"),
        CallbackQueryHandler(complete_task, pattern="^complete_task_"),
        CallbackQueryHandler(show_results, pattern="^show_results$"),
        CallbackQueryHandler(news_menu, pattern="^news_menu$"),
        CallbackQueryHandler(handle_news_category, pattern="^news_"),

        # Финансовые обработчики
        CallbackQueryHandler(finance_menu, pattern="^finance$"),
        CallbackQueryHandler(track_expenses, pattern="^track_expenses$"),
        CallbackQueryHandler(track_income, pattern="^track_income$"),
        CallbackQueryHandler(monthly_summary, pattern="^monthly_summary$"),
        CallbackQueryHandler(saving_tips, pattern="^saving_tips$"),
        CallbackQueryHandler(
            handle_expense_category,
            pattern="^expense_"
        ),
        CallbackQueryHandler(
            handle_income_category,
            pattern="^income_"
        )
    ]

    for handler in callback_handlers:
        application.add_handler(handler)

    # Обработчики текстовых сообщений с приоритетами
    text_handlers = [
        # Высокий приоритет - финансовые операции
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_finance_input,
            block=False
        ),

        # Низкий приоритет - общий обработчик сообщений
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        ),

        # Обработчик голосовых сообщений
        MessageHandler(
            filters.VOICE,
            handle_voice_message
        )
    ]

    # Добавляем обработчики с указанием групп приоритета
    for i, handler in enumerate(text_handlers, start=1):
        application.add_handler(handler, group=i)

    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()