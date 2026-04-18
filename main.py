import telebot
from config import bot

pairs = {}
waiting_for_partner = {}

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,f"Привет, {message.from_user.first_name}! Я бот для пар")
    bot.send_message(
        message.chat.id,f"Напиши /connect, чтобы подключиться к партнеру")

@bot.message_handler(commands=['connect'])
def connect(message):
    waiting_for_partner[message.chat.id] = True
    bot.send_message(message.chat.id, "Введи числовой ID аккаунта партнера:")

@bot.message_handler(func=lambda m: m.chat.id in waiting_for_partner)
def set_partner(message):
    try:
        partner_id = int(message.text)
        pairs[message.chat.id] = partner_id
        pairs[partner_id] = message.chat.id

        waiting_for_partner.pop(message.chat.id)

        bot.send_message(message.chat.id, "Партнер подключен")
    except:
        bot.send_message(message.chat.id, "Ошибка, попробуйте ввести ID еще раз")

if __name__ == "__main__":
    bot.polling(none_stop=True)