import json
import os
from telegram import Update
from telegram.ext import CallbackContext
import torch
import torchvision
import torchvision.transforms as transforms
import random
from io import BytesIO
import requests
import base64
from API import STABILITY_API_URL, STABILITY_API_KEY, WEATHER_API_KEY, API_KEY, MODEL
import matplotlib.pyplot as plt
from note import notes
import datetime

PASSWORDS_FILE = "passwords.json"
DIARY_ENTRIES_FILE = "diary_entries.json"
conversation_context = {}

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

async def personal_diary(update: Update, context: CallbackContext):
    user_ip = str(update.effective_user.id)

    if context.user_data.get("waiting_for_captcha"):
        await update.message.reply_text("Вы уже в процессе подтверждения капчи. Пожалуйста, подождите.")
        return
    captcha_text, captcha_image = generate_captcha()
    context.user_data["captcha_text"] = captcha_text
    context.user_data["waiting_for_captcha"] = True
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

def generate_captcha():
    transform = transforms.Compose([transforms.ToTensor()])
    mnist_dataset = torchvision.datasets.MNIST(root="./data", train=True, download=True, transform=transform)

    random_indices = random.sample(range(len(mnist_dataset)), 4)
    captcha_digits = []
    captcha_images = []

    for idx in random_indices:
        image, label = mnist_dataset[idx]
        captcha_digits.append(str(label))
        captcha_images.append(image.squeeze(0))
    captcha_image = torch.cat(captcha_images, dim=1)
    captcha_image = transforms.ToPILImage()(captcha_image)
    img_byte_array = BytesIO()
    captcha_image.save(img_byte_array, format="PNG")
    img_byte_array.seek(0)
    return ''.join(captcha_digits), img_byte_array

async def generate_image(update, context, prompt):
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "text_prompts": [
            {"text": prompt}
        ],
        "cfg_scale": 15,
        "steps": 50,
        "samples": 1,
        "style_preset": "enhance"
    }
    response = requests.post(STABILITY_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        artifacts = response.json().get("artifacts", [])
        if artifacts:
            image_base64 = artifacts[0]["base64"]
            image_data = base64.b64decode(image_base64)
            image_bytes = BytesIO(image_data)
            return image_bytes
        else:
            await update.message.reply_text("Не удалось сгенерировать изображение. Попробуйте еще раз.")
            return None
    else:
        await update.message.reply_text(f"Произошла ошибка при генерации изображения: {response.status_code}")
        print(response.json())
        return None

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
    job = context.job
    await context.bot.send_message(job.chat_id, text=f"⏰ Напоминание: {job.data}")

def get_psychologist_response(user_input, chat_id):
    if chat_id not in conversation_context:
        conversation_context[chat_id] = []
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
        conversation_context[chat_id].append({"role": "assistant", "content": bot_reply})

        return bot_reply

    except Exception as e:
        print(f"Ошибка в get_psychologist_response: {e}")
        return "❌ Произошла ошибка при обработке запроса. Попробуйте позже!"

async def generate_schedule(update: Update, context: CallbackContext):
    from main import get_main_menu
    user = update.effective_user
    user_id = user.id if user else None

    if not user_id:
        await update.message.reply_text("Не удалось определить пользователя.")
        return

    today = datetime.date.today().strftime("%Y-%m-%d")
    user_notes = [note['note'] for note in notes.get(today, []) if note['user_id'] == user_id]

    if not user_notes:
        await update.effective_message.reply_text(
            "Сегодня у вас нет записанных дел. Добавьте заметки и попробуйте снова.",
            reply_markup=get_main_menu()
        )
        return
    context.user_data["schedule_notes"] = user_notes
    context.user_data["waiting_for_schedule_answers"] = True  # Включаем режим ожидания ответов
    await update.effective_message.reply_text(
        "Я вижу, у вас на сегодня такие задачи:\n\n" + "\n".join(user_notes) +
        "\n\nКакой порядок выполнения вам удобен? Укажите время, если это необходимо."
    )

