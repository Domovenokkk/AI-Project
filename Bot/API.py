import together
# API-ключи
API_KEY = "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"
MODEL = "google/gemini-2.0-flash-001"
TELEGRAM_TOKEN = "7627101415:AAFZQxMXo6dHlxmee2WeRDCY-WL0lZ4TSb4"
WEATHER_API_KEY = "e180423e95471aa73e61e52e90ec3f7d"

# API-ключ Stability AI
STABILITY_API_KEY = 'sk-08QaHikVw1ZEV0TIjTNkSyHApNlUoJO9QNgG32fvImcpdsTf'

# Endpoint для генерации изображений
STABILITY_API_URL = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

client = together.Client(api_key=API_KEY)