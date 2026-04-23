from config import bot
from telebot import types
import time
import db 
from config import bot, ADMIN_IDS

# --- ГЛОБАЛЬНЫЕ СОСТОЯНИЯ ---
# Словари для временного хранения данных в оперативной памяти бота.
# Ключ — это chat_id пользователя, значение — статус или данные.
waiting_for_partner = {} # Флаг: пользователь находится в процессе ввода ID/ника партнера
waiting_for_message = {} # Флаг: пользователь пишет любовное послание
draft_messages = {}      # Хранилище ID сообщений (черновиков) до их подтверждения отправки
waiting_for_broadcast = {} # Флаг: админ находится в режиме рассылки
broadcast_drafts = {}    # Хранилище ID сообщений для рассылки
pending_requests_sender = {}   # Временное хранилище для шага 1 (Отправить/Отменить)
pending_requests_receiver = {} # Временное хранилище для шага 2 (Принять/Отклонить)

# ==========================================
# ФУНКЦИИ-ПОМОЩНИКИ (ИНТЕРФЕЙС И ТЕКСТЫ)
# ==========================================

def get_main_keyboard(user_id):
    """Создает умную клавиатуру: одиноким — 2 кнопки, влюбленным — 3"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    btn_help = types.KeyboardButton("❓ Помощь")
    btn_start = types.KeyboardButton("🔄 Перезапуск")

    # Если есть партнер — добавляем кнопку послания
    if db.get_partner(user_id):
        btn_love = types.KeyboardButton("💌 Отправить послание")
        markup.row(btn_love)

    # Кнопки навигации будут у всех и всегда
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
    bot.send_message(chat_id, text, reply_markup=get_main_keyboard(chat_id))


# ==========================================
# ОСНОВНЫЕ КОМАНДЫ НАВИГАЦИИ
# ==========================================

@bot.message_handler(commands=['help'])
def help_command(message):
    markup = get_main_keyboard(message.chat.id)
    
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
    
    # Проверка прав: если пишет админ, добавляем скрытую команду
    if message.chat.id in ADMIN_IDS:
        help_text += (
            "\n\n🛠 *Команды разработчика:*\n"
            "/broadcast — Массовая рассылка\n"
            "/stats — Статистика пользователей" 
        )

    bot.send_message(message.chat.id, help_text, parse_mode="Markdown", reply_markup=markup)

# Перехват нажатия на текстовую кнопку "❓ Помощь"
@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def help_button_handler(message):
    help_command(message)

@bot.message_handler(commands=['start'])
def start(message):
    # СБРОС ЗАВИСШИХ СОСТОЯНИЙ (если юзер очистил историю и перезапустил бота)
    waiting_for_partner.pop(message.chat.id, None)
    waiting_for_message.pop(message.chat.id, None)
    draft_messages.pop(message.chat.id, None)

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
                reply_markup=get_main_keyboard(message.chat.id)
            )
        else:
            # Сценарий 2: Зарегистрирован, но пока одинок
            animal = "котик 🐈‍⬛" if gender == "male" else "кошечка 🐈"
            bot.send_message(
                message.chat.id, 
                f"С возвращением! В системе ты {animal}.\n"
                "Тебе осталось только подключиться к котейке через команду /connect!",
                reply_markup=get_main_keyboard(message.chat.id)
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
        send_menu(call.message.chat.id, "Меню навигации активно 👇")

@bot.message_handler(commands=['id'])
def id(message):
    # Команда для получения ID (с поддержкой Markdown для копирования по клику)
    markup = get_main_keyboard(message.chat.id)
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
    
    # Создаем инлайн-кнопку для отмены
    markup = types.InlineKeyboardMarkup()
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_connect")
    markup.add(btn_cancel)

    bot.send_message(
        message.chat.id, 
        "Введи числовой ID котейки или никнейм (например, @nickname):",
        reply_markup=markup
    )

# Обработка нажатия на кнопку "Отменить" при вводе ID партнера
@bot.callback_query_handler(func=lambda call: call.data == "cancel_connect")
def cancel_connect_callback(call):
    """Срабатывает, если юзер передумал вводить ID и нажал Отменить"""
    user_id = call.message.chat.id
    waiting_for_partner.pop(user_id, None)
    
    # Меняем текст сообщения, убирая кнопку
    bot.edit_message_text("Ввод отменен 🛑", user_id, call.message.message_id)
    send_menu(user_id, "Главное меню 👇")

# Обработчик текста, срабатывающий ТОЛЬКО если пользователь находится в состоянии waiting_for_partner
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
        self_word = get_text_by_gender(message.chat.id, male_text="самому себе", female_text="самой себе")
        bot.send_message(message.chat.id, f"Нельзя подключиться к {self_word}! Введи ID или ник котейки:")
        return

    if db.get_gender(partner_id) is None:
        bot.send_message(
            message.chat.id, 
            "⚠️ Ошибка! Котейка еще не запустил(а) бота или не выбрал(а) пол.\n"
            "Попроси зайти в бота, нажать /start, выбрать пол и прислать тебе свой ID или ник!"
        )
        return 
        
    if db.get_partner(partner_id):
        bot.send_message(message.chat.id, "⚠️ У этого котейки уже есть пара! Подключение невозможно.")
        return
            
    # НОВАЯ ЛОГИКА: Сохраняем во временный словарь и выдаем кнопки инициатору
    waiting_for_partner.pop(message.chat.id, None)
    pending_requests_sender[message.chat.id] = partner_id

    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("Отправить запрос 💌", callback_data="req_send")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="req_cancel")
    markup.add(btn_cancel, btn_send)

    bot.reply_to(message, "Котейка найден(а)! Отправить запрос на подключение?", reply_markup=markup)

# --- ЭТАП 1: Инициатор решает, отправить запрос или нет ---
@bot.callback_query_handler(func=lambda call: call.data in ["req_send", "req_cancel"])
def process_request_step1(call):
    user_id = call.message.chat.id
    
    if call.data == "req_cancel":
        pending_requests_sender.pop(user_id, None)
        bot.edit_message_text("Запрос отменен 🛑", user_id, call.message.message_id)
        send_menu(user_id, "Главное меню 👇")
        return

    if call.data == "req_send":
        target_id = pending_requests_sender.pop(user_id, None)
        
        if not target_id:
            bot.edit_message_text("⚠️ Ошибка: данные для подключения потеряны.", user_id, call.message.message_id)
            return

        # Переносим запрос в ожидание ответа от второго пользователя
        pending_requests_receiver[target_id] = user_id

        # Формируем сообщение для второго котейки
        sender_text = get_text_by_gender(user_id, "котик 🐈‍⬛", "кошечка 🐈")
        markup = types.InlineKeyboardMarkup()
        btn_accept = types.InlineKeyboardButton("Принять 💕", callback_data="partner_accept")
        btn_decline = types.InlineKeyboardButton("Отклонить ❌", callback_data="partner_decline")
        markup.add(btn_decline, btn_accept)

        try:
            bot.send_message(
                target_id, 
                f"💌 К тебе хочет подключиться {sender_text}!\nЧто ответим?",
                reply_markup=markup
            )
            bot.edit_message_text("Запрос отправлен! Ждем ответа... ⏳", user_id, call.message.message_id)
        except:
            bot.edit_message_text("⚠️ Ошибка: не удалось отправить запрос. Возможно, пользователь заблокировал бота.", user_id, call.message.message_id)

# --- ЭТАП 2: Второй пользователь принимает или отклоняет запрос ---
@bot.callback_query_handler(func=lambda call: call.data in ["partner_accept", "partner_decline"])
def process_request_step2(call):
    target_id = call.message.chat.id # Тот, кому прислали запрос
    requester_id = pending_requests_receiver.pop(target_id, None) # Тот, кто отправлял

    if not requester_id:
        bot.edit_message_text("⚠️ Этот запрос уже устарел или был отменен.", target_id, call.message.message_id)
        return

    if call.data == "partner_decline":
        bot.edit_message_text("Запрос отклонен 🛑", target_id, call.message.message_id)
        bot.send_message(requester_id, "💔 Твой запрос на подключение был отклонен.")
        return

    if call.data == "partner_accept":
        # Финальная проверка перед созданием связи (вдруг кто-то уже нашел пару за это время)
        if db.get_partner(target_id) or db.get_partner(requester_id):
            bot.edit_message_text("⚠️ Ошибка: кто-то из вас уже нашел пару!", target_id, call.message.message_id)
            bot.send_message(requester_id, "⚠️ Ошибка подключения: кто-то из вас уже в паре.")
            return

        # Устанавливаем двустороннюю связь в БД
        db.link_partners(requester_id, target_id)
        
        # Очищаем все возможные временные состояния
        waiting_for_partner.pop(requester_id, None) 
        waiting_for_message.pop(requester_id, None) 

        bot.edit_message_text("Соединение установлено! ✨", target_id, call.message.message_id)

        # Уведомляем инициатора (User A)
        action_text_a = get_text_by_gender(requester_id, "подключен", "подключена")
        target_text_a = get_text_by_gender(target_id, "к своему котику! 🐈‍⬛", "к своей кошечке! 🐈")
        bot.send_message(
            requester_id, 
            f"Ура! Твой запрос принят. Ты {action_text_a} {target_text_a} 💕",
            reply_markup=get_main_keyboard(requester_id)
        )

        # Уведомляем принявшего (User B)
        notification_text_b = get_text_by_gender(requester_id, "К тебе подключился твой котик! 🐈‍⬛", "К тебе подключилась твоя кошечка! 🐈")
        bot.send_message(
            target_id, 
            notification_text_b,
            reply_markup=get_main_keyboard(target_id)
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
# ПАНЕЛЬ АДМИНИСТРАТОРА (РАССЫЛКА НОВОСТЕЙ)
# ==========================================

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    """
    Инициализация режима рассылки. 
    Доступно только пользователям, чей ID есть в списке ADMIN_IDS.
    """
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "Я не знаю такую команду 🥺")
        return

    # Включаем режим ожидания контента для рассылки
    waiting_for_broadcast[message.chat.id] = True
    bot.send_message(
        message.chat.id,
        "📣 *Режим рассылки*\n\nПришли мне сообщение (текст, фото или видео), которое увидят все.\n"
        "Кнопки управления появятся после отправки контента.",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove() # Убираем меню, чтобы не мешало вводу
    )

@bot.message_handler(
    func=lambda m: m.chat.id in waiting_for_broadcast, 
    content_types=['text', 'photo', 'voice', 'video', 'video_note', 'document', 'sticker', 'audio', 'animation']
)
def receive_broadcast_draft(message):
    """
    Ловит контент для рассылки, сохраняет его ID в черновики 
    и выводит инлайн-кнопки для подтверждения.
    """
    waiting_for_broadcast.pop(message.chat.id, None)
    broadcast_drafts[message.chat.id] = message.message_id

    # Создаем меню управления рассылкой
    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("Отправить всем 📣", callback_data="bc_send")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="bc_cancel")
    
    # Кнопка отмены слева, кнопка подтверждения справа
    markup.add(btn_cancel, btn_send)

    bot.reply_to(message, "Контент для рассылки получен. Начинаем?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("bc_"))
def process_broadcast_callback(call):
    """
    Обрабатывает финальное решение админа: запустить рассылку или удалить черновик.
    """
    admin_id = call.message.chat.id
    
    # Сценарий: Отмена
    if call.data == "bc_cancel":
        broadcast_drafts.pop(admin_id, None)
        bot.edit_message_text("Рассылка отменена 🛑", admin_id, call.message.message_id)
        send_menu(admin_id) # Возвращаем пользователя в главное меню
        return

    # Сценарий: Подтверждение отправки
    if call.data == "bc_send":
        draft_id = broadcast_drafts.get(admin_id)
        if not draft_id:
            bot.edit_message_text("⚠️ Ошибка: черновик потерян.", admin_id, call.message.message_id)
            send_menu(admin_id)
            return

        users = db.get_all_users()
        success_count = 0
        
        bot.edit_message_text(f"⏳ Рассылка запущена для {len(users)} пользователей...", admin_id, call.message.message_id)

        for user_id in users:
            # Не отправляем рассылку самому себе
            if user_id == admin_id:
                continue
                
            try:
                # ПРАВКА: Перед основным контентом отправляем заголовок от разработчика
                bot.send_message(
                    user_id, 
                    "📢 <b>Важное сообщение от разработчика:</b>", 
                    parse_mode="HTML"
                )
                
                # Копируем само сообщение черновика
                bot.copy_message(user_id, admin_id, draft_id)
                success_count += 1
                
                # Спим 0.05 сек, чтобы не получить бан от Telegram за слишком частую отправку
                time.sleep(0.05) 
            except:
                # Если пользователь заблокировал бота, просто пропускаем его
                pass

        # Итоговый отчет для админа
        bot.send_message(
            admin_id, 
            f"✅ *Рассылка завершена!*\nДоставлено: {success_count}",
            parse_mode="Markdown"
        )
        send_menu(admin_id)
        broadcast_drafts.pop(admin_id, None)

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    """
    Выводит статистику бота.
    Доступно только пользователям, чей ID есть в списке ADMIN_IDS.
    """
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "Я не знаю такую команду 🥺")
        return

    # Получаем данные из базы
    total_users, total_pairs = db.get_stats()
    
    # Формируем красивое сообщение
    text = (
        "📊 *Статистика SoulLinky*\n\n"
        f"👥 Всего котеек в базе: `{total_users}`\n"
        f"💕 Образовано пар: `{total_pairs}`"
    )
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ==========================================
# СИСТЕМА ЛЮБОВНЫХ ПОСЛАНИЙ (ЧЕРНОВИКИ)
# ==========================================

@bot.message_handler(commands=['love'])
def love(message):
    """Инициализация процесса отправки любовного послания"""
    if db.get_partner(message.chat.id):
        # Включаем состояние ожидания сообщения
        waiting_for_message[message.chat.id] = True
        
        # Создаем инлайн-кнопку для отмены
        markup = types.InlineKeyboardMarkup()
        btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_love")
        markup.add(btn_cancel)

        bot.send_message(
            message.chat.id, 
            "Пришли мне послание (текст, фото, стикер, голос или кружочек) 💌\n"
            "Чтобы отправить фото с текстом, просто добавь описание к картинке!", 
            reply_markup=markup # Показываем кнопку отмены
        )
    else:
        send_no_partner_error(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "💌 Отправить послание")
def love_button_handler(message):
    love(message)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_love")
def cancel_love_callback(call):
    """Срабатывает, если юзер нажал 'Отменить' в процессе подготовки послания"""
    user_id = call.message.chat.id
    
    # Убираем пользователя из режима ожидания сообщения
    waiting_for_message.pop(user_id, None)
    
    # Редактируем сообщение, чтобы убрать кнопку и текст запроса
    bot.edit_message_text("Отправка послания отменена 🛑", user_id, call.message.message_id)
    
    # Возвращаем главное меню
    send_menu(user_id, "Главное меню 👇")

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
# ЛОВУШКА ДЛЯ СЛУЧАЙНЫХ СООБЩЕНИЙ (ЕСЛИ ОЧИСТИЛИ ИСТОРИЮ)
# ==========================================

@bot.message_handler(content_types=['text', 'photo', 'voice', 'video', 'video_note', 'document', 'sticker', 'audio', 'animation'])
def catch_all_messages(message):
    """Сработает, если юзер написал что-то непонятное или очистил историю"""
    
    # Если юзер есть в базе и у него есть пара — просто возвращаем кнопки
    if db.get_partner(message.chat.id):
        send_menu(message.chat.id, "Я не знаю такую команду 🥺\nНо вот твоё главное меню 👇")
        
    # Если пары нет (неважно, выбран ли пол или юзер вообще новый),
    # отправляем его в функцию start — она сама всё проверит и выдаст нужный текст!
    else:
        start(message)

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