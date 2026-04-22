import telebot
import os
from telebot import apihelper
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PROXY = os.getenv("PROXY_URL")

if PROXY:
    apihelper.proxy = {'https': PROXY}

bot = telebot.TeleBot(TOKEN)
