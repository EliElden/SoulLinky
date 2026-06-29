import telebot
import os
from telebot import apihelper
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PROXY = os.getenv("PROXY_URL")

#задокументировать следующие 2 строчки, если прокси не нужен
if PROXY:
   apihelper.proxy = {'https': PROXY}

bot = telebot.TeleBot(TOKEN)

# Достаем строчку с ID из .env (если её нет, берем пустую строку)
admin_ids_raw = os.getenv('ADMIN_IDS', '')

# Превращаем строку '123,456' в настоящий список чисел: [123, 456]
ADMIN_IDS = []
if admin_ids_raw:
    for admin_id in admin_ids_raw.split(','):
        ADMIN_IDS.append(int(admin_id.strip()))
