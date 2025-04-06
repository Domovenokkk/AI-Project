from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
import requests
import time
from telegram.error import BadRequest
from datetime import datetime, timedelta

async def news_menu(update: Update, context: CallbackContext):
    categories = [
        ["Общие 🗞", "news_general"],
        ["Технологии 💻", "news_technology"],
        ["Бизнес 💼", "news_business"],
        ["Наука 🧪", "news_science"],
        ["Спорт ⚽", "news_sports"]
    ]

    # Формируем клавиатуру
    keyboard = [
        *[[InlineKeyboardButton(cat[0], callback_data=cat[1])] for cat in categories],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]

    await update.callback_query.edit_message_text(
        "📰 Выберите категорию новостей:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def get_news(category: str):
    API_KEY = "3d6342443a39413f91d99eb6911cf4b5"  # Замените на реальный ключ
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    try:
        url = f"https://newsapi.org/v2/everything?q={category}&from={week_ago}&sortBy=publishedAt&language=ru&pageSize=5&apiKey={API_KEY}"
        response = requests.get(url)
        data = response.json()

        if data.get("status") == "ok" and data.get("totalResults", 0) > 0:
            return format_news(data["articles"])
        return "😞 В этой категории пока нет свежих новостей за последнюю неделю"

    except Exception as e:
        print(f"News API Error: {e}")
        return "⚠️ Не удалось получить новости. Попробуйте позже."


def format_news(articles):
    news_items = []
    for idx, article in enumerate(articles[:5], 1):
        title = article.get('title', 'Без названия').split(' - ')[0]
        source = f"📌 {article.get('source', {}).get('name', 'Неизвестный источник')}"
        url = article.get('url', '')
        if url:
            link = f"<a href='{url}'>Читать</a>"
        else:
            link = "🚫 Нет ссылки"

        news_items.append(f"{idx}. {title}\n{source} | {link}\n")

    return "\n".join(news_items)


async def handle_news_category(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    category_map = {
        "news_general": "россия",
        "news_technology": "технологии",
        "news_business": "бизнес",
        "news_science": "наука",
        "news_sports": "спорт"
    }

    category = category_map.get(query.data)
    if category:
        try:
            news_text = await get_news(category)
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data=f"{query.data}_{int(time.time())}"),
                 InlineKeyboardButton("🔙 Назад", callback_data="news_menu")]
            ]

            # Проверка на изменение контента
            if query.message.text == f"📰 Последние новости:\n\n{news_text}":
                await query.answer("Новых новостей пока нет")
                return

            await query.edit_message_text(
                f"📰 Последние новости:\n\n{news_text}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer("Новых новостей пока нет")
            else:
                await query.answer("Ошибка обновления")