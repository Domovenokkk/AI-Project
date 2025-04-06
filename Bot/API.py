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