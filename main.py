from config import bot
from telebot import types
import time
import db

waiting_for_partner = {}
waiting_for_message = {}

# --- ФУНКЦИИ-ПОМОЩНИКИ ---

def get_main_keyboard():
    """Создает главную клавиатуру с кнопками в два ряда"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    btn_love = types.KeyboardButton("💌 Отправить послание")
    btn_help = types.KeyboardButton("❓ Помощь")
    btn_start = types.KeyboardButton("🔄 Перезапуск")

    # .row() располагает кнопки в один ряд.
    markup.row(btn_love)
    markup.row(btn_help, btn_start)
    
    return markup

def get_gender_keyboard():
    """Создает инлайн-кнопки для выбора пола"""
    markup = types.InlineKeyboardMarkup()
    btn_m = types.InlineKeyboardButton("Я кот 🐈‍⬛", callback_data="gender_m")
    btn_f = types.InlineKeyboardButton("Я кошка 🐈", callback_data="gender_f")
    markup.add(btn_m, btn_f)
    return markup

def get_text_by_gender(user_id, male_text, female_text):
    """Возвращает нужный текст в зависимости от пола пользователя"""
    gender = db.get_gender(user_id)
    if gender == "female":
        return female_text
    return male_text

# --- ОСНОВНЫЕ КОМАНДЫ ---

@bot.message_handler(commands=['help'])
def help_command(message):
    markup = get_main_keyboard() if db.get_partner(message.chat.id) else None
    help_text = (
        "Доступные команды:\n\n"
        "/start — Перезапустить бота\n"
        "/help — Показать это меню\n"
        "/gender — Изменить свой пол\n"
        "/id — Узнать свой числовой ID\n"
        "/connect — Подключиться к партнеру\n"
        "/disconnect — Отключиться от партнера 💔\n"
        "/love — Отправить любовное послание 💌"
    )
    bot.send_message(message.chat.id, help_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def help_button_handler(message):
    help_command(message)

@bot.message_handler(commands=['start'])
def start(message):
    gender = db.get_gender(message.chat.id)

    # Если пол уже выбран, не показываем кнопки снова
    if gender:
        if db.get_partner(message.chat.id):
            status_text = get_text_by_gender(message.chat.id, "подключен", "подключена")
            bot.send_message(
                message.chat.id, 
                f"С возвращением! Ты уже {status_text} к своей половинке 💕\n"
                "Используй меню внизу, чтобы отправить послание, или /help для списка команд.",
                reply_markup=get_main_keyboard()
            )
        else:
            animal = "котик 🐈‍⬛" if gender == "male" else "кошечка 🐈"
            bot.send_message(
                message.chat.id, 
                f"С возвращением! В системе ты {animal}.\n"
                "Тебе осталось только подключиться к партнеру через команду /connect!"
            )
        return

    # Если пола нет, показываем регистрацию
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}! Я бот для парочек 💕\n"
        "Для начала, скажи кто ты:",
        reply_markup=get_gender_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "🔄 Перезапуск")
def start_button_handler(message):
    start(message)

@bot.message_handler(commands=['gender'])
def change_gender(message):
    # Прячем нижнюю клавиатуру коротким сообщением
    bot.send_message(
        message.chat.id, 
        "⚙️ Открываю настройки...", 
        reply_markup=types.ReplyKeyboardRemove()
    )
    # Выдаем сообщение с инлайн-кнопками
    bot.send_message(
        message.chat.id, 
        "Выбери, кем ты хочешь быть в системе:",
        reply_markup=get_gender_keyboard() 
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("gender_"))
def save_gender(call):
    gender = "male" if call.data == "gender_m" else "female"
    db.add_or_update_user(call.message.chat.id, gender, call.from_user.username)

    if db.get_partner(call.message.chat.id):
        bot.edit_message_text(
            "Готово! Твой пол успешно изменен ✨",
            call.message.chat.id, 
            call.message.message_id
        )
        bot.send_message(
            call.message.chat.id, 
            "Меню посланий активно 👇", 
            reply_markup=get_main_keyboard()
        )
    else:
        text = (
            "Отлично! Теперь ты можешь подключиться к своей половинке.\n\n"
            "Напиши /connect и введи ID партнера или его @username\n"
            "Чтобы узнать свой ID, напиши /id\n"
            "Если забудешь команды, просто нажми /help"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['id'])
def id(message):
    markup = get_main_keyboard() if db.get_partner(message.chat.id) else None
    bot.send_message(message.chat.id, "Твой числовой ID (нажми на цифры ниже, чтобы скопировать):")
    bot.send_message(
        message.chat.id, 
        f"`{message.from_user.id}`", 
        parse_mode="Markdown",
        reply_markup=markup
    )

# --- ПОДКЛЮЧЕНИЕ И ОТКЛЮЧЕНИЕ ---

@bot.message_handler(commands=['connect'])
def connect(message):
    if db.get_partner(message.chat.id):
        status_text = get_text_by_gender(message.chat.id, "подключен", "подключена")
        bot.send_message(
            message.chat.id, 
            f"⚠️ Ты уже {status_text} к партнеру! Сначала нужно разорвать текущую связь через команду /disconnect"
        )
        return

    waiting_for_partner[message.chat.id] = True
    bot.send_message(message.chat.id, "Введи числовой ID своей половинки или никнейм (например, @nickname):")

@bot.message_handler(func=lambda m: m.chat.id in waiting_for_partner)
def set_partner(message):
    if message.text.startswith('/'):
        waiting_for_partner.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Ввод отменен. Напиши команду еще раз:")
        return

    raw_input = message.text.strip()
    partner_id = None

    if raw_input.startswith('@'):
        partner_id = db.get_id_by_username(raw_input)
        if not partner_id:
            bot.send_message(message.chat.id, "⚠️ Пользователь с таким ником не найден. Он должен сначала зайти в бота!")
            return
    else:
        try:
            partner_id = int(raw_input)
        except ValueError:
            bot.send_message(
                message.chat.id, 
                "❌ Формат не распознан.\n"
                "Введи либо числовой ID (только цифры), либо никнейм (обязательно с символом @ в начале):"
            )
            return

    if partner_id == message.chat.id:
        bot.send_message(message.chat.id, "Нельзя подключиться к самому себе! Введи ID или ник партнера:")
        return

    if db.get_gender(partner_id) is None:
        bot.send_message(
            message.chat.id, 
            "⚠️ Ошибка! Твой партнер еще не запустил бота или не выбрал пол.\n"
            "Попроси его зайти в бота, нажать /start, выбрать пол и прислать тебе свой ID или ник!"
        )
        return 
            
    db.link_partners(message.chat.id, partner_id)
    waiting_for_partner.pop(message.chat.id, None)

    # Уведомления об успехе с выдачей главной клавиатуры
    action_text = get_text_by_gender(message.chat.id, "подключен", "подключена")
    target_text = get_text_by_gender(partner_id, "к своему котику! 🐈‍⬛", "к своей кошечке! 🐈")
    bot.send_message(
        message.chat.id, 
        f"Ура! Ты успешно {action_text} {target_text} 💕",
        reply_markup=get_main_keyboard()
    )

    notification_text = get_text_by_gender(message.chat.id, "К тебе подключился твой котик! 🐈‍⬛", "К тебе подключилась твоя кошечка! 🐈")
    bot.send_message(
        partner_id, 
        notification_text,
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['disconnect'])
def disconnect(message):
    if not db.get_partner(message.chat.id):
        status_text = get_text_by_gender(message.chat.id, "подключен", "подключена")
        bot.send_message(message.chat.id, f"Ты ни с кем не {status_text}. Для подключения нажми /connect")
        return

    # Прячем нижнюю клавиатуру коротким сообщением
    bot.send_message(
        message.chat.id, 
        "💔 Управление связью...", 
        reply_markup=types.ReplyKeyboardRemove()
    )

    changed_mind = get_text_by_gender(message.chat.id, "передумал", "передумала")
    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton("Да, отключиться 💔", callback_data="disconnect_yes")
    btn_no = types.InlineKeyboardButton(f"Нет, я {changed_mind} ❤️", callback_data="disconnect_no")
    markup.add(btn_yes, btn_no)

    sure_word = get_text_by_gender(message.chat.id, "уверен", "уверена")
    bot.send_message(
        message.chat.id, 
        f"Ты точно {sure_word}, что хочешь отключиться от своей половинки?", 
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("disconnect_"))
def process_disconnect(call):
    if call.data == "disconnect_no":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Отключение отменено. Вы всё еще вместе! 💕"
        )
        bot.send_message(
            call.message.chat.id, 
            "Главное меню активно 👇", 
            reply_markup=get_main_keyboard()
        )
        return
    
    if call.data == "disconnect_yes":
        partner_id = db.get_partner(call.message.chat.id)
        if partner_id:
            db.unlink_partners(call.message.chat.id)
            
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
            bot.send_message(
                call.message.chat.id,
                "Связь разорвана. Вы больше не подключены друг к другу. 💔",
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            initiator_text = get_text_by_gender(call.message.chat.id, "Твой котик разорвал", "Твоя кошечка разорвала")
            bot.send_message(
                partner_id, 
                f"💔 {initiator_text} связь. Вы больше не подключены друг к другу.",
                reply_markup=types.ReplyKeyboardRemove()
            )
        else:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Связь уже была разорвана."
            )

# --- ЛЮБОВНЫЕ ПОСЛАНИЯ ---

@bot.message_handler(commands=['love'])
def love(message):
    if db.get_partner(message.chat.id):
        waiting_for_message[message.chat.id] = True
        # Прячем кнопки, пока человек пишет сообщение
        bot.send_message(
            message.chat.id, 
            "Напиши сообщение для партнера 💌", 
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        bot.send_message(message.chat.id, "Сначала нужно подключиться к половинке через /connect")

@bot.message_handler(func=lambda message: message.text == "💌 Отправить послание")
def love_button_handler(message):
    love(message)

@bot.message_handler(func=lambda m: m.chat.id in waiting_for_message)
def send_love(message):
    if message.text.startswith('/'):
        waiting_for_message.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отправка сообщения отменена.", reply_markup=get_main_keyboard())
        return

    partner_id = db.get_partner(message.chat.id)

    if partner_id:
        sender_text = get_text_by_gender(
            message.chat.id,
            "твоего котика",
            "твоей кошечки"
        )
        bot.send_message(partner_id, f"💌 Сообщение от {sender_text}:\n\n{message.text}")
        bot.send_message(message.chat.id, "Отправлено 💕", reply_markup=get_main_keyboard())

    waiting_for_message.pop(message.chat.id, None)

# --- ЗАПУСК БОТА ---

if __name__ == "__main__":
    db.init_db() 
    print("Бот запущен...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=90) 
        except Exception as e:
            print(f"⚠️ Ошибка связи с Telegram. Жду 5 секунд... Ошибка: {e}")
            time.sleep(5)