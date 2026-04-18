from config import bot
from telebot import types

pairs = {}
waiting_for_partner = {}
waiting_for_message = {}
user_genders = {}

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    btn_m = types.InlineKeyboardButton("Я кот 🐈‍⬛", callback_data="gender_m")
    btn_f = types.InlineKeyboardButton("Я кошка 🐈", callback_data="gender_f")
    markup.add(btn_m, btn_f)

    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}! Я бот для парочек 💕\n"
        "Для начала, давай выберем твой пол:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("gender_"))
def save_gender(call):
    if call.data == "gender_m":
        user_genders[call.message.chat.id] = "male"
    elif call.data == "gender_f":
        user_genders[call.message.chat.id] = "female"

    text = (
        "Отлично! Теперь ты можешь подключиться к своей половинке.\n\n"
        "Напиши /connect, чтобы подключиться к партнеру\n"
        "Чтобы узнать свой ID для подключения, напиши /id\n\n"
        "Если забудешь команды, просто нажми /help"
    )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "Доступные команды:\n\n"
        "/start — Перезапустить бота\n"
        "/help — Показать это меню\n"
        "/id — Узнать свой числовой ID\n"
        "/connect — Подключиться к партнеру по его ID\n"
        "/love — Отправить любовное послание 💌"
    )
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['id'])
def id(message):
    bot.send_message(message.chat.id, f"Ваш ID: {message.from_user.id}")

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


@bot.message_handler(commands=['love'])
def love(message):
    
    if message.chat.id in pairs:
        waiting_for_message[message.chat.id] = True
        bot.send_message(message.chat.id, "Напиши сообщение для партнера 💌")
    else:
        bot.send_message(message.chat.id, "Сначала нужно подключиться к партнеру через /connect")

@bot.message_handler(func=lambda m: m.chat.id in waiting_for_message)
def send_love(message):
    partner_id = pairs.get(message.chat.id)

    if partner_id:
        bot.send_message(partner_id, f"💌 Сообщение от партнера:\n{message.text}")
        bot.send_message(message.chat.id, "Отправлено 💕")

    if message.chat.id in waiting_for_message:
        waiting_for_message.pop(message.chat.id)

if __name__ == "__main__":
    bot.polling(none_stop=True)