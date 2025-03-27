import together
# API-ключи
API_KEY = "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"
MODEL = "google/gemini-2.0-flash-001"
TELEGRAM_TOKEN = "7627101415:AAFZQxMXo6dHlxmee2WeRDCY-WL0lZ4TSb4"
WEATHER_API_KEY = "e180423e95471aa73e61e52e90ec3f7d"

# API-ключ Stability AI
STABILITY_API_KEY = 'sk-Wq7zsBrt1aKJxVQMjC0uXiDodA3vW7dtDQCH2uk8CON053f4'

# Endpoint для генерации изображений
STABILITY_API_URL = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

client = together.Client(api_key=API_KEY)