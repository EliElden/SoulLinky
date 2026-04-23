from config import bot
from telebot import types
import time
import db

# Списки для управления состояниями пользователей
waiting_for_partner = {}
waiting_for_message = {}
draft_messages = {}

# --- ФУНКЦИИ-ПОМОЩНИКИ (ИНТЕРФЕЙС И ТЕКСТЫ) ---

def get_main_keyboard():
    """Создает главную клавиатуру с кнопками в два ряда"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    btn_love = types.KeyboardButton("💌 Отправить послание")
    btn_help = types.KeyboardButton("❓ Помощь")
    btn_start = types.KeyboardButton("🔄 Перезапуск")

    markup.row(btn_love)
    markup.row(btn_help, btn_start)
    
    return markup

def get_gender_keyboard():
    """Создает инлайн-кнопки для выбора пола"""
    markup = types.InlineKeyboardMarkup()
    btn_m = types.InlineKeyboardButton("Я котик 🐈‍⬛", callback_data="gender_m")
    btn_f = types.InlineKeyboardButton("Я кошечка 🐈", callback_data="gender_f")
    markup.add(btn_m, btn_f)
    return markup

def get_target_partner_text(user_id):
    """Возвращает ласковое обращение к котейке, основываясь на РЕАЛЬНОМ поле партнера"""
    partner_id = db.get_partner(user_id)
    
    partner_gender = db.get_gender(partner_id)
    
    if partner_gender == "female":
        return "своей кошечке 🐈"
    return "своему котику 🐈‍⬛"

def get_text_by_gender(user_id, male_text, female_text):
    """Возвращает нужный текст в зависимости от пола пользователя"""
    gender = db.get_gender(user_id)
    if gender == "female":
        return female_text
    return male_text

def send_no_partner_error(chat_id):
    """Универсальная ошибка: у пользователя нет пары"""
    status_text = get_text_by_gender(chat_id, "подключен", "подключена")
    bot.send_message(
        chat_id, 
        f"⚠️ Ошибка: ты ни к кому не {status_text}. Сначала подключись к котейке через команду /connect!"
    )

def send_menu(chat_id, text="Главное меню 👇"):
    """Универсальный возврат кнопок главного меню"""
    bot.send_message(chat_id, text, reply_markup=get_main_keyboard())

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
        "/connect — Подключиться к котейке\n"
        "/disconnect — Отключиться от котейки 💔\n"
        "/love — Отправить послание котейке 💌"
    )
    bot.send_message(message.chat.id, help_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def help_button_handler(message):
    help_command(message)

@bot.message_handler(commands=['start'])
def start(message):
    gender = db.get_gender(message.chat.id)

    if gender:
        if db.get_partner(message.chat.id):
            status_text = get_text_by_gender(message.chat.id, "подключен", "подключена")
            target_text = get_target_partner_text(message.chat.id) 
            
            bot.send_message(
                message.chat.id, 
                f"С возвращением! Ты уже {status_text} к {target_text} 💕\n"
                "Используй меню внизу или /help для списка команд.",
                reply_markup=get_main_keyboard()
            )
        else:
            animal = "котик 🐈‍⬛" if gender == "male" else "кошечка 🐈"
            bot.send_message(
                message.chat.id, 
                f"С возвращением! В системе ты {animal}.\n"
                "Тебе осталось только подключиться к котейке через команду /connect!"
            )
        return

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
    bot.send_message(
        message.chat.id, 
        "⚙️ Открываю настройки...", 
        reply_markup=types.ReplyKeyboardRemove()
    )
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
        send_menu(call.message.chat.id, "Меню посланий активно 👇")
    else:
        text = (
            "Отлично! Теперь ты можешь подключиться к котейке.\n\n"
            "Напиши /connect и введи ID или @username котейки\n"
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
        target_text = get_target_partner_text(message.chat.id)
        
        bot.send_message(
            message.chat.id, 
            f"⚠️ Ты уже {status_text} к {target_text}! Сначала нужно разорвать текущую связь через команду /disconnect"
        )
        return

    waiting_for_partner[message.chat.id] = True
    bot.send_message(message.chat.id, "Введи числовой ID котейки или никнейм (например, @nickname):")

@bot.message_handler(func=lambda m: m.chat.id in waiting_for_partner)
def set_partner(message):
    if message.content_type != 'text':
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправь ID или никнейм текстом.")
        return

    if message.text in ["💌 Отправить послание", "❓ Помощь", "🔄 Перезапуск"]:
        waiting_for_partner.pop(message.chat.id, None)
        if message.text == "💌 Отправить послание":
            love(message)
        elif message.text == "❓ Помощь":
            help_command(message)
        else:
            start(message)
        return

    if message.text.startswith('/'):
        waiting_for_partner.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Ввод отменен.")
        return

    raw_input = message.text.strip()
    partner_id = None

    if raw_input.startswith('@'):
        partner_id = db.get_id_by_username(raw_input)
        if not partner_id:
            bot.send_message(message.chat.id, "⚠️ Котейка с таким ником не найден(а). Скажи сначала зайти в бота!")
            return
    else:
        try:
            partner_id = int(raw_input)
        except ValueError:
            bot.send_message(
                message.chat.id, 
                "❌ Формат не распознан.\n"
                "Введи либо числовой ID (только цифры), либо никнейм (обязательно с @ в начале):"
            )
            return

    if partner_id == message.chat.id:
        self_word = get_text_by_gender(
            message.chat.id,
            male_text="самому себе",
            female_text="самой себе"
        )
        bot.send_message(
            message.chat.id, 
            f"Нельзя подключиться к {self_word}! Введи ID или ник котейки:"
        )
        return

    if db.get_gender(partner_id) is None:
        bot.send_message(
            message.chat.id, 
            "⚠️ Ошибка! Котейка еще не запустил(а) бота или не выбрал(а) пол.\n"
            "Попроси зайти в бота, нажать /start, выбрать пол и прислать тебе свой ID или ник!"
        )
        return 
            
    db.link_partners(message.chat.id, partner_id)
    
    waiting_for_partner.pop(message.chat.id, None)
    waiting_for_partner.pop(partner_id, None) 
    waiting_for_message.pop(partner_id, None) 

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
        send_no_partner_error(message.chat.id)
        return

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
        f"Ты точно {sure_word}, что хочешь отключиться от котейки?", 
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
        send_menu(call.message.chat.id, "Главное меню активно 👇")
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

# --- СИСТЕМА ЛЮБОВНЫХ ПОСЛАНИЙ (ЧЕРНОВИКИ) ---

@bot.message_handler(commands=['love'])
def love(message):
    if db.get_partner(message.chat.id):
        waiting_for_message[message.chat.id] = True
        bot.send_message(
            message.chat.id, 
            "Пришли мне послание (текст, фото, стикер, голос или кружочек) 💌\n"
            "Чтобы отправить фото с текстом, просто добавь описание к картинке!", 
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        send_no_partner_error(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "💌 Отправить послание")
def love_button_handler(message):
    love(message)

@bot.message_handler(
    func=lambda m: m.chat.id in waiting_for_message, 
    content_types=['text', 'photo', 'voice', 'video', 'video_note', 'document', 'sticker', 'audio', 'animation']
)
def receive_love_draft(message):
    if message.content_type == 'text' and message.text in ["💌 Отправить послание", "❓ Помощь", "🔄 Перезапуск"]:
        waiting_for_message.pop(message.chat.id, None)
        if message.text == "💌 Отправить послание":
            love(message)
        elif message.text == "❓ Помощь":
            help_command(message)
        else:
            start(message)
        return

    if message.content_type == 'text' and message.text.startswith('/'):
        waiting_for_message.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    waiting_for_message.pop(message.chat.id, None)
    draft_messages[message.chat.id] = message.message_id

    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("Отправить 💌", callback_data="draft_send")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="draft_cancel")
    
    markup.add(btn_cancel, btn_send) 

    bot.reply_to(message, "Послание готово. Отправляем?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("draft_"))
def process_draft(call):
    user_id = call.message.chat.id
    
    if call.data == "draft_cancel":
        draft_messages.pop(user_id, None)
        bot.edit_message_text("Отправка отменена 🗑️", user_id, call.message.message_id)
        send_menu(user_id)
        return

    if call.data == "draft_send":
        message_id = draft_messages.get(user_id)
        partner_id = db.get_partner(user_id)
        
        if not message_id or not partner_id:
            bot.edit_message_text("⚠️ Ошибка: черновик не найден или бот отключился.", user_id, call.message.message_id)
            send_menu(user_id)
            return
            
        sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
        bot.send_message(partner_id, f"💌 Новое послание от {sender_text}:")
        bot.copy_message(partner_id, user_id, message_id)

        bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
        send_menu(user_id)
        draft_messages.pop(user_id, None)

# --- ЗАПУСК БОТА ---

if __name__ == "__main__":
    db.init_db() 
    print("Бот запущен и готов к работе...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=90) 
        except Exception as e:
            print(f"⚠️ Ошибка связи с Telegram. Жду 5 секунд... Ошибка: {e}")
            time.sleep(5)