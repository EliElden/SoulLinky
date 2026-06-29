from telebot import types
import db 
from config import bot, ADMIN_IDS
from datetime import datetime
import threading
from PIL import Image, ImageDraw, ImageFont
import io
import tempfile
import os
import random
import time
import sys


# --- ГЛОБАЛЬНЫЕ СОСТОЯНИЯ ---
# Словари для временного хранения данных в оперативной памяти бота.
# Ключ — это chat_id пользователя, значение — статус или данные.
waiting_for_partner = {} # Флаг: пользователь находится в процессе ввода ID/ника партнера
waiting_for_message = {} # Флаг: пользователь пишет любовное послание
draft_messages = {}      # Хранилище ID сообщений (черновиков) до их подтверждения отправки
waiting_for_broadcast = {} # Флаг: админ находится в режиме рассылки
broadcast_drafts = {}    # Хранилище ID сообщений для рассылки
pending_requests_sender = {}   # Временное хранилище (Отправить/Отменить)
pending_requests_receiver = {} # Временное хранилище (Принять/Отклонить)
waiting_for_block = {}   # Ожидание ID для блокировки
waiting_for_unblock = {} # Ожидание ID для разблокировки
# Состояния для добавления важной даты
waiting_for_date_title = {}      # ожидание ввода названия
waiting_for_date_value = {}      # ожидание ввода даты (хранит название)
waiting_for_date_type = {}       # ожидание выбора типа (хранит (название, дата))
waiting_for_date_remind = {}     # ожидание выбора срока (хранит (название, дата, is_annual))
waiting_for_date_partner = {}    # хранит partner_id для текущей сессии
# Состояния для общего вишлиста
waiting_for_wish_type = {}
waiting_for_wish_title = {}
waiting_for_wish_description = {}
waiting_for_delwish_id = {}
waiting_for_deldate_id = {}
waiting_for_wish_confirm = {}   # данные для подтверждения добавления вишлиста
waiting_for_date_confirm = {}   # данные для подтверждения добавления даты

