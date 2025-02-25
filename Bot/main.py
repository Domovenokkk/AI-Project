import together
import requests
import calendar
import datetime
import os
import json
import re
import matplotlib.pyplot as plt
import torch
import torchvision
import torchvision.transforms as transforms
import random
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from note import send_calendar, generate_calendar, handle_date_selection, change_month, add_note, save_note, delete_note, view_notes, load_notes, save_notes, notes, handle_main_menu

# API-ключи
API_KEY = "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"
MODEL = "google/gemini-2.0-flash-001"
TELEGRAM_TOKEN = "7627101415:AAFZQxMXo6dHlxmee2WeRDCY-WL0lZ4TSb4"
WEATHER_API_KEY = "e180423e95471aa73e61e52e90ec3f7d"

client = together.Client(api_key=API_KEY)

# Словарь для хранения истории диалогов пользователей
conversation_context = {}

PASSWORDS_FILE = "passwords.json"
DIARY_ENTRIES_FILE = "diary_entries.json"

if os.path.exists(PASSWORDS_FILE) and os.path.getsize(PASSWORDS_FILE) > 0:
    try:
        with open(PASSWORDS_FILE, "r") as f:
            passwords = json.load(f)
    except json.JSONDecodeError:
        passwords = {}
else:
    passwords = {}

with open(PASSWORDS_FILE, "w") as f:
    json.dump(passwords, f)

# Загружаем записи дневника
if os.path.exists(DIARY_ENTRIES_FILE) and os.path.getsize(DIARY_ENTRIES_FILE) > 0:
    try:
        with open(DIARY_ENTRIES_FILE, "r") as f:
            diary_entries = json.load(f)
    except json.JSONDecodeError:
        diary_entries = {}
else:
    diary_entries = {}

def save_passwords():
    with open(PASSWORDS_FILE, "w") as f:
        json.dump(passwords, f)

