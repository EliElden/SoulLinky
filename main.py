from config import bot
from telebot import types
import time
import db

waiting_for_partner = {}
waiting_for_message = {}

# /help - показать список команд
@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "Доступные команды:\n\n"
        "/start — Перезапустить бота\n"
        "/help — Показать это меню\n"
        "/id — Узнать свой числовой ID\n"
        "/connect — Подключиться к партнеру\n"
        "/disconnect — Отключиться от партнера 💔\n"
        "/love — Отправить любовное послание 💌"
    )
    bot.send_message(message.chat.id, help_text)

# Функция для получения текста в зависимости от пола пользователя
def get_text_by_gender(user_id, male_text, female_text):
    gender = db.get_gender(user_id)
    if gender == "female":
        return female_text
    return male_text

# /start - начать диалог с ботом и выбрать пол пользователя
@bot.message_handler(commands=['start'])
def start(message):
    if db.get_partner(message.chat.id):
        status_text = get_text_by_gender(
            message.chat.id, 
            male_text="подключен", 
            female_text="подключена"
        )
        
        bot.send_message(
            message.chat.id, 
            f"С возвращением! Ты уже {status_text} к своей половинке 💕\n"
            "Введи /love, чтобы отправить послание, или /help для списка команд."
        )
        return

    markup = types.InlineKeyboardMarkup()
    btn_m = types.InlineKeyboardButton("Я кот 🐈‍⬛", callback_data="gender_m")
    btn_f = types.InlineKeyboardButton("Я кошка 🐈", callback_data="gender_f")
    markup.add(btn_m, btn_f)

    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}! Я бот для парочек 💕\n"
        "Для начала, скажи кто ты:",
        reply_markup=markup
    )

# Обработка выбора пола пользователя
@bot.callback_query_handler(func=lambda call: call.data.startswith("gender_"))
def save_gender(call):
    gender = "male" if call.data == "gender_m" else "female"
    
    db.add_or_update_user(call.message.chat.id, gender, call.from_user.username)

    text = (
        "Отлично! Теперь ты можешь подключиться к своей половинке.\n\n"
        "Напиши /connect и введи ID партнера или его @username\n"
        "Чтобы узнать свой ID, напиши /id\n"
        "Если забудешь команды, просто нажми /help"
    )

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text
    )

# /id - показать числовой ID пользователя для подключения
@bot.message_handler(commands=['id'])
def id(message):
    bot.send_message(message.chat.id, "Твой числовой ID (нажми на цифры ниже, чтобы скопировать):")
    bot.send_message(message.chat.id, f"`{message.from_user.id}`", parse_mode="Markdown")

# /connect - начать процесс подключения к партнеру
@bot.message_handler(commands=['connect'])
def connect(message):
    if db.get_partner(message.chat.id):
        status_text = get_text_by_gender(
            message.chat.id,
            male_text="подключен",
            female_text="подключена"
        )
        
        bot.send_message(
            message.chat.id, 
            f"⚠️ Ты уже {status_text} к партнеру! Сначала нужно разорвать текущую связь через команду /disconnect"
        )
        return

    waiting_for_partner[message.chat.id] = True
    bot.send_message(message.chat.id, "Введи числовой ID своей половинки или никнейм (например, @nickname):")

# /disconnect - разорвать связь с партнером
@bot.message_handler(commands=['disconnect'])
def disconnect(message):
    if not db.get_partner(message.chat.id):
        bot.send_message(message.chat.id, "У тебя и так нет партнера. Для подключения нажми /connect")
        return

    changed_mind = get_text_by_gender(
        message.chat.id,
        male_text="передумал",
        female_text="передумала"
    )

    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton("Да, отключиться 💔", callback_data="disconnect_yes")
    btn_no = types.InlineKeyboardButton(f"Нет, я {changed_mind} ❤️", callback_data="disconnect_no")
    markup.add(btn_yes, btn_no)

    sure_word = get_text_by_gender(
        message.chat.id,
        male_text="уверен",
        female_text="уверена"
    )

    bot.send_message(
        message.chat.id, 
        f"Ты точно {sure_word}, что хочешь отключиться от своей половинки?", 
        reply_markup=markup
    )