# ==========================================
# ФУНКЦИИ-ПОМОЩНИКИ (ИНТЕРФЕЙС И ТЕКСТЫ)
# ==========================================
def get_main_keyboard(user_id):
    """Создает умную клавиатуру: одиноким — 2 кнопки, влюбленным — 3 (и более)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    btn_help = types.KeyboardButton("❓ Помощь")
    btn_start = types.KeyboardButton("🔄 Перезапуск")

    if db.get_partner(user_id):
        btn_love = types.KeyboardButton("💌 Послание")
        btn_wishlist = types.KeyboardButton("🎁 Вишлист")
        btn_dates = types.KeyboardButton("📅 Даты")
        btn_streak = types.KeyboardButton("🔥 Серия")
        btn_mood = types.KeyboardButton("🎭 Настроение")
        btn_timeout = types.KeyboardButton("🛑 В угол") 
        
        # Компонуем по рядам для красоты
        markup.row(btn_love, btn_wishlist)
        markup.row(btn_dates, btn_streak)
        markup.row(btn_mood, btn_timeout) 

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

def get_user_display_name(user_id):
    """
    Умная функция для отображения имени.
    Возвращает @username (если он есть в базе), либо числовой ID.
    """
    username = db.get_username(user_id)
    if username:
        return f"@{username}"
    return str(user_id)

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
        "/disconnect — Отключиться от котейки \n"
        "/love — Отправить послание котейке \n"
        "/streak — Показать текущую серию \n"
        "/timeout — Отправить подумать над поведением 🛑\n\n"
        "📅 *Важные даты:*\n"
        "/adddate — Добавить общую важную дату\n"
        "/mydates — Список всех важных дат\n"
        "/deldate — Удалить важную дату\n\n"
        "💕 *Вишлист пары:*\n"
        "/wishlist — Посмотреть общий вишлист\n"
        "/addwish — Добавить подарок, свидание или желание\n"
        "/delwish — Удалить элемент вишлиста\n"
        "/mood — Отметить, как ты себя чувствуешь\n\n"
        "🛡 *Безопасность:*\n"
        "/block — Заблокировать котейку\n"
        "/unblock — Разблокировать котейку\n"
        "/blacklist — Мой черный список"
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

    # Умная отмена: прерываем ожидание, если нажали кнопку из главного меню
    if message.text in ["💌 Послание", "❓ Помощь", "🔄 Перезапуск"]:
        waiting_for_partner.pop(message.chat.id, None)
        if message.text == "💌 Послание":
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
        self_word = get_text_by_gender(message.chat.id, male_text="самому себе", female_text="самой себе")
        bot.send_message(message.chat.id, f"Нельзя подключиться к {self_word}! Введи ID или ник котейки:")
        return

    # Проверка существования партнера в базе бота (тут оставляем (а), так как пол партнера неизвестен)
    if db.get_gender(partner_id) is None:
        bot.send_message(
            message.chat.id, 
            "⚠️ Ошибка! Котейка еще не запустил(а) бота или не выбрал(а) пол.\n"
            "Попроси зайти в бота, нажать /start, выбрать пол и прислать тебе свой ID или ник!"
        )
        return 
        
    # Защита: у партнера уже есть пара
    if db.get_partner(partner_id):
        bot.send_message(message.chat.id, "⚠️ У котейки уже есть пара! Подключение невозможно.")
        return
        
    # --- ПРОВЕРКИ ЧЕРНОГО СПИСКА ---
    # 1. Если партнер добавил нас в ЧС
    if db.is_blocked(partner_id, message.chat.id):
        bot.send_message(message.chat.id, "⚠️ Котейка не найден(а) или ограничил(а) к себе доступ.")
        return

    # 2. Если мы сами добавили партнера в ЧС (персонализируем)
    if db.is_blocked(message.chat.id, partner_id):
        action_word = get_text_by_gender(message.chat.id, "заблокировал", "заблокировала")
        bot.send_message(message.chat.id, f"⚠️ Ты {action_word} котейку! Сначала разблокируй через /unblock.")
        return
    # -------------------------------
            
    # Сохраняем во временный словарь и выдаем кнопки инициатору
    waiting_for_partner.pop(message.chat.id, None)
    pending_requests_sender[message.chat.id] = partner_id

    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("Отправить запрос 💌", callback_data="req_send")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="req_cancel")
    markup.add(btn_cancel, btn_send)

    # Узнаем пол партнера и подбираем правильное слово
    found_text = get_text_by_gender(partner_id, "Котик найден! 🐈‍⬛", "Кошечка найдена! 🐈")

    bot.reply_to(message, f"{found_text} Отправить запрос на подключение?", reply_markup=markup)

# --- Инициатор решает, отправить запрос или нет ---
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
        sender_name = get_user_display_name(user_id) # Достаем ник или ID
        
        markup = types.InlineKeyboardMarkup()
        btn_accept = types.InlineKeyboardButton("Принять 💕", callback_data="partner_accept")
        btn_decline = types.InlineKeyboardButton("Отклонить ❌", callback_data="partner_decline")
        markup.add(btn_decline, btn_accept)

        try:
            bot.send_message(
                target_id, 
                f"💌 К тебе хочет подключиться {sender_text} {sender_name}!\nЧто ответим?",
                reply_markup=markup
            )
            bot.edit_message_text("Запрос отправлен! Ждем ответа... ⏳", user_id, call.message.message_id)
        except:
            bot.edit_message_text("⚠️ Ошибка: не удалось отправить запрос. Возможно, котейка заблокировал(а) бота.", user_id, call.message.message_id)

# Второй пользователь принимает или отклоняет запрос ---
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
        
        # --- ПРОВЕРКА НА УГОЛ ---
        timeout = db.get_timeout(message.chat.id)
        if timeout:
            time_left = int((timeout - datetime.now()).total_seconds() / 60) + 1
            bot.send_message(message.chat.id, f"🛑 Тихо! Тебя отправили в угол думать над своим поведением.\nОсталось сидеть: {time_left} мин. 🤫")
            return
        # ------------------------------

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

@bot.message_handler(func=lambda message: message.text == "💌 Послание")
def love_button_handler(message):
    love(message)

@bot.message_handler(func=lambda message: message.text == "🎁 Вишлист")
def wishlist_menu_handler(message):
    show_wishlist_menu(message.chat.id)

def show_wishlist_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn_view = types.InlineKeyboardButton("📋 Просмотреть", callback_data="wishlist_view")
    btn_add = types.InlineKeyboardButton("➕ Добавить", callback_data="wishlist_add")
    btn_del = types.InlineKeyboardButton("❌ Удалить", callback_data="wishlist_del")
    markup.add(btn_view, btn_add)
    markup.add(btn_del)
    bot.send_message(chat_id, "💕 Меню вишлиста:", reply_markup=markup)

def show_dates_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn_view = types.InlineKeyboardButton("📋 Просмотреть", callback_data="dates_view")
    btn_add = types.InlineKeyboardButton("➕ Добавить", callback_data="dates_add")
    btn_del = types.InlineKeyboardButton("❌ Удалить", callback_data="dates_del")
    markup.add(btn_view, btn_add)
    markup.add(btn_del)
    bot.send_message(chat_id, "📅 Меню важных дат:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📅 Даты")
def dates_menu_handler(message):
    show_dates_menu(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "🔥 Серия")
def streak_button_handler(message):
    streak_command(message)

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

@bot.callback_query_handler(func=lambda call: call.data in ["wishlist_view", "wishlist_add", "wishlist_del", "dates_view", "dates_add", "dates_del"])
def process_wishlist_dates_menu(call):
    user_id = call.message.chat.id
    if call.data == "wishlist_view":
        wishlist(call.message)  # вызываем существующую функцию показа списка
        bot.answer_callback_query(call.id)
    elif call.data == "wishlist_add":
        add_wish_start(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == "wishlist_del":
        # запускаем процесс удаления (интерактивно)
        delwish_interactive(user_id)
        bot.answer_callback_query(call.id)
    elif call.data == "dates_view":
        list_dates(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == "dates_add":
        add_date_start(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == "dates_del":
        deldate_interactive(user_id)
        bot.answer_callback_query(call.id)

# Обработчик любых типов сообщений для создания черновика
@bot.message_handler(
    func=lambda m: m.chat.id in waiting_for_message, 
    content_types=['text', 'photo', 'voice', 'video', 'video_note', 'document', 'sticker', 'audio', 'animation']
)
def receive_love_draft(message):
    # Умная отмена: если пользователь передумал и нажал кнопку главного меню
    if message.content_type == 'text' and message.text in ["💌 Послание", "❓ Помощь", "🔄 Перезапуск"]:
        waiting_for_message.pop(message.chat.id, None)
        if message.text == "💌 Послание":
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
    btn_send_cat = types.InlineKeyboardButton("С котёнком 🐱", callback_data="draft_send_cat")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="draft_cancel")
    markup.add(btn_send, btn_send_cat)
    markup.add(btn_cancel)

    # Используем reply_to, чтобы визуально привязать кнопки к черновику
    bot.reply_to(message, "Послание готово. Отправляем?", reply_markup=markup)

# Обработка кнопок подтверждения отправки черновика
@bot.callback_query_handler(func=lambda call: call.data in ["draft_send", "draft_cancel"])
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

        db.update_streak(user_id, partner_id) #обновить серию

        # 3. Закрываем черновик у отправителя
        bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
        send_menu(user_id)
        draft_messages.pop(user_id, None)

#Обработчик callback для послания с котёнком
@bot.callback_query_handler(func=lambda call: call.data == "draft_send_cat")
def process_draft_cat(call):
    user_id = call.message.chat.id
    message_id = draft_messages.get(user_id)
    partner_id = db.get_partner(user_id)

    if not message_id or not partner_id:
        bot.edit_message_text("⚠️ Ошибка: черновик не найден или бот отключился.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    # 1. Получение текста (пересылаем себе, затем удаляем копию)
    try:
        forwarded = bot.forward_message(user_id, user_id, message_id)
        # Сразу удаляем пересланное, чтобы скрыть от отправителя
        bot.delete_message(user_id, forwarded.message_id)

        if forwarded.content_type == 'text':
            text = forwarded.text.strip()
        else:
            # Не текст – отправляем как обычное послание
            bot.send_message(user_id, "⚠️ Наложение текста на картинку поддерживается только для текстовых сообщений. Отправляю обычное послание.")
            sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
            bot.send_message(partner_id, f"💌 Новое послание от {sender_text}:")
            bot.copy_message(partner_id, user_id, message_id)
            bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
            draft_messages.pop(user_id, None)
            send_menu(user_id)
            return
    except Exception as e:
        bot.edit_message_text(f"⚠️ Ошибка при получении черновика: {e}", user_id, call.message.message_id)
        send_menu(user_id)
        return

    if not text:
        text = "🐱 Мур-мур!"

    # 2. Загрузка локального изображения
    cat_bytes = get_local_cat_image()
    if cat_bytes is None:
        bot.edit_message_text("⚠️ Не удалось загрузить картинку кота. Отправляю обычное послание.", user_id, call.message.message_id)
        sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
        bot.send_message(partner_id, f"💌 Новое послание от {sender_text}:")
        bot.copy_message(partner_id, user_id, message_id)
        bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
        draft_messages.pop(user_id, None)
        send_menu(user_id)
        return

    # 3. Генерация мема с улучшенной обводкой
    meme_bytes = generate_cat_meme_optimized(cat_bytes, text)
    if meme_bytes is None:
        bot.edit_message_text("⚠️ Ошибка при создании картинки. Отправляю обычное послание.", user_id, call.message.message_id)
        sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
        bot.send_message(partner_id, f"💌 Новое послание от {sender_text}:")
        bot.copy_message(partner_id, user_id, message_id)
        bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
        draft_messages.pop(user_id, None)
        send_menu(user_id)
        return

    # 4. Отправка готового изображения партнёру
    sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
    bot.send_message(partner_id, f"💌 Новое послание от {sender_text} (с котёнком 🐱):")
    bot.send_photo(partner_id, photo=io.BytesIO(meme_bytes))

    # 5. Завершение: обновляем клавиатуру без лишнего текста
    bot.edit_message_text("✅ Отправлено с котёнком!", user_id, call.message.message_id)
    bot.send_message(user_id, " ", reply_markup=get_main_keyboard(user_id))  # невидимый пробел
    draft_messages.pop(user_id, None)

#Альтернатива - получаем локальное изображение котика
def get_local_cat_image():
    """
    Возвращает байты случайного локального изображения котика.
    Если папка пуста или файлы недоступны, возвращает None.
    """
    folder = os.path.join(os.path.dirname(__file__), 'cat_images')
    if not os.path.exists(folder):
        return None

    # Получаем список файлов изображений (можно расширить список расширений)
    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
    files = [f for f in os.listdir(folder) if f.lower().endswith(valid_extensions)]

    if not files:
        return None

    chosen = random.choice(files)
    file_path = os.path.join(folder, chosen)

    try:
        with open(file_path, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"Ошибка чтения локального изображения: {e}")
        return None

# Серия сообщений подряд
@bot.message_handler(commands=['streak'])
def streak_command(message):
    """Показывает текущую серию (количество дней подряд, когда оба отправляли послания)."""
    partner_id = db.get_partner(message.chat.id)
    if not partner_id:
        bot.send_message(message.chat.id, "❌ У тебя нет пары, чтобы смотреть серию.")
        return

    streak = db.get_streak(message.chat.id, partner_id)
    if streak == 0:
        bot.send_message(message.chat.id, "💔 У вас пока нет серии. Отправляйте друг другу послания каждый день!")
    else:
        bot.send_message(message.chat.id, f"🔥 Ваша серия: {streak} дней подряд! Продолжайте в том же духе!")


# ==========================================
# ФУНКЦИИ ДЛЯ ГЕНЕРАЦИИ КОТО-ПОСЛАНИЙ
# ==========================================

def get_random_cat_image():
    """
    Использует только локальные изображения из папки cat_images.
    """
    return get_local_cat_image()


def generate_cat_meme_optimized(image_bytes, text, max_size=(1200, 1200), quality=75):
    if image_bytes is None:
        return None

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image.thumbnail(max_size, Image.LANCZOS)

        draw = ImageDraw.Draw(image)

        # Поиск шрифта
        font = None
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "C:\\Windows\\Fonts\\Arial.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, 36)
                    break
                except:
                    continue
        if font is None:
            font = ImageFont.load_default()

        # Разбиваем на строки
        max_chars = 30
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line + " " + word) <= max_chars:
                current_line += (" " + word) if current_line else word
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        img_width, img_height = image.size
        line_height = 50
        total_text_height = len(lines) * line_height
        y = (img_height - total_text_height) // 2

        for line in lines:
            # Определяем ширину текста
            try:
                if hasattr(draw, 'textbbox'):
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                else:
                    text_width, _ = draw.textsize(line, font=font)
            except:
                text_width = len(line) * 20
            x = (img_width - text_width) // 2

            # Рисуем текст с обводкой
            draw.text(
                (x, y),
                line,
                font=font,
                fill="white",
                stroke_width=2,
                stroke_fill="black"
            )
            y += line_height

        img_bytes = io.BytesIO()
        image.save(img_bytes, format='JPEG', quality=quality)
        img_bytes.seek(0)
        return img_bytes.getvalue()

    except Exception as e:
        # Можно закомментировать, если не нужен вывод ошибок
        print(f"Ошибка в generate_cat_meme_optimized: {e}")
        return None

# ==========================================
# ШУТОЧНЫЙ ТАЙМАУТ (В УГОЛ!)
# ==========================================

@bot.message_handler(commands=['timeout'])
def timeout_command(message):
    user_id = message.chat.id
    partner_id = db.get_partner(user_id)
    
    if not partner_id:
        bot.send_message(user_id, "❌ У тебя нет пары. Кого наказывать-то?")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("На 5 минут ⏱", callback_data="timeout_5"),
        types.InlineKeyboardButton("На 15 минут ⏳", callback_data="timeout_15")
    )
    markup.add(
        types.InlineKeyboardButton("На 1 час 🕰", callback_data="timeout_60"),
        types.InlineKeyboardButton("Простить (снять) 😇", callback_data="timeout_0")
    )
    markup.add(types.InlineKeyboardButton("Любезно передумать ❌", callback_data="timeout_cancel"))

    bot.send_message(user_id, "В угол! На сколько отправим подумать над своим поведением? 🛑", reply_markup=markup)

# --- ОБРАБОТЧИК ДЛЯ КНОПКИ ---
@bot.message_handler(func=lambda message: message.text == "🛑 В угол")
def timeout_button_handler(message):
    timeout_command(message)
# --------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("timeout_"))
def process_timeout(call):
    user_id = call.message.chat.id
    action = call.data.split("_")[1]

    if action == "cancel":
        bot.edit_message_text("Отмена. Никто не наказан 😇", user_id, call.message.message_id)
        return

    partner_id = db.get_partner(user_id)
    if not partner_id:
        bot.edit_message_text("❌ Ошибка: котейка потерян(а).", user_id, call.message.message_id)
        return

    minutes = int(action)
    initiator_text = get_text_by_gender(user_id, "Твой котик отправил", "Твоя кошечка отправила")

    if minutes == 0:
        db.clear_timeout(partner_id)
        bot.edit_message_text("Ты милосердно прощаешь котейку 😇", user_id, call.message.message_id)
        try:
            pardon_text = get_text_by_gender(user_id, "Твой котик сменил", "Твоя кошечка сменила")
            bot.send_message(partner_id, f"✨ {pardon_text} гнев на милость. Ты можешь выйти из угла и снова писать послания!")
        except:
            pass
    else:
        db.set_timeout(partner_id, minutes)
        bot.edit_message_text(f"🛑 Котейка отправлен(а) в угол на {minutes} минут!", user_id, call.message.message_id)
        try:
            bot.send_message(
                partner_id, 
                f"🛑 *ВНИМАНИЕ!*\n{initiator_text} тебя подумать над своим поведением в угол на {minutes} минут!\nОтправка посланий временно заблокирована. 🤫", 
                parse_mode="Markdown"
            )
        except:
            pass
            
        # --- ПОЛНАЯ ПЕРСОНАЛИЗАЦИЯ ТАЙМЕРА ---
        def notify_timeout_end():
            try:
                db.cursor.execute('SELECT timeout_until FROM users WHERE user_id = ?', (partner_id,))
                res = db.cursor.fetchone()
                
                if res and res[0]:
                    timeout_time = datetime.strptime(res[0], "%Y-%m-%d %H:%M:%S")
                    if datetime.now() >= timeout_time:
                        db.clear_timeout(partner_id)
                        
                        # Пол того, кто сидел в углу (partner_id)
                        thought_word = get_text_by_gender(partner_id, "подумал", "подумала")
                        
                        # Пол того, кто наказывал (user_id)
                        target_text = get_text_by_gender(user_id, "своего котика", "свою кошечку")
                        waiter_text = get_text_by_gender(user_id, "твой котик ждет", "твоя кошечка ждет")
                        
                        unban_msg = (
                            "⏰ *Дзинь-дзинь!*\n\n"
                            "Твоё время в углу подошло к концу! 🎉\n"
                            f"Надеюсь, ты хорошо {thought_word} над своим поведением и больше не будешь расстраивать {target_text}. 😼\n\n"
                            f"А теперь бегом извиняться, мириться и обниматься, {waiter_text}! 🥺💕"
                        )
                        bot.send_message(partner_id, unban_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Ошибка в таймере угла: {e}")

        # Запускаем фоновый таймер (переводим минуты в секунды)
        threading.Timer(minutes * 60, notify_timeout_end).start()

# ==========================================
# ЧЕРНЫЙ СПИСОК (БЛОКИРОВКА)
# ==========================================

@bot.message_handler(commands=['blacklist'])
def blacklist_command(message):
    """Показывает список заблокированных пользователей"""
    blocked_users = db.get_blocked_users(message.chat.id)
    
    if not blocked_users:
        bot.send_message(message.chat.id, "Твой черный список пуст ✨")
        return
        
    text = "🛑 *Твой черный список:*\n\n"
    for user_id, username in blocked_users:
        mention = f" (@{username})" if username else ""
        text += f"• ID: `{user_id}`{mention}\n"
        
    text += "\nЧтобы разблокировать, используй команду /unblock"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['block'])
def block_command(message):
    """Запускает процесс блокировки"""
    waiting_for_block[message.chat.id] = True
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_block"))
    
    bot.send_message(
        message.chat.id, 
        "Введи ID или @username котейки, которую хочешь заблокировать 🛑:",
        reply_markup=markup
    )

@bot.message_handler(commands=['unblock'])
def unblock_command(message):
    """Запускает процесс разблокировки"""
    waiting_for_unblock[message.chat.id] = True
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_unblock"))
    
    bot.send_message(
        message.chat.id, 
        "Введи ID или @username котейки для разблокировки 🔓:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in ["cancel_block", "cancel_unblock"])
def cancel_block_unblock(call):
    """Отмена ввода ID для блокировки/разблокировки"""
    user_id = call.message.chat.id
    if call.data == "cancel_block":
        waiting_for_block.pop(user_id, None)
        bot.edit_message_text("Блокировка отменена.", user_id, call.message.message_id)
    else:
        waiting_for_unblock.pop(user_id, None)
        bot.edit_message_text("Разблокировка отменена.", user_id, call.message.message_id)
    send_menu(user_id)

@bot.message_handler(func=lambda m: m.chat.id in waiting_for_block or m.chat.id in waiting_for_unblock)
def process_block_unblock(message):
    """Обрабатывает введенный ID для бана или разбана"""
    user_id = message.chat.id
    is_blocking = user_id in waiting_for_block
    
    # Отмена через главное меню или другую команду
    if message.content_type != 'text' or message.text in ["💌 Послание", "❓ Помощь", "🔄 Перезапуск"] or message.text.startswith('/'):
        waiting_for_block.pop(user_id, None)
        waiting_for_unblock.pop(user_id, None)
        # Если это была кнопка меню, перенаправляем в ловушку
        if message.content_type == 'text' and not message.text.startswith('/'):
            catch_all_messages(message)
        return

    raw_input = message.text.strip()
    target_id = None

    if raw_input.startswith('@'):
        target_id = db.get_id_by_username(raw_input)
        if not target_id:
            bot.send_message(user_id, "⚠️ Котейки с таким ником нет в базе бота.")
            return
    else:
        try:
            target_id = int(raw_input)
        except ValueError:
            bot.send_message(user_id, "❌ Введи корректный числовой ID или @username.")
            return

    # Защита от самоблокировки с учетом пола
    if target_id == user_id:
        self_word = get_text_by_gender(user_id, "самого себя", "саму себя")
        bot.send_message(user_id, f"Ты не можешь заблокировать или разблокировать {self_word}!")
        return

    if is_blocking:
        db.block_user(user_id, target_id)
        waiting_for_block.pop(user_id, None)
        
        # Получаем красивое имя для уведомления
        target_name = get_user_display_name(target_id)
        bot.send_message(user_id, f"🛑 Котейка {target_name} добавлен(а) в черный список.")
        
        # ВАЖНО: Если пользователь заблокировал своего текущего партнера — разрываем связь!
        if db.get_partner(user_id) == target_id:
            db.unlink_partners(user_id)
            bot.send_message(user_id, "💔 Так как вы были в паре, связь автоматически разорвана.", reply_markup=get_main_keyboard(user_id))
            try:
                # Персонализируем сообщение для заблокированного партнера
                initiator_text = get_text_by_gender(user_id, "Твой котик разорвал", "Твоя кошечка разорвала")
                bot.send_message(target_id, f"💔 {initiator_text} связь.", reply_markup=get_main_keyboard(target_id))
            except:
                pass
    else:
        db.unblock_user(user_id, target_id)
        waiting_for_unblock.pop(user_id, None)
        
        target_name = get_user_display_name(target_id)
        bot.send_message(user_id, f"🔓 Котейка {target_name} больше не в черном списке.")
        
    send_menu(user_id)

# ==========================================
# ВАЖНЫЕ ДАТЫ
# ==========================================
#/adddate и её обработчики
@bot.message_handler(commands=['adddate'])
def add_date_start(message):
    """Начинает процесс добавления важной даты"""
    partner_id = db.get_partner(message.chat.id)
    if not partner_id:
        bot.send_message(message.chat.id, "❌ У тебя нет пары! Сначала подключись через /connect")
        return

    waiting_for_date_partner[message.chat.id] = partner_id
    waiting_for_date_title[message.chat.id] = True

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))

    bot.send_message(message.chat.id, "📅 Введи название важной даты (например: «Годовщина свадьбы»):",
                     reply_markup=markup)


@bot.message_handler(func=lambda m: m.chat.id in waiting_for_date_title)
def get_date_title(message):
    if message.text.startswith('/') or message.text in ["💌 Послание", "❓ Помощь", "🔄 Перезапуск"]:
        waiting_for_date_title.pop(message.chat.id, None)
        waiting_for_date_partner.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    waiting_for_date_title.pop(message.chat.id, None)
    waiting_for_date_value[message.chat.id] = message.text

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_date_title"))
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))
    bot.send_message(message.chat.id, "📆 Введи дату в формате ДД.ММ.ГГГГ (например: 14.02.2025):", 
                     reply_markup=markup)


@bot.message_handler(func=lambda m: m.chat.id in waiting_for_date_value)
def get_date_value(message):
    if message.text.startswith('/'):
        waiting_for_date_value.pop(message.chat.id, None)
        waiting_for_date_partner.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return
    try:
        date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        title = waiting_for_date_value.pop(message.chat.id, None)
        waiting_for_date_type[message.chat.id] = (title, date_obj.strftime("%Y-%m-%d"), message.text)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Однократная 🔂", callback_data="date_type_once"), 
                   types.InlineKeyboardButton("Ежегодная 🔁", callback_data="date_type_annual"))
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_date_value"), 
                   types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))
        bot.send_message(message.chat.id, "🔄 Это повторяющаяся дата (каждый год) или однократная (напоминание только раз в точную дату)?",
                         reply_markup=markup)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат! Введи дату как ДД.ММ.ГГГГ")


@bot.callback_query_handler(func=lambda call: call.data in ["date_type_once", "date_type_annual", "cancel_adddate"])
def process_date_type(call):
    user_id = call.message.chat.id
    if call.data == "cancel_adddate":
        for d in [waiting_for_date_title, waiting_for_date_value, waiting_for_date_type, waiting_for_date_remind, waiting_for_date_partner]:
            d.pop(user_id, None)
        bot.edit_message_text("❌ Добавление отменено.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    is_annual = 1 if call.data == "date_type_annual" else 0
    title, event_date, original_date_str = waiting_for_date_type.pop(user_id)
    waiting_for_date_remind[user_id] = (title, event_date, is_annual, original_date_str)

    markup = types.InlineKeyboardMarkup()
    for days, label in [(1, "За 1 день"), (3, "За 3 дня"), (7, "За неделю"), (30, "За месяц")]:
        markup.add(types.InlineKeyboardButton(label, callback_data=f"remind_{days}"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_date_type"), 
               types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))
    bot.edit_message_text("⏰ За сколько дней до даты прислать напоминание?", user_id, call.message.message_id, 
                          reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("remind_"))
def process_remind_days(call):
    user_id = call.message.chat.id
    remind_days = int(call.data.split("_")[1])

    if user_id not in waiting_for_date_remind:
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        return

    title, event_date, is_annual, original_date_str = waiting_for_date_remind.pop(user_id)
    partner_id = waiting_for_date_partner.pop(user_id)

    waiting_for_date_confirm[user_id] = {'title': title, 'event_date': event_date, 'is_annual': is_annual, 'remind_days': remind_days, 'original_date_str': original_date_str, 'partner_id': partner_id}

    date_display = original_date_str if not is_annual else original_date_str[:5]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_date_add"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_date_remind"), 
               types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_date_add"))
    
    bot.edit_message_text(
        f"📅 Проверь данные:\n\nНазвание: {title}\nДата: {date_display}\n"
        f"Тип: {'Ежегодная' if is_annual else 'Однократная'}\n"
        f"Напоминание за {remind_days} дн.\n\nВсё верно?",
        user_id, call.message.message_id, reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("back_date_"))
def handle_date_back(call):
    user_id = call.message.chat.id
    if call.data == "back_date_title":
        waiting_for_date_value.pop(user_id, None)
        waiting_for_date_title[user_id] = True
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))
        bot.edit_message_text("📅 Введи название важной даты:", user_id, call.message.message_id, reply_markup=markup)
        
    elif call.data == "back_date_value":
        data = waiting_for_date_type.pop(user_id, None)
        if data:
            waiting_for_date_value[user_id] = data[0] # возвращаем title
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_date_title"), types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))
            bot.edit_message_text("📆 Введи дату в формате ДД.ММ.ГГГГ заново:", user_id, call.message.message_id, reply_markup=markup)

    elif call.data == "back_date_type":
        data = waiting_for_date_remind.pop(user_id, None)
        if data:
            waiting_for_date_type[user_id] = (data[0], data[1], data[3])
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Однократная 🔂", callback_data="date_type_once"), 
                       types.InlineKeyboardButton("Ежегодная 🔁", callback_data="date_type_annual"))
            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_date_value"), 
                       types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))
            bot.edit_message_text("🔄 Это повторяющаяся дата или однократная?", user_id, call.message.message_id, 
                                  reply_markup=markup)

    elif call.data == "back_date_remind":
        data = waiting_for_date_confirm.pop(user_id, None)
        if data:
            waiting_for_date_remind[user_id] = (data['title'], data['event_date'], data['is_annual'], data['original_date_str'])
            waiting_for_date_partner[user_id] = data['partner_id']
            markup = types.InlineKeyboardMarkup()
            for days, label in [(1, "За 1 день"), (3, "За 3 дня"), (7, "За неделю"), (30, "За месяц")]:
                markup.add(types.InlineKeyboardButton(label, callback_data=f"remind_{days}"))
            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_date_type"), 
                       types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))
            bot.edit_message_text("⏰ За сколько дней до даты прислать напоминание?", user_id, call.message.message_id, 
                                  reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_date_add", "cancel_date_add"])
def confirm_date_add(call):
    user_id = call.message.chat.id
    if call.data == "cancel_date_add":
        waiting_for_date_confirm.pop(user_id, None)
        bot.edit_message_text("Добавление даты отменено.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    data = waiting_for_date_confirm.get(user_id)
    if not data:
        bot.edit_message_text("❌ Данные потеряны. Начни заново.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    db.add_important_date(user_id, data['partner_id'], data['title'], data['event_date'], data['is_annual'], data['remind_days'])
    waiting_for_date_confirm.pop(user_id, None)

    date_display = data['original_date_str'] if not data['is_annual'] else data['original_date_str'][:5]
    bot.edit_message_text(
        f"✅ Дата «{data['title']}» ({date_display}) добавлена!\n⏰ Напоминание за {data['remind_days']} дн.",
        user_id, call.message.message_id
    )
    send_menu(user_id)

#mydates
@bot.message_handler(commands=['mydates'])
def list_dates(message):
    """Показывает все важные даты пользователя с точным количеством дней"""
    dates = db.get_dates_for_user(message.chat.id)
    if not dates:
        bot.send_message(message.chat.id, "📭 У вас пока нет общих важных дат. Добавь через /adddate")
        return

    today = datetime.now().date()
    text = "📅 *Ваши общие важные даты:*\n\n"

    for date_id, title, event_date, is_annual, remind_days in dates:
        date_obj = datetime.strptime(event_date, "%Y-%m-%d").date()

        if is_annual:
            # Формируем дату в текущем году
            this_year_date = date_obj.replace(year=today.year)
            date_display = f"каждый год {event_date[5:]}"  # ДД.ММ

            if this_year_date < today:
                # Уже была в этом году – сколько дней прошло
                days_diff = (today - this_year_date).days
                if days_diff == 0:
                    status = " (сегодня!)"
                else:
                    status = f" (прошло {days_diff} дн. назад)"
            else:
                # Ещё не наступила – сколько осталось
                days_diff = (this_year_date - today).days
                if days_diff == 0:
                    status = " (сегодня!)"
                else:
                    status = f" (через {days_diff} дн.)"
        else:
            # Однократная дата
            date_display = event_date  # полная дата
            if date_obj < today:
                days_diff = (today - date_obj).days
                if days_diff == 0:
                    status = " (сегодня!)"
                else:
                    status = f" (прошло {days_diff} дн. назад)"
            else:
                days_diff = (date_obj - today).days
                if days_diff == 0:
                    status = " (сегодня!)"
                else:
                    status = f" (через {days_diff} дн.)"

        text += f"• *{title}* — {date_display}{status}\n"
        text += f"  `Напом. за {remind_days} дн.\n"

    text += "\nДля удаления используй /deldate (без ID)"
    bot.send_message(message.chat.id, text, parse_mode="Markdown)


# ==========================================
# УДАЛЕНИЕ ВИШЛИСТА И ДАТ
#==========================================


def delwish_interactive(user_id):
    """Запускает процесс удаления вишлиста"""
    waiting_for_delwish_id[user_id] = True
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_delwish"))
    bot.send_message(user_id, "Введи ID элемента вишлиста, который хочешь удалить:", reply_markup=markup)

def deldate_interactive(user_id):
    """Запускает процесс удаления даты"""
    waiting_for_deldate_id[user_id] = True
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_deldate"))
    bot.send_message(user_id, "Введи ID важной даты, которую хочешь удалить:", reply_markup=markup)

@bot.message_handler(commands=['delwish'])
def delwish_command(message):
    delwish_interactive(message.chat.id)

@bot.message_handler(commands=['deldate'])
def deldate_command(message):
    deldate_interactive(message.chat.id)

# Отмена удаления
@bot.callback_query_handler(func=lambda call: call.data in ["cancel_delwish", "cancel_deldate"])
def cancel_delete(call):
    user_id = call.message.chat.id
    if call.data == "cancel_delwish":
        waiting_for_delwish_id.pop(user_id, None)
        bot.edit_message_text("Удаление вишлиста отменено.", user_id, call.message.message_id)
    else:
        waiting_for_deldate_id.pop(user_id, None)
        bot.edit_message_text("Удаление даты отменено.", user_id, call.message.message_id)
    send_menu(user_id)

# Обработчик ввода ID для удаления
@bot.message_handler(func=lambda m: m.chat.id in waiting_for_delwish_id or m.chat.id in waiting_for_deldate_id)
def process_delete_id(message):
    user_id = message.chat.id
    is_wish = user_id in waiting_for_delwish_id
    if message.content_type != 'text':
        bot.send_message(user_id, "❌ Пожалуйста, отправь ID числом.")
        return
    try:
        item_id = int(message.text.strip())
    except ValueError:
        bot.send_message(user_id, "❌ ID должен быть числом. Попробуй ещё раз.")
        return

    if is_wish:
        # Проверяем, существует ли элемент и принадлежит ли паре
        wish = db.get_wish_by_id(item_id)
        if not wish:
            bot.send_message(user_id, "❌ Элемент с таким ID не найден.")
            return
        # Проверяем, что пользователь имеет право удалять (он участник пары)
        wish_id, wish_type, title, description, creator_id = wish
        # Надо проверить, что user_id является user1_id или user2_id в этой записи
        # Для этого нужно получить пару из БД – сделаем функцию в db.py
        if not db.is_wish_owner(user_id, item_id):
            bot.send_message(user_id, "❌ У тебя нет прав на удаление этого элемента.")
            return
        # Показываем подтверждение
        confirm_markup = types.InlineKeyboardMarkup()
        confirm_markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_delwish_{item_id}"),
            types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_delwish")
        )
        emoji = "🎁" if wish_type == "gift" else ("🌆" if wish_type == "date" else "💭")
        bot.send_message(user_id,
            f"Ты хочешь удалить:\n{emoji} *{title}*\n📝 {description}\n\nПодтверждаешь?",
            parse_mode="Markdown", reply_markup=confirm_markup)
        waiting_for_delwish_id.pop(user_id, None)
    else:
        # Аналогично для дат
        date = db.get_date_by_id(item_id)
        if not date:
            bot.send_message(user_id, "❌ Дата с таким ID не найдена.")
            return
        if not db.is_date_owner(user_id, item_id):
            bot.send_message(user_id, "❌ У тебя нет прав на удаление этой даты.")
            return
        confirm_markup = types.InlineKeyboardMarkup()
        confirm_markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_deldate_{item_id}"),
            types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_deldate")
        )
        bot.send_message(user_id,
            f"Ты хочешь удалить дату:\n📅 *{date[1]}* ({date[2]})\n\nПодтверждаешь?",
            parse_mode="Markdown", reply_markup=confirm_markup)
        waiting_for_deldate_id.pop(user_id, None)

# Обработчик кнопок "Подтвердить" для удаления из вишлиста и дат
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delwish_") or call.data.startswith("confirm_deldate_"))
def confirm_delete_action(call):
    user_id = call.message.chat.id
    
    # Сценарий: Удаление из вишлиста
    if call.data.startswith("confirm_delwish_"):
        # Извлекаем ID из строки "confirm_delwish_15"
        item_id = int(call.data.split("_")[2]) 
        success = db.delete_wish(item_id, user_id)
        
        if success:
            bot.edit_message_text("✅ Элемент успешно удален из вишлиста.", user_id, call.message.message_id)
        else:
            bot.edit_message_text("❌ Ошибка при удалении или элемент уже удален.", user_id, call.message.message_id)
            
    # Сценарий: Удаление важной даты
    elif call.data.startswith("confirm_deldate_"):
        # Извлекаем ID из строки "confirm_deldate_5"
        item_id = int(call.data.split("_")[2]) 
        success = db.delete_date(item_id, user_id)
        
        if success:
            bot.edit_message_text("✅ Важная дата успешно удалена.", user_id, call.message.message_id)
        else:
            bot.edit_message_text("❌ Ошибка при удалении или дата уже удалена.", user_id, call.message.message_id)
            
    # Возвращаем меню
    send_menu(user_id)

# ==========================================
# ВИШЛИСТ ПАРЫ
# ==========================================

@bot.message_handler(commands=['addwish'])
def add_wish_start(message):
    partner_id = db.get_partner(message.chat.id)
    if not partner_id:
        send_no_partner_error(message.chat.id)
        return

    markup = types.InlineKeyboardMarkup()
    btn_gift = types.InlineKeyboardButton("🎁 Подарок", callback_data="wish_gift")
    btn_date = types.InlineKeyboardButton("🌆 Свидание", callback_data="wish_date")
    btn_wish = types.InlineKeyboardButton("💭 Желание", callback_data="wish_wish")   
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="wish_cancel")
    markup.add(btn_gift, btn_date, btn_wish)   
    markup.add(btn_cancel)
    bot.send_message(message.chat.id, "Что хочешь добавить в вишлист?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("wish_"))
def process_wish_type(call):
    user_id = call.message.chat.id
    if call.data == "wish_cancel":
        waiting_for_wish_type.pop(user_id, None)
        waiting_for_wish_title.pop(user_id, None)
        waiting_for_wish_description.pop(user_id, None)
        bot.edit_message_text("Добавление отменено 🛑", user_id, call.message.message_id)
        send_menu(user_id)
        return

    wish_type = "gift" if call.data == "wish_gift" else ("date" if call.data == "wish_date" else "wish")
    waiting_for_wish_type[user_id] = wish_type
    waiting_for_wish_title[user_id] = True
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_wish_type"))
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="wish_cancel"))
    bot.edit_message_text("✍️ Введи название:", user_id, call.message.message_id, reply_markup=markup)


@bot.message_handler(func=lambda m: m.chat.id in waiting_for_wish_title)
def get_wish_title(message):
    if message.text.startswith('/'):
        waiting_for_wish_title.pop(message.chat.id, None)
        waiting_for_wish_type.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    waiting_for_wish_title.pop(message.chat.id, None)
    waiting_for_wish_description[message.chat.id] = {"title": message.text}

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_wish_title"))
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="wish_cancel"))
    bot.send_message(message.chat.id, "📝 Теперь введи описание:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.chat.id in waiting_for_wish_description)
def get_wish_description(message):
    if message.text.startswith('/'):
        waiting_for_wish_description.pop(message.chat.id, None)
        waiting_for_wish_type.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    user_id = message.chat.id
    title = waiting_for_wish_description[user_id]["title"]
    wish_type = waiting_for_wish_type[user_id]

    waiting_for_wish_confirm[user_id] = {'type': wish_type, 'title': title, 'description': message.text}
    waiting_for_wish_description.pop(user_id, None)
    waiting_for_wish_type.pop(user_id, None)

    emoji = "🎁" if wish_type == "gift" else ("🌆" if wish_type == "date" else "💭")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_wish_add"))
    markup.add(
        types.InlineKeyboardButton("⬅️ Назад", callback_data="back_wish_desc"),
        types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_wish_add")
    )
    bot.send_message(user_id, f"📝 Проверь данные:\n\n{emoji} *{title}*\n📝 {message.text}\n\nВсё верно?", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("back_wish_"))
def handle_wish_back(call):
    user_id = call.message.chat.id
    if call.data == "back_wish_type":
        waiting_for_wish_title.pop(user_id, None)
        waiting_for_wish_type.pop(user_id, None)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎁 Подарок", callback_data="wish_gift"), 
                   types.InlineKeyboardButton("🌆 Свидание", callback_data="wish_date"), 
                   types.InlineKeyboardButton("💭 Желание", callback_data="wish_wish"))
        markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="wish_cancel"))
        bot.edit_message_text("Что хочешь добавить в вишлист?", user_id, call.message.message_id, reply_markup=markup)
        
    elif call.data == "back_wish_title":
        waiting_for_wish_description.pop(user_id, None)
        waiting_for_wish_title[user_id] = True
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_wish_type"), 
                   types.InlineKeyboardButton("Отменить ❌", callback_data="wish_cancel"))
        bot.edit_message_text("✍️ Введи название:", user_id, call.message.message_id, reply_markup=markup)
        
    elif call.data == "back_wish_desc":
        data = waiting_for_wish_confirm.pop(user_id, None)
        if data:
            waiting_for_wish_description[user_id] = {"title": data["title"]}
            waiting_for_wish_type[user_id] = data["type"]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_wish_title"), 
                       types.InlineKeyboardButton("Отменить ❌", callback_data="wish_cancel"))
            bot.edit_message_text("📝 Введи описание заново:", user_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_wish_add", "cancel_wish_add"])
def confirm_wish_add(call):
    user_id = call.message.chat.id
    if call.data == "cancel_wish_add":
        waiting_for_wish_confirm.pop(user_id, None)
        bot.edit_message_text("Добавление вишлиста отменено.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    data = waiting_for_wish_confirm.get(user_id)
    if not data:
        bot.edit_message_text("❌ Данные потеряны. Начни заново.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    partner_id = db.get_partner(user_id)
    if not partner_id:
        bot.edit_message_text("❌ У тебя нет пары.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    wish_id = db.add_wish(user_id, partner_id, user_id, data['type'], data['title'], data['description'])
    waiting_for_wish_confirm.pop(user_id, None)

    emoji = "🎁" if data['type'] == "gift" else ("🌆" if data['type'] == "date" else "💭")
    bot.edit_message_text(f"✅ Добавлено в вишлист!\n\n{emoji} {data['title']}\n📝 {data['description']}", user_id, call.message.message_id)

    # Уведомление партнёру
    creator_text = get_text_by_gender(user_id, "Твой котик 🐈‍⬛", "Твоя кошечка 🐈")
    try:
        bot.send_message(partner_id, f"💕 {creator_text} добавил(а) новую идею в вишлист!\n\n{emoji} {data['title']}\n📝 {data['description']}")
    except:
        pass
    send_menu(user_id)




@bot.message_handler(commands=['wishlist'])
def wishlist(message):

    wishes = db.get_wishlist(message.chat.id)

    if not wishes:
        bot.send_message(
            message.chat.id,
            "💕 Ваш вишлист пока пуст!"
        )
        return

    text = "💕 *Общий вишлист пары:*\n\n"

    for wish_id, wish_type, title, description, creator_id, username in wishes:

        if wish_type == "gift":
            emoji = "🎁"
        elif wish_type == "date":
            emoji = "🌆"
        else:  # wish
            emoji = "💭"

        creator = f"@{username}" if username else creator_id

        text += (
            f"`id:{wish_id}` {emoji} *{title}*\n"
            f"📝 {description}\n"
            f"👤 Добавил(а): {creator}\n\n"
        )

    text += "Удалить: /delwish <id>"

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown"
    )



# ==========================================
# МУД-ТРЕКЕР (НАСТРОЕНИЕ)
# ==========================================

@bot.message_handler(commands=['mood'])
def mood_command(message):
    show_mood_menu(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "🎭 Настроение")
def mood_button_handler(message):
    show_mood_menu(message.chat.id)

def show_mood_menu(chat_id, message_id=None):
    if not db.get_partner(chat_id):
        send_no_partner_error(chat_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_happy = types.InlineKeyboardButton("Счастлив(а) 😊", callback_data="mood_happy")
    btn_love = types.InlineKeyboardButton("Люблю 🥰", callback_data="mood_love")
    btn_sad = types.InlineKeyboardButton("Грущу 😢", callback_data="mood_sad")
    btn_angry = types.InlineKeyboardButton("Злюсь 😠", callback_data="mood_angry")
    btn_tired = types.InlineKeyboardButton("Устал(а) 😴", callback_data="mood_tired")
    
    # Кнопки статистики и журнала в один ряд
    btn_stats = types.InlineKeyboardButton("📊 Статистика", callback_data="mood_stats")
    btn_journal = types.InlineKeyboardButton("📖 Журнал", callback_data="mood_journal")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="mood_cancel")
    
    markup.add(btn_happy, btn_love, btn_sad, btn_angry, btn_tired)
    markup.row(btn_stats, btn_journal)
    markup.add(btn_cancel)
    
    latest_mood = db.get_latest_mood(chat_id)
    current_status = ""
    if latest_mood:
        mood_emoji = {
            "happy": "😊", "love": "🥰", "sad": "😢", 
            "angry": "😠", "tired": "😴"
        }.get(latest_mood[0], "")
        current_status = f"\nТвое текущее настроение: {mood_emoji}\n"

    text = f"Как ты себя чувствуешь сейчас? 🎭{current_status}"

    # Если message_id передан, редактируем сообщение (для кнопки Назад), иначе отправляем новое
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("mood_"))
def process_mood_selection(call):
    user_id = call.message.chat.id
    
    if call.data == "mood_cancel":
        bot.edit_message_text("Выбор настроения отменен.", user_id, call.message.message_id)
        return

    # Обработка кнопки "Назад" (возвращает основное меню настроения)
    if call.data == "mood_back":
        show_mood_menu(user_id, call.message.message_id)
        return

    # --- СТАТИСТИКА ---
    if call.data == "mood_stats":
        partner_id = db.get_partner(user_id)
        if not partner_id:
            bot.edit_message_text("❌ У тебя нет пары для просмотра статистики.", user_id, call.message.message_id)
            return
        
        my_stats = db.get_mood_stats(user_id)
        partner_stats = db.get_mood_stats(partner_id)
        
        mood_names = {"happy": "Счастье 😊", "love": "Любовь 🥰", "sad": "Грусть 😢", "angry": "Злость 😠", "tired": "Усталость 😴"}
        
        def format_stats(stats_dict):
            if not stats_dict:
                return "Пока нет записей 📭"
            lines = []
            sorted_stats = sorted(stats_dict.items(), key=lambda item: item[1], reverse=True)
            for mood, count in sorted_stats:
                name = mood_names.get(mood, mood)
                lines.append(f"• {name}: `{count}` раз(а)")
            return "\n".join(lines)
        
        partner_name = get_user_display_name(partner_id)
        text = (
            "📊 *Статистика за всё время*\n\n"
            f"👤 *Твои эмоции:*\n{format_stats(my_stats)}\n\n"
            f"🐱 *Эмоции {partner_name}:*\n{format_stats(partner_stats)}"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="mood_back"))
        bot.edit_message_text(text, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        return

    # --- ЖУРНАЛ НАСТРОЕНИЙ ---
    if call.data == "mood_journal":
        partner_id = db.get_partner(user_id)
        if not partner_id:
            bot.edit_message_text("❌ У тебя нет пары для просмотра журнала.", user_id, call.message.message_id)
            return

        history = db.get_mood_history(user_id, partner_id, limit=15)

        if not history:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="mood_back"))
            bot.edit_message_text("📭 Журнал настроений пока пуст.", user_id, call.message.message_id, reply_markup=markup)
            return

        mood_emoji = {"happy": "😊", "love": "🥰", "sad": "😢", "angry": "😠", "tired": "😴"}
        text = "📖 *Журнал настроений (последние 15 записей):*\n\n"

        for uid, mood, created_at, username in history:
            # Превращаем '2026-06-29 14:30:00' в '29.06 14:30'
            try:
                dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                date_str = dt.strftime("%d.%m %H:%M")
            except:
                date_str = created_at[:16] # Резервный вариант, если формат другой

            name = "Ты" if uid == user_id else get_user_display_name(uid)
            emoji = mood_emoji.get(mood, "🎭")
            
            text += f"`{date_str}` | {name}: {emoji}\n"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="mood_back"))
        bot.edit_message_text(text, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        return

    # --- УСТАНОВКА НАСТРОЕНИЯ ---
    selected_mood = call.data.split('_')[1]
    db.set_mood(user_id, selected_mood)
    bot.edit_message_text("Твое настроение обновлено! ✨", user_id, call.message.message_id)
    
    partner_id = db.get_partner(user_id)
    if partner_id:
        initiator = get_text_by_gender(user_id, "Твой котик 🐈‍⬛", "Твоя кошечка 🐈")
        mood_messages = {
            "happy": get_text_by_gender(user_id, "счастлив 😊", "счастлива 😊"),
            "love": "посылает тебе свою любовь 🥰",
            "sad": "грустит 😢. Самое время для поддержки!",
            "angry": "злится 😠. Осторожно!",
            "tired": get_text_by_gender(user_id, "устал 😴", "устала 😴")
        }
        status_text = mood_messages.get(selected_mood, "изменил(а) настроение.")
        
        try:
            bot.send_message(partner_id, f"🎭 *Обновление статуса:*\n{initiator} сейчас {status_text}", parse_mode="Markdown")
        except:
            pass

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
# СИСТЕМА НАПОМИНАНИЙ (ФОНОВЫЙ ПОТОК)
# ==========================================

def check_and_send_reminders():
    """Проверяет и отправляет напоминания о важных датах"""
    today_str = datetime.now().strftime("%Y-%m-%d")

    dates_to_remind = db.get_dates_to_remind(today_str)

    for date_id, user1_id, user2_id, title, event_date, is_annual, remind_days in dates_to_remind:
        current_year = datetime.now().year

        # Проверяем, не отправляли ли уже напоминание в этом году
        if db.was_reminder_sent(date_id, current_year):
            continue

        # Отправляем обоим партнёрам
        for user_id in (user1_id, user2_id):
            try:
                if is_annual:
                    msg = f"🎉 *Ежегодное напоминание!*\nЧерез {remind_days} дн. — {title} ({event_date[5:]})"
                else:
                    msg = f"📅 *Напоминание!*\nЧерез {remind_days} дн. — {title} ({event_date})"

                bot.send_message(user_id, msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Не удалось отправить напоминание {user_id}: {e}")

        # Отмечаем, что напоминание отправлено
        db.mark_reminder_sent(date_id, current_year)


def reminder_loop():
    """Запускается в отдельном потоке и проверяет напоминания каждые 6 часов"""
    while True:
        try:
            check_and_send_reminders()
        except Exception as e:
            print(f"Ошибка в reminder_loop: {e}")
        time.sleep(21600)  # 6 часов



# ==========================================
# ТОЧКА ВХОДА (ЗАПУСК БОТА)
# ==========================================

if __name__ == "__main__":
    db.init_db() # Инициализация структуры базы данных при старте

    #Запуск потока (напоминания о датах)
    reminder_thread = threading.Thread(target=reminder_loop, daemon=True)
    reminder_thread.start()

    print("Бот запущен и готов к работе...")
    while True:
        try:
            # none_stop=True предотвращает остановку при ошибках сети
            bot.polling(none_stop=True, timeout=90) 
        except Exception as e:
            # Защита от падений API Telegram
            print(f"⚠️ Ошибка связи с Telegram. Жду 5 секунд... Ошибка: {e}")
            time.sleep(5)