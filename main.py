from config import bot
from telebot import types
import time
import db 

# --- ГЛОБАЛЬНЫЕ СОСТОЯНИЯ ---
# Словари для временного хранения данных в оперативной памяти бота.
# Ключ — это chat_id пользователя, значение — статус или данные.
waiting_for_partner = {} # Флаг: пользователь находится в процессе ввода ID/ника партнера
waiting_for_message = {} # Флаг: пользователь пишет любовное послание
draft_messages = {}      # Хранилище ID сообщений (черновиков) до их подтверждения отправки

# ==========================================
# ФУНКЦИИ-ПОМОЩНИКИ (ИНТЕРФЕЙС И ТЕКСТЫ)
# ==========================================

def get_main_keyboard():
    """Создает главную reply-клавиатуру (постоянное меню внизу экрана)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    btn_love = types.KeyboardButton("💌 Отправить послание")
    btn_help = types.KeyboardButton("❓ Помощь")
    btn_start = types.KeyboardButton("🔄 Перезапуск")

    # Располагаем кнопки в два ряда для компактности
    markup.row(btn_love)
    markup.row(btn_help, btn_start)
    
    return markup

def get_gender_keyboard():
    """Создает inline-клавиатуру для первичного выбора пола или его изменения"""
    markup = types.InlineKeyboardMarkup()
    btn_m = types.InlineKeyboardButton("Я котик 🐈‍⬛", callback_data="gender_m")
    btn_f = types.InlineKeyboardButton("Я кошечка 🐈", callback_data="gender_f")
    markup.add(btn_m, btn_f)
    return markup

def get_target_partner_text(user_id):
    """
    Определяет пол ПАРТНЕРА по базе данных и возвращает правильное
    ласковое обращение (используется для подстановки после предлога 'к').
    """
    partner_id = db.get_partner(user_id)
    partner_gender = db.get_gender(partner_id)
    
    if partner_gender == "female":
        return "своей кошечке 🐈"
    return "своему котику 🐈‍⬛"

def get_text_by_gender(user_id, male_text, female_text):
    """Универсальная функция для выдачи текста в зависимости от пола САМОГО пользователя"""
    gender = db.get_gender(user_id)
    if gender == "female":
        return female_text
    return male_text

def send_no_partner_error(chat_id):
    """Универсальный обработчик ошибки: попытка действия без подключенного партнера"""
    status_text = get_text_by_gender(chat_id, "подключен", "подключена")
    bot.send_message(
        chat_id, 
        f"⚠️ Ошибка: ты ни к кому не {status_text}. Сначала подключись к котейке через команду /connect!"
    )

def send_menu(chat_id, text="Главное меню 👇"):
    """Универсальная функция для возврата пользователя в главное меню со сбросом состояний"""
    bot.send_message(chat_id, text, reply_markup=get_main_keyboard())


# ==========================================
# ОСНОВНЫЕ КОМАНДЫ НАВИГАЦИИ
# ==========================================

@bot.message_handler(commands=['help'])
def help_command(message):
    # Показываем клавиатуру только если у пользователя уже есть партнер
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

# Перехват нажатия на текстовую кнопку "❓ Помощь"
@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def help_button_handler(message):
    help_command(message)

@bot.message_handler(commands=['start'])
def start(message):
    gender = db.get_gender(message.chat.id)

    # Ветвление логики: если пользователь уже зарегистрирован (пол указан)
    if gender:
        if db.get_partner(message.chat.id):
            # Сценарий 1: Зарегистрирован и в паре
            status_text = get_text_by_gender(message.chat.id, "подключен", "подключена")
            target_text = get_target_partner_text(message.chat.id) 
            
            bot.send_message(
                message.chat.id, 
                f"С возвращением! Ты уже {status_text} к {target_text} 💕\n"
                "Используй меню внизу или /help для списка команд.",
                reply_markup=get_main_keyboard()
            )
        else:
            # Сценарий 2: Зарегистрирован, но пока одинок
            animal = "котик 🐈‍⬛" if gender == "male" else "кошечка 🐈"
            bot.send_message(
                message.chat.id, 
                f"С возвращением! В системе ты {animal}.\n"
                "Тебе осталось только подключиться к котейке через команду /connect!"
            )
        return

    # Сценарий 3: Новый пользователь (нужна регистрация)
    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}! Я бот для парочек 💕\n"
        "Для начала, скажи кто ты:",
        reply_markup=get_gender_keyboard()
    )

# Перехват нажатия на текстовую кнопку "🔄 Перезапуск"
@bot.message_handler(func=lambda message: message.text == "🔄 Перезапуск")
def start_button_handler(message):
    start(message)

@bot.message_handler(commands=['gender'])
def change_gender(message):
    # Убираем нижнюю клавиатуру, чтобы она не мешала inline-выбору
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

# Обработка нажатий на inline-кнопки выбора пола
@bot.callback_query_handler(func=lambda call: call.data.startswith("gender_"))
def save_gender(call):
    # Извлекаем пол из callback_data (gender_m -> male, gender_f -> female)
    gender = "male" if call.data == "gender_m" else "female"
    db.add_or_update_user(call.message.chat.id, gender, call.from_user.username)

    if db.get_partner(call.message.chat.id):
        # Если есть партнер — просто подтверждаем изменения
        bot.edit_message_text(
            "Готово! Твой пол успешно изменен ✨",
            call.message.chat.id, 
            call.message.message_id
        )
        send_menu(call.message.chat.id, "Меню посланий активно 👇")
    else:
        # Если партнера нет — выдаем инструкцию по подключению
        text = (
            "Отлично! Теперь ты можешь подключиться к котейке.\n\n"
            "Напиши /connect и введи ID или @username котейки\n"
            "Чтобы узнать свой ID, напиши /id\n"
            "Если забудешь команды, просто нажми /help"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['id'])
def id(message):
    # Команда для получения ID (с поддержкой Markdown для копирования по клику)
    markup = get_main_keyboard() if db.get_partner(message.chat.id) else None
    bot.send_message(message.chat.id, "Твой числовой ID (нажми на цифры ниже, чтобы скопировать):")
    bot.send_message(
        message.chat.id, 
        f"`{message.from_user.id}`", 
        parse_mode="Markdown",
        reply_markup=markup
    )


# ==========================================
# ЛОГИКА ПОДКЛЮЧЕНИЯ И ОТКЛЮЧЕНИЯ ПАР
# ==========================================

@bot.message_handler(commands=['connect'])
def connect(message):
    # Защита: нельзя подключиться, если связь уже установлена
    if db.get_partner(message.chat.id):
        status_text = get_text_by_gender(message.chat.id, "подключен", "подключена")
        target_text = get_target_partner_text(message.chat.id)
        
        bot.send_message(
            message.chat.id, 
            f"⚠️ Ты уже {status_text} к {target_text}! Сначала нужно разорвать текущую связь через команду /disconnect"
        )
        return

    # Переводим пользователя в режим ожидания ввода ID
    waiting_for_partner[message.chat.id] = True
    bot.send_message(message.chat.id, "Введи числовой ID котейки или никнейм (например, @nickname):")

# Обработчик текста, срабатывающий ТОЛЬКО если пользователь находится в состоянии waiting_for_partner
@bot.message_handler(func=lambda m: m.chat.id in waiting_for_partner)
def set_partner(message):
    # Защита от дурака: если прислали стикер/фото вместо текста
    if message.content_type != 'text':
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправь ID или никнейм текстом.")
        return

    # Умная отмена: прерываем ожидание, если нажали кнопку из главного меню
    if message.text in ["💌 Отправить послание", "❓ Помощь", "🔄 Перезапуск"]:
        waiting_for_partner.pop(message.chat.id, None)
        # Перенаправляем на соответствующие функции
        if message.text == "💌 Отправить послание":
            love(message)
        elif message.text == "❓ Помощь":
            help_command(message)
        else:
            start(message)
        return

    # Ручная отмена ожидания через вызов любой другой команды
    if message.text.startswith('/'):
        waiting_for_partner.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Ввод отменен.")
        return

    raw_input = message.text.strip()
    partner_id = None

    # Обработка ввода: поиск по @username или по числовому ID
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

    # Защита: блокируем попытку подключиться к самому себе
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

    # Проверка существования партнера в базе бота
    if db.get_gender(partner_id) is None:
        bot.send_message(
            message.chat.id, 
            "⚠️ Ошибка! Котейка еще не запустил(а) бота или не выбрал(а) пол.\n"
            "Попроси зайти в бота, нажать /start, выбрать пол и прислать тебе свой ID или ник!"
        )
        return 
            
    # Устанавливаем двустороннюю связь в БД
    db.link_partners(message.chat.id, partner_id)
    
    # Сбрасываем ВСЕ состояния ожидания для обоих пользователей (защита от багов)
    waiting_for_partner.pop(message.chat.id, None)
    waiting_for_partner.pop(partner_id, None) 
    waiting_for_message.pop(partner_id, None) 

    # Отправка уведомлений об успехе обоим партнерам
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
    # Проверка наличия партнера перед попыткой отключения
    if not db.get_partner(message.chat.id):
        send_no_partner_error(message.chat.id)
        return

    # Прячем Reply-кнопки, чтобы предотвратить случайные нажатия в процессе
    bot.send_message(
        message.chat.id, 
        "💔 Управление связью...", 
        reply_markup=types.ReplyKeyboardRemove()
    )

    # Формируем Inline-клавиатуру для подтверждения разрыва
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

# Обработка нажатий на inline-кнопки подтверждения отключения
@bot.callback_query_handler(func=lambda call: call.data.startswith("disconnect_"))
def process_disconnect(call):
    if call.data == "disconnect_no":
        # Пользователь передумал — отменяем процесс и возвращаем меню
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
            # Разрываем связь в базе данных
            db.unlink_partners(call.message.chat.id)
            
            # Удаляем сообщение с вопросом "Ты уверен?"
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
            # Уведомляем инициатора
            bot.send_message(
                call.message.chat.id,
                "Связь разорвана. Вы больше не подключены друг к другу. 💔",
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            # Уведомляем бывшего партнера
            initiator_text = get_text_by_gender(call.message.chat.id, "Твой котик разорвал", "Твоя кошечка разорвала")
            bot.send_message(
                partner_id, 
                f"💔 {initiator_text} связь. Вы больше не подключены друг к другу.",
                reply_markup=types.ReplyKeyboardRemove()
            )
        else:
            # Обработка race condition (если партнер уже нажал отключиться секундой ранее)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Связь уже была разорвана."
            )


# ==========================================
# СИСТЕМА ЛЮБОВНЫХ ПОСЛАНИЙ (ЧЕРНОВИКИ)
# ==========================================

@bot.message_handler(commands=['love'])
def love(message):
    if db.get_partner(message.chat.id):
        # Переводим пользователя в состояние ожидания контента
        waiting_for_message[message.chat.id] = True
        bot.send_message(
            message.chat.id, 
            "Пришли мне послание (текст, фото, стикер, голос или кружочек) 💌\n"
            "Чтобы отправить фото с текстом, просто добавь описание к картинке!", 
            reply_markup=types.ReplyKeyboardRemove() # Прячем меню на время ввода
        )
    else:
        send_no_partner_error(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "💌 Отправить послание")
def love_button_handler(message):
    love(message)

# Обработчик любых типов сообщений для создания черновика
@bot.message_handler(
    func=lambda m: m.chat.id in waiting_for_message, 
    content_types=['text', 'photo', 'voice', 'video', 'video_note', 'document', 'sticker', 'audio', 'animation']
)
def receive_love_draft(message):
    # Умная отмена: если пользователь передумал и нажал кнопку главного меню
    if message.content_type == 'text' and message.text in ["💌 Отправить послание", "❓ Помощь", "🔄 Перезапуск"]:
        waiting_for_message.pop(message.chat.id, None)
        if message.text == "💌 Отправить послание":
            love(message)
        elif message.text == "❓ Помощь":
            help_command(message)
        else:
            start(message)
        return

    # Отмена через команду
    if message.content_type == 'text' and message.text.startswith('/'):
        waiting_for_message.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    # Завершаем режим ожидания и сохраняем ID сообщения-исходника в черновик
    waiting_for_message.pop(message.chat.id, None)
    draft_messages[message.chat.id] = message.message_id

    # Создаем меню подтверждения отправки
    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("Отправить 💌", callback_data="draft_send")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="draft_cancel")
    markup.add(btn_cancel, btn_send) 

    # Используем reply_to, чтобы визуально привязать кнопки к черновику
    bot.reply_to(message, "Послание готово. Отправляем?", reply_markup=markup)

# Обработка кнопок подтверждения отправки черновика
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
        
        # Проверка целостности данных: если бот перезапускался или партнер пропал
        if not message_id or not partner_id:
            bot.edit_message_text("⚠️ Ошибка: черновик не найден или бот отключился.", user_id, call.message.message_id)
            send_menu(user_id)
            return
            
        # 1. Отправляем партнеру "шапку" сообщения
        sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
        bot.send_message(partner_id, f"💌 Новое послание от {sender_text}:")
        
        # 2. Магия copy_message: полностью копирует исходное сообщение (стикер/фото/кружок) партнеру
        bot.copy_message(partner_id, user_id, message_id)

        # 3. Закрываем черновик у отправителя
        bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
        send_menu(user_id)
        draft_messages.pop(user_id, None)


# ==========================================
# ТОЧКА ВХОДА (ЗАПУСК БОТА)
# ==========================================

if __name__ == "__main__":
    db.init_db() # Инициализация структуры базы данных при старте
    print("Бот запущен и готов к работе...")
    while True:
        try:
            # none_stop=True предотвращает остановку при ошибках сети
            bot.polling(none_stop=True, timeout=90) 
        except Exception as e:
            # Защита от падений API Telegram
            print(f"⚠️ Ошибка связи с Telegram. Жду 5 секунд... Ошибка: {e}")
            time.sleep(5)