# Обработка кнопок подтверждения отключения
@bot.callback_query_handler(func=lambda call: call.data.startswith("disconnect_"))
def process_disconnect(call):
    # Если человек передумал
    if call.data == "disconnect_no":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Отключение отменено. Вы всё еще вместе! 💕"
        )
        return
    
    # Если нажал "Да"
    if call.data == "disconnect_yes":
        partner_id = db.get_partner(call.message.chat.id)
        if partner_id:
            db.unlink_partners(call.message.chat.id)
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Связь разорвана. Вы больше не подключены друг к другу. 💔"
            )
            
            # Уведомляем второго человека
            initiator_text = get_text_by_gender(
                call.message.chat.id,
                male_text="Твой котик разорвал",
                female_text="Твоя кошечка разорвала"
            )
            bot.send_message(partner_id, f"💔 {initiator_text} связь. Вы больше не подключены друг к другу.")
        else:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Связь уже была разорвана."
            )

# Обработка ввода ID/ника партнера для подключения
@bot.message_handler(func=lambda m: m.chat.id in waiting_for_partner)
def set_partner(message):
    if message.text.startswith('/'):
        waiting_for_partner.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Ввод отменен. Напиши команду еще раз:")
        return

    raw_input = message.text.strip()
    partner_id = None

    # Гибридная проверка: никнейм или ID
    if raw_input.startswith('@'):
        partner_id = db.get_id_by_username(raw_input)
        if not partner_id:
            bot.send_message(message.chat.id, "⚠️ Пользователь с таким ником не найден. Он должен сначала зайти в бота!")
            return
    else:
        try:
            partner_id = int(raw_input)
        except ValueError:
            bot.send_message(message.chat.id, "Введи либо ID (цифры), либо никнейм (начиная с @)")
            return

    # Защита от случайного подключения к самому себе
    if partner_id == message.chat.id:
        bot.send_message(message.chat.id, "Нельзя подключиться к самому себе! Введи ID или ник партнера:")
        return

    # Проверка регистрации партнера
    if db.get_gender(partner_id) is None:
        bot.send_message(
            message.chat.id, 
            "⚠️ Ошибка! Твой партнер еще не запустил бота или не выбрал пол.\n"
            "Попроси его зайти в бота, нажать /start, выбрать пол и прислать тебе свой ID или ник!"
        )
        return 
            
    db.link_partners(message.chat.id, partner_id)
    waiting_for_partner.pop(message.chat.id, None)

    # Уведомления об успехе
    action_text = get_text_by_gender(
        message.chat.id,
        male_text="подключен",
        female_text="подключена"
    )
    target_text = get_text_by_gender(
        partner_id,
        male_text="к своему котику! 🐈‍⬛",
        female_text="к своей кошечке! 🐈"
    )
    bot.send_message(message.chat.id, f"Ура! Ты успешно {action_text} {target_text} 💕")

    notification_text = get_text_by_gender(
        message.chat.id, 
        male_text="К тебе подключился твой котик! 🐈‍⬛",
        female_text="К тебе подключилась твоя кошечка! 🐈"
    )
    bot.send_message(partner_id, notification_text)


# /love - отправить любовное послание партнеру
@bot.message_handler(commands=['love'])
def love(message):
    if db.get_partner(message.chat.id):
        waiting_for_message[message.chat.id] = True
        bot.send_message(message.chat.id, "Напиши сообщение для партнера 💌")
    else:
        bot.send_message(message.chat.id, "Сначала нужно подключиться к половинке через /connect")


# Обработка ввода сообщения для партнера и отправка ему
@bot.message_handler(func=lambda m: m.chat.id in waiting_for_message)
def send_love(message):
    if message.text.startswith('/'):
        waiting_for_message.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отправка сообщения отменена.")
        return

    partner_id = db.get_partner(message.chat.id)

    if partner_id:
        # Сделали сообщения тоже персонализированными в зависимости от пола отправителя
        sender_text = get_text_by_gender(
            message.chat.id,
            male_text="твоего котика",
            female_text="твоей кошечки"
        )
        bot.send_message(partner_id, f"💌 Сообщение от {sender_text}:\n\n{message.text}")
        bot.send_message(message.chat.id, "Отправлено 💕")

    waiting_for_message.pop(message.chat.id, None)

if __name__ == "__main__":
    db.init_db() # Обязательная инициализация базы данных
    print("Бот запущен...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=90) 
        except Exception as e:
            print(f"⚠️ Ошибка связи с Telegram. Жду 5 секунд... Ошибка: {e}")
            time.sleep(5)