def save_diary_entries():
    with open(DIARY_ENTRIES_FILE, "w") as f:
        json.dump(diary_entries, f)

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Заметки", callback_data="notes")],
        [InlineKeyboardButton("❓ Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton("🧠 Личный психолог", callback_data="psychologist")],
        [InlineKeyboardButton("📆 Составить расписание", callback_data="schedule")],
        [InlineKeyboardButton("⏰ Установить напоминание", callback_data="set_reminder")],
        [InlineKeyboardButton("🌤 Узнать погоду", callback_data="weather")],
        [InlineKeyboardButton("📖 Личный дневник", callback_data="personal_diary")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: CallbackContext):
    """Приветственное сообщение"""
    await update.message.reply_text("Привет! Выбери действие:", reply_markup=get_main_menu())

async def weather_command(update: Update, context: CallbackContext):
    """Обрабатывает запрос на погоду как через команду, так и через кнопку"""
    if "waiting_for_city" not in context.user_data:
        await update.message.reply_text("Введите название города для получения погоды:")
        context.user_data["waiting_for_city"] = True
    else:
        await update.message.reply_text("Вы уже в процессе получения погоды. Пожалуйста, подождите.")


def reset_ai_context(context):
    """Сбрасывает состояния общения с ИИ (психолог, вопросы и т. д.)."""
    context.user_data["waiting_for_psychologist"] = False
    context.user_data["waiting_for_question"] = False
    context.user_data.pop("question_history", None)
    context.user_data.pop("conversation_context", None)

async def button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    # Сбрасываем активные состояния общения с ИИ перед переходом в новый раздел
    reset_ai_context(context)

    # Сбрасываем флаг ожидания капчи, если он установлен
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
        # Запрашиваем данные для расписания
        await query.message.reply_text("Введите задачи для составления расписания.")
        context.user_data["waiting_for_schedule_answers"] = True

    elif query.data == "set_reminder":
        # Запрос на установку напоминания
        await query.message.reply_text("Введите задачу для напоминания:")
        context.user_data["waiting_for_reminder_task"] = True

    elif query.data == "weather":
        # Запрос на погоду
        await query.message.reply_text("Введите название города для получения погоды:")
        context.user_data["waiting_for_city"] = True

    elif query.data == "personal_diary":
        # Генерация капчи
        captcha_text, captcha_image = generate_captcha()

        # Сохраняем капчу для дальнейшей проверки
        context.user_data["captcha_text"] = captcha_text
        context.user_data["waiting_for_captcha"] = True  # Устанавливаем флаг ожидания капчи

        # Отправляем пользователю капчу
        await query.message.reply_photo(photo=captcha_image, caption="Введите цифры с изображения для подтверждения:")

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

def generate_captcha():
    """Генерирует капчу и возвращает текст и изображение (из 5 цифр)"""
    transform = transforms.Compose([transforms.ToTensor()])
    mnist_dataset = torchvision.datasets.MNIST(root="./data", train=True, download=True, transform=transform)

    random_indices = random.sample(range(len(mnist_dataset)), 4)  # Выбираем 5 случайных цифр
    captcha_digits = []
    captcha_images = []

    for idx in random_indices:
        image, label = mnist_dataset[idx]
        captcha_digits.append(str(label))
        captcha_images.append(image.squeeze(0))  # Убираем лишнее измерение, чтобы осталась форма (28, 28)

    # Теперь объединяем изображения по ширине (по оси 1)
    captcha_image = torch.cat(captcha_images, dim=1)  # Собираем изображение из 5 цифр (по оси 1)
    captcha_image = transforms.ToPILImage()(captcha_image)  # Преобразуем в формат PIL

    # Сохраняем капчу как изображение в байтовый поток
    img_byte_array = BytesIO()
    captcha_image.save(img_byte_array, format="PNG")
    img_byte_array.seek(0)

    # Возвращаем текст капчи и саму картинку
    return ''.join(captcha_digits), img_byte_array



def remove_markdown(text):
    """Удаляет Markdown-форматирование (**жирный**, *курсив*, _подчеркнутый_, `код`)"""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Убираем жирный текст
    text = re.sub(r"\*(.*?)\*", r"\1", text)  # Убираем курсив
    text = re.sub(r"`(.*?)`", r"\1", text)  # Убираем моноширинный текст
    text = re.sub(r"_(.*?)_", r"\1", text)  # Убираем подчёркивание
    return text


def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print("Ответ от OpenWeatherMap:", data)  # Добавляем логирование
        forecast = {}
        for entry in data['list']:
            date = entry['dt_txt'].split(' ')[0]
            if date not in forecast:
                forecast[date] = []
            forecast[date].append(entry['main']['temp'])

        avg_temps = {date: sum(temps) / len(temps) for date, temps in forecast.items()}

        weather_desc = data['list'][0]['weather'][0]['description'].capitalize()
        temp = data['list'][0]['main']['temp']
        feels_like = data['list'][0]['main']['feels_like']
        humidity = data['list'][0]['main']['humidity']
        wind_speed = data['list'][0]['wind']['speed']

        weather_info = f"🌤 Погода в {city}: {weather_desc}\n"
        weather_info += f"🌡 Температура: {temp}°C (Ощущается как {feels_like}°C)\n"
        weather_info += f"💧 Влажность: {humidity}%\n"
        weather_info += f"💨 Ветер: {wind_speed} м/с\n"

        forecast_image = plot_forecast(avg_temps, city)

        return weather_info, forecast_image
    else:
        print(f"Ошибка при получении данных о погоде: {response.status_code}")  # Логируем ошибку
        return "❌ Не удалось получить данные о погоде. Проверьте правильность названия города.", None



def plot_forecast(avg_temps, city):
    dates = list(avg_temps.keys())
    temps = list(avg_temps.values())

    plt.figure(figsize=(10, 5))
    plt.plot(dates, temps, marker='o', linestyle='-', color='b', linewidth=2, markersize=6)
    plt.fill_between(dates, temps, color='skyblue', alpha=0.3)

    plt.xlabel('Дата', fontsize=12)
    plt.ylabel('Температура (°C)', fontsize=12)
    plt.title(f'Прогноз погоды в {city} на неделю', fontsize=14)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(rotation=45)

    filename = f"forecast_{city}.png"
    plt.savefig(filename, bbox_inches='tight')
    plt.close()

    return filename

async def send_reminder(context: CallbackContext):
    """Отправляет напоминание пользователю"""
    job = context.job
    await context.bot.send_message(job.chat_id, text=f"⏰ Напоминание: {job.data}")

conversation_context = {}  # Храним историю общения с психологом

async def weather_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Введите название города для получения погоды:")
    context.user_data["waiting_for_city"] = True

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
        print("Ответ от OpenRouter:", response_json)
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

async def personal_diary(update: Update, context: CallbackContext):
    """Функция для обработки входа в личный дневник с капчей"""
    user_ip = str(update.effective_user.id)

    # Проверяем, не был ли ранее установлен флаг ожидания капчи
    if context.user_data.get("waiting_for_captcha"):
        await update.message.reply_text("Вы уже в процессе подтверждения капчи. Пожалуйста, подождите.")
        return

    # Генерация капчи
    captcha_text, captcha_image = generate_captcha()

    # Сохраняем капчу для дальнейшей проверки
    context.user_data["captcha_text"] = captcha_text
    context.user_data["waiting_for_captcha"] = True  # Устанавливаем флаг ожидания капчи

    # Отправляем пользователю капчу
    await update.message.reply_photo(photo=captcha_image, caption="Введите цифры с изображения для подтверждения:")
    print("Капча отправлена пользователю:", captcha_text)
    print("Флаг waiting_for_captcha установлен:", context.user_data.get("waiting_for_captcha"))


async def add_diary_entry(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_ip = str(query.from_user.id)
    if user_ip in passwords and context.user_data.get("authenticated_diary") == user_ip:
        await query.message.reply_text("Введите запись в дневник:")
        context.user_data["writing_diary"] = user_ip
    else:
        await query.message.reply_text("Сначала введите пароль для доступа к дневнику.")

async def view_diary_entries(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_ip = str(query.from_user.id)
    if user_ip in passwords and context.user_data.get("authenticated_diary") == user_ip:
        entries = diary_entries.get(user_ip, [])
        if not entries:
            await query.message.reply_text("У вас пока нет записей в дневнике.")
        else:
            messages = [f"📅 {entry['date']}: {entry['entry']}" for entry in entries]
            await query.message.reply_text("\n".join(messages))
    else:
        await query.message.reply_text("Сначала введите пароль для доступа к дневнику.")

async def handle_message(update: Update, context: CallbackContext):
    """Обработка текстовых сообщений (включая ответы для психолога и диалог с ИИ)"""
    user_message = update.message.text.strip()
    user_ip = str(update.effective_user.id)

    # Команда выхода из диалога с ИИ
    if user_message.lower() == "/exit":
        context.user_data["waiting_for_psychologist"] = False
        context.user_data["waiting_for_question"] = False  # Завершаем диалог с ИИ
        context.user_data.pop("question_history", None)  # Очищаем историю диалога
        context.user_data.pop("conversation_context", None)  # Очищаем историю диалога с психологом
        await update.message.reply_text(remove_markdown("🛑 Диалог завершен. Чем еще могу помочь?"), reply_markup=get_main_menu())
        return

    # Проверка капчи
    if context.user_data.get("waiting_for_captcha"):
        if user_message == context.user_data.get("captcha_text"):
            # Капча пройдена, теперь запрашиваем пароль
            await update.message.reply_text("Капча пройдена. Теперь введите пароль для доступа к дневнику:")

            # Устанавливаем флаг для пароля
            context.user_data["waiting_for_captcha"] = False  # Сброс флага капчи
            context.user_data["waiting_for_diary_password"] = user_ip  # Устанавливаем флаг для пароля

            # Если пароля нет, то предлагаем создать новый
            if user_ip not in passwords:
                await update.message.reply_text(
                    "У вас нет установленного пароля. Введите новый пароль для доступа к дневнику:")
                context.user_data["setting_diary_password"] = user_ip  # Устанавливаем флаг для создания пароля
        else:
            # Неверная капча, возвращаем в главное меню
            await update.message.reply_text("❌ Неверная капча! Попробуйте снова.", reply_markup=get_main_menu())
            context.user_data["waiting_for_captcha"] = False  # Сброс капчи
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
            # Пароль верен
            context.user_data["authenticated_diary"] = user_ip  # Устанавливаем, что пользователь аутентифицирован
            del context.user_data["waiting_for_diary_password"]  # Убираем флаг ожидания пароля
            await update.message.reply_text("✅ Доступ разрешен. Выберите действие:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Добавить запись", callback_data="add_diary_entry")],
                [InlineKeyboardButton("📜 Просмотреть записи", callback_data="view_diary_entries")]
            ]))
        else:
            # Пароль неверен
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

    # Работа с заметками
    if context.user_data.get("waiting_for_note"):
        reset_ai_context(context)
        context.user_data["waiting_for_note"] = False
        await save_note(update, context)
        return

    if context.user_data.get("waiting_for_city"):
        weather_info, weather_image = get_weather(user_message)
        await update.message.reply_text(weather_info)
        if weather_image:
            await update.message.reply_photo(photo=open(weather_image, 'rb'))
        context.user_data["waiting_for_city"] = False  # Сброс флага
        return

    # Обработка планирования расписания
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

    # Обработка учебных вопросов (поддержка диалога с ИИ)
    if context.user_data.get("waiting_for_question"):
        reset_ai_context(context)
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
        reset_ai_context(context)
        context.user_data["waiting_for_question"] = True
        context.user_data["question_history"] = []  # Очищаем историю перед новым вопросом
        await update.message.reply_text(remove_markdown("📝 Задайте ваш вопрос:"))
        return

    # Обработка общения с психологом (сохранение истории)
    if context.user_data.get("waiting_for_psychologist", False):
        reset_ai_context(context)
        bot_reply = get_psychologist_response(user_message, update.message.chat_id)
        await update.message.reply_text(remove_markdown(bot_reply))
        return

    await update.message.reply_text(remove_markdown("Я не понял ваш запрос. Используйте кнопки."), reply_markup=get_main_menu())


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

    # Обработка кнопок

    application.add_handler(CallbackQueryHandler(button_click,
                                                 pattern="^(notes|ask_question|psychologist|schedule|set_reminder|personal_diary|weather)$"))
    application.add_handler(CallbackQueryHandler(handle_date_selection, pattern="^date_"))
    application.add_handler(CallbackQueryHandler(change_month, pattern="^change_month_"))
    application.add_handler(CallbackQueryHandler(add_note, pattern="^add_note$"))
    application.add_handler(CallbackQueryHandler(view_notes, pattern="^view_notes$"))
    application.add_handler(CallbackQueryHandler(delete_note, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(generate_schedule, pattern="^schedule$"))
    application.add_handler(CallbackQueryHandler(handle_main_menu, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(add_diary_entry, pattern="^add_diary_entry$"))
    application.add_handler(CallbackQueryHandler(view_diary_entries, pattern="^view_diary_entries$"))

    # Обработка текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()