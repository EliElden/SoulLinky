import telebot
from config import bot

pairs = {}
waiting_for_partner = {}

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id, f"Привет, {message.from_user.first_name}! Я бот для пар")
    bot.send_message(
        message.chat.id, f"Напиши /connect, чтобы подключиться к партнеру")
    bot.send_message(
        message.chat.id, f"Чтобы узнать свой ID для подключения, напиши /id")

@bot.message_handler(commands=['connect'])
def connect(message):
    waiting_for_partner[message.chat.id] = True
    bot.send_message(message.chat.id, "Введи числовой ID партнера:")

@bot.message_handler(func=lambda m: m.chat.id in waiting_for_partner)
def set_partner(message):
    try:
        partner_id = int(message.text)
        pairs[message.chat.id] = partner_id
        pairs[partner_id] = message.chat.id

        waiting_for_partner.pop(message.chat.id)

        bot.send_message(message.chat.id, "Партнер успешно подключен!")
    except:
        bot.send_message(message.chat.id, "Ошибка, попробуй ввести ID еще раз")

@bot.message_handler(commands=['id'])
def id(message):
    bot.send_message(message.chat.id, f"Ваш ID: {message.from_user.id}")

if __name__ == "__main__":
    bot.polling(none_stop=True)