from telebot import types
import time
import db 
from config import bot, ADMIN_IDS
from datetime import datetime
import threading
from PIL import Image, ImageDraw, ImageFont
import io
import os
import random

# ==========================================
# ОБЪЕКТНО-ОРИЕНТИРОВАННАЯ АРХИТЕКТУРА ИНТЕРФЕЙСА
# ==========================================

class BaseMarkupManager:
    """
    @brief Базовый класс для создания компонентов интерфейса.
    @details Служит фундаментом для реализации фабрики клавиатур Telegram.
    """
    def __init__(self):
        pass


class BotInterfaceManager(BaseMarkupManager):
    """
    @brief Класс для управления клавиатурами и визуальными компонентами.
    @details Наследуется от BaseMarkupManager, полностью сохраняя оригинальный дизайн UI.
    """

    def get_main_keyboard(self, user_id: int) -> types.ReplyKeyboardMarkup:
        """
        @brief Создает умную главную клавиатуру бота.
        @param user_id ID пользователя для проверки наличия пары.
        @return Объект ReplyKeyboardMarkup.
        """
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        
        btn_help = types.KeyboardButton("❓ Помощь")
        btn_start = types.KeyboardButton("🔄 Перезапуск")

        if db.bot_db.get_partner(user_id):
            btn_love = types.KeyboardButton("💌 Послание")
            btn_wishlist = types.KeyboardButton("🎁 Вишлист")
            btn_dates = types.KeyboardButton("📅 Даты")
            btn_streak = types.KeyboardButton("🔥 Серия")
            markup.row(btn_love, btn_wishlist)
            markup.row(btn_dates, btn_streak)

        markup.row(btn_help, btn_start)
        return markup

    def get_gender_keyboard(self) -> types.InlineKeyboardMarkup:
        """
        @brief Создает inline-клавиатуру для первичного выбора пола или его изменения.
        @return Объект InlineKeyboardMarkup.
        """
        markup = types.InlineKeyboardMarkup()
        btn_m = types.InlineKeyboardButton("Я котик 🐈‍⬛", callback_data="gender_m")
        btn_f = types.InlineKeyboardButton("Я кошечка 🐈", callback_data="gender_f")
        markup.add(btn_m, btn_f)
        return markup


# Инициализируем менеджер интерфейса
ui_manager = BotInterfaceManager()


# ==========================================
# СИСТЕМА УПРАВЛЕНИЯ СОСТОЯНИЯМИ (ИНКАПСУЛЯЦИЯ ДАННЫХ)
# ==========================================

class BotStateManager:
    """
    @brief Класс для централизованного управления состояниями пользователей в ОЗУ.
    @details Заменяет разрозненные глобальные словари на единую ООП-структуру.
    """
    def __init__(self):
        self.waiting_for_partner = {}
        self.waiting_for_message = {}
        self.draft_messages = {}
        self.waiting_for_broadcast = {}
        self.broadcast_drafts = {}
        self.pending_requests_sender = {}
        self.pending_requests_receiver = {}
        self.waiting_for_block = {}
        self.waiting_for_unblock = {}
        
        # Состояния для добавления важной даты
        self.waiting_for_date_title = {}
        self.waiting_for_date_value = {}
        self.waiting_for_date_type = {}
        self.waiting_for_date_remind = {}
        self.waiting_for_date_partner = {}
        
        # Состояния для общего вишлиста
        self.waiting_for_wish_type = {}
        self.waiting_for_wish_title = {}
        self.waiting_for_wish_description = {}
        self.waiting_for_delwish_id = {}
        self.waiting_for_deldate_id = {}
        self.waiting_for_wish_confirm = {}
        self.waiting_for_date_confirm = {}


# Инициализируем менеджер состояний
state = BotStateManager()


# ==========================================
# ФУНКЦИИ-ПОМОЩНИКИ (ИНТЕРФЕЙС И ТЕКСТЫ)
# ==========================================

def get_target_partner_text(user_id: int) -> str:
    """
    @brief Определяет пол ПАРТНЕРА по базе данных и возвращает правильное ласковое обращение.
    """
    partner_id = db.bot_db.get_partner(user_id)
    partner_gender = db.bot_db.get_gender(partner_id)
    
    if partner_gender == "female":
        return "своей кошечке 🐈"
    return "своему котику 🐈‍⬛"


def get_text_by_gender(user_id: int, male_text: str, female_text: str) -> str:
    """
    @brief Универсальная функция для выдачи текста в зависимости от пола САМОГО пользователя.
    """
    gender = db.bot_db.get_gender(user_id)
    if gender == "female":
        return female_text
    return male_text


def send_no_partner_error(chat_id: int):
    """
    @brief Универсальный обработчик ошибки: попытка действия без подключенного партнера.
    """
    status_text = get_text_by_gender(chat_id, "подключен", "подключена")
    bot.send_message(
        chat_id, 
        f"⚠️ Ошибка: ты ни к кому не {status_text}. Сначала подключись к котейке через команду /connect!"
    )


def send_menu(chat_id: int, text: str = "Главное меню 👇"):
    """
    @brief Универсальная функция для возврата пользователя в главное меню со сбросом состояний.
    """
    bot.send_message(chat_id, text, reply_markup=ui_manager.get_main_keyboard(chat_id))


def get_user_display_name(user_id: int) -> str:
    """
    @brief Умная функция для отображения имени. Возвращает @username или числовой ID.
    """
    username = db.bot_db.get_username(user_id)
    if username:
        return f"@{username}"
    return str(user_id)


# ==========================================
# ОСНОВНЫЕ КОМАНДЫ НАВИГАЦИИ
# ==========================================

@bot.message_handler(commands=['help'])
def help_command(message):
    """
    @brief Обработчик команды /help. Выводит список всех доступных команд.
    """
    markup = ui_manager.get_main_keyboard(message.chat.id)

    help_text = (
        "Доступные команды:\n\n"
        "/start — Перезапустить бота\n"
        "/help — Показать это меню\n"
        "/gender — Изменить свой пол\n"
        "/id — Узнать свой числовой ID\n"
        "/connect — Подключиться к котейке\n"
        "/disconnect — Отключиться от котейки \n"
        "/love — Отправить послание котейке \n"
        "/streak — Показать текущую серию \n\n"
        "📅 *Важные даты:*\n"
        "/adddate — Добавить общую важную дату\n"
        "/mydates — Список всех важных дат\n"
        "/deldate — Удалить важную дату\n\n"
        "💕 *Вишлист пары:*\n"
        "/wishlist — Посмотреть общий вишлист\n"
        "/addwish — Добавить подарок, свидание или желание\n\n"
        "/delwish — Удалить элемент вишлиста\n\n"
        "🛡 *Безопасность:*\n"
        "/block — Заблокировать котейку\n"
        "/unblock — Разблокировать котейку\n"
        "/blacklist — Мой черный список"
    )
    
    if message.chat.id in ADMIN_IDS:
        help_text += (
            "\n\n🛠 *Команды разработчика:*\n"
            "/broadcast — Массовая рассылка\n"
            "/stats — Статистика пользователей" 
        )

    bot.send_message(message.chat.id, help_text, parse_mode="Markdown", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "❓ Помощь")
def help_button_handler(message):
    """
    @brief Перехват нажатия на текстовую кнопку "❓ Помощь".
    """
    help_command(message)


@bot.message_handler(commands=['start'])
def start(message):
    """
    @brief Обработчик команды /start. Регистрирует или приветствует пользователя.
    """
    state.waiting_for_partner.pop(message.chat.id, None)
    state.waiting_for_message.pop(message.chat.id, None)
    state.draft_messages.pop(message.chat.id, None)

    gender = db.bot_db.get_gender(message.chat.id)

    if gender:
        if db.bot_db.get_partner(message.chat.id):
            status_text = get_text_by_gender(message.chat.id, "подключен", "подключена")
            target_text = get_target_partner_text(message.chat.id) 
            
            bot.send_message(
                message.chat.id, 
                f"С возвращением! Ты уже {status_text} к {target_text} 💕\n"
                "Используй меню внизу или /help для списка команд.",
                reply_markup=ui_manager.get_main_keyboard(message.chat.id)
            )
        else:
            animal = "котик 🐈‍⬛" if gender == "male" else "кошечка 🐈"
            bot.send_message(
                message.chat.id, 
                f"С возвращением! В системе ты {animal}.\n"
                "Тебе осталось только подключиться к котейке через команду /connect!",
                reply_markup=ui_manager.get_main_keyboard(message.chat.id)
            )
        return

    bot.send_message(
        message.chat.id, 
        f"Привет, {message.from_user.first_name}! Я бот для парочек 💕\n"
        "Для начала, скажи кто ты:",
        reply_markup=ui_manager.get_gender_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "🔄 Перезапуск")
def start_button_handler(message):
    """
    @brief Перехват нажатия на текстовую кнопку "🔄 Перезапуск".
    """
    start(message)


@bot.message_handler(commands=['gender'])
def change_gender(message):
    """
    @brief Обработчик команды /gender для изменения пола.
    """
    bot.send_message(
        message.chat.id, 
        "⚙️ Открываю настройки...", 
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.send_message(
        message.chat.id, 
        "Выбери, кем ты хочешь быть в системе:",
        reply_markup=ui_manager.get_gender_keyboard() 
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("gender_"))
def save_gender(call):
    """
    @brief Сохраняет выбранный пол в базу данных.
    """
    gender = "male" if call.data == "gender_m" else "female"
    db.bot_db.add_or_update_user(call.message.chat.id, gender, call.from_user.username)

    if db.bot_db.get_partner(call.message.chat.id):
        bot.edit_message_text(
            "Готово! Твой пол успешно изменен ✨",
            call.message.chat.id, 
            call.message.message_id
        )
        send_menu(call.message.chat.id, "Меню посланий активно 👇")
    else:
        text = (
            "Отлично! Теперь ты можешь подключиться к котейке.\n\n"
            "Напиши /connect and введи ID или @username котейки\n"
            "Чтобы узнать свой ID, напиши /id\n"
            "Если забудешь команды, просто нажми /help"
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
        send_menu(call.message.chat.id, "Меню навигации активно 👇")


@bot.message_handler(commands=['id'])
def id_command(message):
    """
    @brief Обработчик команды /id. Выводит Telegram ID пользователя.
    """
    markup = ui_manager.get_main_keyboard(message.chat.id)
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
    """
    @brief Обработчик команды /connect.
    @details Запускает процесс привязки двух пользователей друг к другу.
    """
    if db.bot_db.get_partner(message.chat.id):
        status_text = get_text_by_gender(message.chat.id, "подключен", "подключена")
        target_text = get_target_partner_text(message.chat.id)
        
        bot.send_message(
            message.chat.id, 
            f"⚠️ Ты уже {status_text} к {target_text}! Сначала нужно разорвать текущую связь через команду /disconnect"
        )
        return

    state.waiting_for_partner[message.chat.id] = True
    
    markup = types.InlineKeyboardMarkup()
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_connect")
    markup.add(btn_cancel)

    bot.send_message(
        message.chat.id, 
        "Введи числовой ID котейки или никнейм (например, @nickname):",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "cancel_connect")
def cancel_connect_callback(call):
    """
    @brief Отмена ввода ID партнера.
    """
    user_id = call.message.chat.id
    state.waiting_for_partner.pop(user_id, None)
    
    bot.edit_message_text("Ввод отменен 🛑", user_id, call.message.message_id)
    send_menu(user_id, "Главное меню 👇")


@bot.message_handler(func=lambda m: m.chat.id in state.waiting_for_partner)
def set_partner(message):
    """
    @brief Обрабатывает введенный ID или никнейм для подключения.
    @details Проводит валидацию, проверки на ЧС и наличие пары у потенциального партнера.
    """
    if message.content_type != 'text':
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправь ID или никнейм текстом.")
        return

    if message.text in ["💌 Послание", "❓ Помощь", "🔄 Перезапуск"]:
        state.waiting_for_partner.pop(message.chat.id, None)
        if message.text == "💌 Послание":
            love(message)
        elif message.text == "❓ Помощь":
            help_command(message)
        else:
            start(message)
        return

    if message.text.startswith('/'):
        state.waiting_for_partner.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Ввод отменен.")
        return

    raw_input = message.text.strip()
    partner_id = None

    if raw_input.startswith('@'):
        partner_id = db.bot_db.get_id_by_username(raw_input)
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

    if db.bot_db.get_gender(partner_id) is None:
        bot.send_message(
            message.chat.id, 
            "⚠️ Ошибка! Котейка еще не запустил(а) бота или не выбрал(а) пол.\n"
            "Попроси зайти в бота, нажать /start, выбрать пол и прислать тебе свой ID или ник!"
        )
        return 
        
    if db.bot_db.get_partner(partner_id):
        bot.send_message(message.chat.id, "⚠️ У котейки уже есть пара! Подключение невозможно.")
        return
        
    if db.bot_db.is_blocked(partner_id, message.chat.id):
        bot.send_message(message.chat.id, "⚠️ Котейка не найден(а) или ограничил(а) к себе доступ.")
        return

    if db.bot_db.is_blocked(message.chat.id, partner_id):
        action_word = get_text_by_gender(message.chat.id, "заблокировал", "заблокировала")
        bot.send_message(message.chat.id, f"⚠️ Ты {action_word} котейку! Сначала разблокируй через /unblock.")
        return
            
    state.waiting_for_partner.pop(message.chat.id, None)
    state.pending_requests_sender[message.chat.id] = partner_id

    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("Отправить запрос 💌", callback_data="req_send")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="req_cancel")
    markup.add(btn_cancel, btn_send)

    found_text = get_text_by_gender(partner_id, "Котик найден! 🐈‍⬛", "Кошечка найдена! 🐈")
    bot.reply_to(message, f"{found_text} Отправить запрос на подключение?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ["req_send", "req_cancel"])
def process_request_step1(call):
    """
    @brief Обработка решения инициатора об отправке запроса.
    """
    user_id = call.message.chat.id
    
    if call.data == "req_cancel":
        state.pending_requests_sender.pop(user_id, None)
        bot.edit_message_text("Запрос отменен 🛑", user_id, call.message.message_id)
        send_menu(user_id, "Главное меню 👇")
        return

    if call.data == "req_send":
        target_id = state.pending_requests_sender.pop(user_id, None)
        
        if not target_id:
            bot.edit_message_text("⚠️ Ошибка: данные для подключения потеряны.", user_id, call.message.message_id)
            return

        state.pending_requests_receiver[target_id] = user_id

        sender_text = get_text_by_gender(user_id, "котик 🐈‍⬛", "кошечка 🐈")
        sender_name = get_user_display_name(user_id)
        
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


@bot.callback_query_handler(func=lambda call: call.data in ["partner_accept", "partner_decline"])
def process_request_step2(call):
    """
    @brief Обработка ответа потенциального партнера на запрос.
    """
    target_id = call.message.chat.id 
    requester_id = state.pending_requests_receiver.pop(target_id, None) 

    if not requester_id:
        bot.edit_message_text("⚠️ Этот запрос уже устарел или был отменен.", target_id, call.message.message_id)
        return

    if call.data == "partner_decline":
        bot.edit_message_text("Запрос отклонен 🛑", target_id, call.message.message_id)
        bot.send_message(requester_id, "💔 Твой запрос на подключение был отклонен.")
        return

    if call.data == "partner_accept":
        if db.bot_db.get_partner(target_id) or db.bot_db.get_partner(requester_id):
            bot.edit_message_text("⚠️ Ошибка: кто-то из вас уже нашел пару!", target_id, call.message.message_id)
            bot.send_message(requester_id, "⚠️ Ошибка подключения: кто-то из вас уже в паре.")
            return

        db.bot_db.link_partners(requester_id, target_id)
        
        state.waiting_for_partner.pop(requester_id, None) 
        state.waiting_for_message.pop(requester_id, None) 

        bot.edit_message_text("Соединение установлено! ✨", target_id, call.message.message_id)

        action_text_a = get_text_by_gender(requester_id, "подключен", "подключена")
        target_text_a = get_text_by_gender(target_id, "к своему котику! 🐈‍⬛", "к своей кошечке! 🐈")
        bot.send_message(
            requester_id, 
            f"Ура! Твой запрос принят. Ты {action_text_a} {target_text_a} 💕",
            reply_markup=ui_manager.get_main_keyboard(requester_id)
        )

        notification_text_b = get_text_by_gender(requester_id, "К тебе подключился твой котик! 🐈‍⬛", "К тебе подключилась твоя кошечка! 🐈")
        bot.send_message(
            target_id, 
            notification_text_b,
            reply_markup=ui_manager.get_main_keyboard(target_id)
        )


@bot.message_handler(commands=['disconnect'])
def disconnect(message):
    """
    @brief Обработчик команды /disconnect. Инициализирует разрыв пары.
    """
    if not db.bot_db.get_partner(message.chat.id):
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
    """
    @brief Финализирует разрыв связи между партнерами.
    """
    if call.data == "disconnect_no":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Отключение отменено. Вы всё еще вместе! 💕"
        )
        send_menu(call.message.chat.id, "Главное меню активно 👇")
        return
    
    if call.data == "disconnect_yes":
        partner_id = db.bot_db.get_partner(call.message.chat.id)
        if partner_id:
            db.bot_db.unlink_partners(call.message.chat.id)
            
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

# ==========================================
# ПАНЕЛЬ АДМИНИСТРАТОРА (РАССЫЛКА НОВОСТЕЙ)
# ==========================================

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    """
    @brief Инициализация режима массовой рассылки (только для админов).
    """
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "Я не знаю такую команду 🥺")
        return

    state.waiting_for_broadcast[message.chat.id] = True
    bot.send_message(
        message.chat.id,
        "📣 *Режим рассылки*\n\nПришли мне сообщение (текст, фото или видео), которое увидят все.\n"
        "Кнопки управления появятся после отправки контента.",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )


@bot.message_handler(
    func=lambda m: m.chat.id in state.waiting_for_broadcast, 
    content_types=['text', 'photo', 'voice', 'video', 'video_note', 'document', 'sticker', 'audio', 'animation']
)
def receive_broadcast_draft(message):
    """
    @brief Ловит контент для рассылки и сохраняет его ID в черновики.
    """
    state.waiting_for_broadcast.pop(message.chat.id, None)
    state.broadcast_drafts[message.chat.id] = message.message_id

    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("Отправить всем 📣", callback_data="bc_send")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="bc_cancel")
    
    markup.add(btn_cancel, btn_send)

    bot.reply_to(message, "Контент для рассылки получен. Начинаем?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("bc_"))
def process_broadcast_callback(call):
    """
    @brief Обрабатывает финальное решение админа о запуске рассылки.
    """
    admin_id = call.message.chat.id
    
    if call.data == "bc_cancel":
        state.broadcast_drafts.pop(admin_id, None)
        bot.edit_message_text("Рассылка отменена 🛑", admin_id, call.message.message_id)
        send_menu(admin_id)
        return

    if call.data == "bc_send":
        draft_id = state.broadcast_drafts.get(admin_id)
        if not draft_id:
            bot.edit_message_text("⚠️ Ошибка: черновик потерян.", admin_id, call.message.message_id)
            send_menu(admin_id)
            return

        users = db.bot_db.get_all_users()
        success_count = 0
        
        bot.edit_message_text(f"⏳ Рассылка запущена для {len(users)} пользователей...", admin_id, call.message.message_id)

        for user_id in users:
            if user_id == admin_id:
                continue
                
            try:
                bot.send_message(
                    user_id, 
                    "📢 <b>Важное сообщение от разработчика:</b>", 
                    parse_mode="HTML"
                )
                
                bot.copy_message(user_id, admin_id, draft_id)
                success_count += 1
                
                time.sleep(0.05) 
            except:
                pass

        bot.send_message(
            admin_id, 
            f"✅ *Рассылка завершена!*\nДоставлено: {success_count}",
            parse_mode="Markdown"
        )
        send_menu(admin_id)
        state.broadcast_drafts.pop(admin_id, None)


@bot.message_handler(commands=['stats'])
def admin_stats(message):
    """
    @brief Выводит статистику бота (только для админов).
    """
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "Я не знаю такую команду 🥺")
        return

    total_users, total_pairs = db.bot_db.get_stats()
    
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
    """
    @brief Инициализация процесса отправки любовного послания.
    """
    if db.bot_db.get_partner(message.chat.id):
        state.waiting_for_message[message.chat.id] = True
        
        markup = types.InlineKeyboardMarkup()
        btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_love")
        markup.add(btn_cancel)

        bot.send_message(
            message.chat.id, 
            "Пришли мне послание (текст, фото, стикер, голос или кружочек) 💌\n"
            "Чтобы отправить фото с текстом, просто добавь описание к картинке!", 
            reply_markup=markup
        )
    else:
        send_no_partner_error(message.chat.id)


@bot.message_handler(func=lambda message: message.text == "💌 Послание")
def love_button_handler(message):
    """
    @brief Перехват кнопки "💌 Послание".
    """
    love(message)


@bot.callback_query_handler(func=lambda call: call.data == "cancel_love")
def cancel_love_callback(call):
    """
    @brief Отмена создания любовного послания.
    """
    user_id = call.message.chat.id
    
    state.waiting_for_message.pop(user_id, None)
    
    bot.edit_message_text("Отправка послания отменена 🛑", user_id, call.message.message_id)
    send_menu(user_id, "Главное меню 👇")


@bot.message_handler(
    func=lambda m: m.chat.id in state.waiting_for_message, 
    content_types=['text', 'photo', 'voice', 'video', 'video_note', 'document', 'sticker', 'audio', 'animation']
)
def receive_love_draft(message):
    """
    @brief Сохраняет контент любовного послания как черновик.
    """
    if message.content_type == 'text' and message.text in ["💌 Послание", "❓ Помощь", "🔄 Перезапуск"]:
        state.waiting_for_message.pop(message.chat.id, None)
        if message.text == "💌 Послание":
            love(message)
        elif message.text == "❓ Помощь":
            help_command(message)
        else:
            start(message)
        return

    if message.content_type == 'text' and message.text.startswith('/'):
        state.waiting_for_message.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    state.waiting_for_message.pop(message.chat.id, None)
    state.draft_messages[message.chat.id] = message.message_id

    markup = types.InlineKeyboardMarkup()
    btn_send = types.InlineKeyboardButton("Отправить 💌", callback_data="draft_send")
    btn_send_cat = types.InlineKeyboardButton("С котёнком 🐱", callback_data="draft_send_cat")
    btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="draft_cancel")
    markup.add(btn_send, btn_send_cat)
    markup.add(btn_cancel)

    bot.reply_to(message, "Послание готово. Отправляем?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ["draft_send", "draft_cancel"])
def process_draft(call):
    """
    @brief Отправка обычного черновика партнеру.
    """
    user_id = call.message.chat.id
    
    if call.data == "draft_cancel":
        state.draft_messages.pop(user_id, None)
        bot.edit_message_text("Отправка отменена 🗑️", user_id, call.message.message_id)
        send_menu(user_id)
        return

    if call.data == "draft_send":
        message_id = state.draft_messages.get(user_id)
        partner_id = db.bot_db.get_partner(user_id)
        
        if not message_id or not partner_id:
            bot.edit_message_text("⚠️ Ошибка: черновик не найден или бот отключился.", user_id, call.message.message_id)
            send_menu(user_id)
            return
            
        sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
        bot.send_message(partner_id, f"💌 Новое послание от {sender_text}:")
        
        bot.copy_message(partner_id, user_id, message_id)

        db.bot_db.update_streak(user_id, partner_id)

        bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
        send_menu(user_id)
        state.draft_messages.pop(user_id, None)


@bot.callback_query_handler(func=lambda call: call.data == "draft_send_cat")
def process_draft_cat(call):
    """
    @brief Отправка послания, наложенного на мем с котиком.
    """
    user_id = call.message.chat.id
    message_id = state.draft_messages.get(user_id)
    partner_id = db.bot_db.get_partner(user_id)

    if not message_id or not partner_id:
        bot.edit_message_text("⚠️ Ошибка: черновик не найден или бот отключился.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    try:
        forwarded = bot.forward_message(user_id, user_id, message_id)
        bot.delete_message(user_id, forwarded.message_id)

        if forwarded.content_type == 'text':
            text = forwarded.text.strip()
        else:
            bot.send_message(user_id, "⚠️ Наложение текста на картинку поддерживается только для текстовых сообщений. Отправляю обычное послание.")
            sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
            bot.send_message(partner_id, f"💌 Новое послание от {sender_text}:")
            bot.copy_message(partner_id, user_id, message_id)
            bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
            state.draft_messages.pop(user_id, None)
            send_menu(user_id)
            return
    except Exception as e:
        bot.edit_message_text(f"⚠️ Ошибка при получении черновика: {e}", user_id, call.message.message_id)
        send_menu(user_id)
        return

    if not text:
        text = "🐱 Мур-мур!"

    cat_bytes = get_local_cat_image()
    if cat_bytes is None:
        bot.edit_message_text("⚠️ Не удалось загрузить картинку кота. Отправляю обычное послание.", user_id, call.message.message_id)
        sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
        bot.send_message(partner_id, f"💌 Новое послание от {sender_text}:")
        bot.copy_message(partner_id, user_id, message_id)
        bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
        state.draft_messages.pop(user_id, None)
        send_menu(user_id)
        return

    meme_bytes = generate_cat_meme_optimized(cat_bytes, text)
    if meme_bytes is None:
        bot.edit_message_text("⚠️ Ошибка при создании картинки. Отправляю обычное послание.", user_id, call.message.message_id)
        sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
        bot.send_message(partner_id, f"💌 Новое послание от {sender_text}:")
        bot.copy_message(partner_id, user_id, message_id)
        bot.edit_message_text("Отправлено! 💕", user_id, call.message.message_id)
        state.draft_messages.pop(user_id, None)
        send_menu(user_id)
        return

    sender_text = get_text_by_gender(user_id, "твоего котика 🐈‍⬛", "твоей кошечки 🐈")
    bot.send_message(partner_id, f"💌 Новое послание от {sender_text} (с котёнком 🐱):")
    bot.send_photo(partner_id, photo=io.BytesIO(meme_bytes))
    
    db.bot_db.update_streak(user_id, partner_id)

    bot.edit_message_text("✅ Отправлено с котёнком!", user_id, call.message.message_id)
    bot.send_message(user_id, " ", reply_markup=ui_manager.get_main_keyboard(user_id)) 
    state.draft_messages.pop(user_id, None)


def get_local_cat_image() -> bytes:
    """
    @brief Возвращает байты случайного локального изображения котика.
    @return bytes или None при ошибке.
    """
    folder = os.path.join(os.path.dirname(__file__), 'cat_images')
    if not os.path.exists(folder):
        return None

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


def generate_cat_meme_optimized(image_bytes: bytes, text: str, max_size=(1200, 1200), quality=75) -> bytes:
    """
    @brief Генерирует мем с котиком, накладывая текст.
    @param image_bytes Исходное изображение.
    @param text Текст для наложения.
    @return Сгенерированное изображение в байтах или None.
    """
    if image_bytes is None:
        return None

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image.thumbnail(max_size, Image.LANCZOS)

        draw = ImageDraw.Draw(image)

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
            try:
                if hasattr(draw, 'textbbox'):
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                else:
                    text_width, _ = draw.textsize(line, font=font)
            except:
                text_width = len(line) * 20
            x = (img_width - text_width) // 2

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
        print(f"Ошибка в generate_cat_meme_optimized: {e}")
        return None


@bot.message_handler(commands=['streak'])
def streak_command(message):
    """
    @brief Обработчик команды /streak. Показывает счетчик дней подряд.
    """
    partner_id = db.bot_db.get_partner(message.chat.id)
    if not partner_id:
        bot.send_message(message.chat.id, "❌ У тебя нет пары, чтобы смотреть серию.")
        return

    streak = db.bot_db.get_streak(message.chat.id, partner_id)
    if streak == 0:
        bot.send_message(message.chat.id, "💔 У вас пока нет серии. Отправляйте друг другу послания каждый день!")
    else:
        bot.send_message(message.chat.id, f"🔥 Ваша серия: {streak} дней подряд! Продолжайте в том же духе!")

@bot.message_handler(func=lambda message: message.text == "🔥 Серия")
def streak_button_handler(message):
    """
    @brief Перехват кнопки главного меню "🔥 Серия".
    """
    streak_command(message)

# ==========================================
# МЕНЮ ВИШЛИСТА И ВАЖНЫХ ДАТ
# ==========================================

@bot.message_handler(func=lambda message: message.text == "🎁 Вишлист")
def wishlist_menu_handler(message):
    """
    @brief Обработчик кнопки главного меню "🎁 Вишлист".
    """
    show_wishlist_menu(message.chat.id)


def show_wishlist_menu(chat_id: int):
    """
    @brief Отправляет inline-меню управления вишлистом.
    @param chat_id ID чата пользователя.
    """
    markup = types.InlineKeyboardMarkup()
    btn_view = types.InlineKeyboardButton("📋 Просмотреть", callback_data="wishlist_view")
    btn_add = types.InlineKeyboardButton("➕ Добавить", callback_data="wishlist_add")
    btn_del = types.InlineKeyboardButton("❌ Удалить", callback_data="wishlist_del")
    markup.add(btn_view, btn_add)
    markup.add(btn_del)
    bot.send_message(chat_id, "💕 Меню вишлиста:", reply_markup=markup)


def show_dates_menu(chat_id: int):
    """
    @brief Отправляет inline-меню управления важными датами.
    @param chat_id ID чата пользователя.
    """
    markup = types.InlineKeyboardMarkup()
    btn_view = types.InlineKeyboardButton("📋 Просмотреть", callback_data="dates_view")
    btn_add = types.InlineKeyboardButton("➕ Добавить", callback_data="dates_add")
    btn_del = types.InlineKeyboardButton("❌ Удалить", callback_data="dates_del")
    markup.add(btn_view, btn_add)
    markup.add(btn_del)
    bot.send_message(chat_id, "📅 Меню важных дат:", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "📅 Даты")
def dates_menu_handler(message):
    """
    @brief Обработчик кнопки главного меню "📅 Даты".
    """
    show_dates_menu(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data in ["wishlist_view", "wishlist_add", "wishlist_del", "dates_view", "dates_add", "dates_del"])
def process_wishlist_dates_menu(call):
    """
    @brief Центральный обработчик inline-кнопок для меню вишлиста и дат.
    """
    user_id = call.message.chat.id
    if call.data == "wishlist_view":
        wishlist(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == "wishlist_add":
        add_wish_start(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == "wishlist_del":
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


# ==========================================
# ЧЕРНЫЙ СПИСОК (БЛОКИРОВКА)
# ==========================================

@bot.message_handler(commands=['blacklist'])
def blacklist_command(message):
    """
    @brief Показывает список заблокированных пользователей.
    """
    blocked_users = db.bot_db.get_blocked_users(message.chat.id)
    
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
    """
    @brief Запускает процесс блокировки пользователя.
    """
    state.waiting_for_block[message.chat.id] = True
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_block"))
    
    bot.send_message(
        message.chat.id, 
        "Введи ID или @username котейки, которую хочешь заблокировать 🛑:",
        reply_markup=markup
    )


@bot.message_handler(commands=['unblock'])
def unblock_command(message):
    """
    @brief Запускает процесс разблокировки пользователя.
    """
    state.waiting_for_unblock[message.chat.id] = True
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_unblock"))
    
    bot.send_message(
        message.chat.id, 
        "Введи ID или @username котейки для разблокировки 🔓:",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data in ["cancel_block", "cancel_unblock"])
def cancel_block_unblock(call):
    """
    @brief Отменяет процесс блокировки/разблокировки.
    """
    user_id = call.message.chat.id
    if call.data == "cancel_block":
        state.waiting_for_block.pop(user_id, None)
        bot.edit_message_text("Блокировка отменена.", user_id, call.message.message_id)
    else:
        state.waiting_for_unblock.pop(user_id, None)
        bot.edit_message_text("Разблокировка отменена.", user_id, call.message.message_id)
    send_menu(user_id)


@bot.message_handler(func=lambda m: m.chat.id in state.waiting_for_block or m.chat.id in state.waiting_for_unblock)
def process_block_unblock(message):
    """
    @brief Обрабатывает введенный ID или никнейм для бана или разбана.
    """
    user_id = message.chat.id
    is_blocking = user_id in state.waiting_for_block
    
    if message.content_type != 'text' or message.text in ["💌 Послание", "❓ Помощь", "🔄 Перезапуск"] or message.text.startswith('/'):
        state.waiting_for_block.pop(user_id, None)
        state.waiting_for_unblock.pop(user_id, None)
        if message.content_type == 'text' and not message.text.startswith('/'):
            catch_all_messages(message)
        return

    raw_input = message.text.strip()
    target_id = None

    if raw_input.startswith('@'):
        target_id = db.bot_db.get_id_by_username(raw_input)
        if not target_id:
            bot.send_message(user_id, "⚠️ Котейки с таким ником нет в базе бота.")
            return
    else:
        try:
            target_id = int(raw_input)
        except ValueError:
            bot.send_message(user_id, "❌ Введи корректный числовой ID или @username.")
            return

    if target_id == user_id:
        self_word = get_text_by_gender(user_id, "самого себя", "саму себя")
        bot.send_message(user_id, f"Ты не можешь заблокировать или разблокировать {self_word}!")
        return

    if is_blocking:
        db.bot_db.block_user(user_id, target_id)
        state.waiting_for_block.pop(user_id, None)
        
        target_name = get_user_display_name(target_id)
        bot.send_message(user_id, f"🛑 Котейка {target_name} добавлен(а) в черный список.")
        
        if db.bot_db.get_partner(user_id) == target_id:
            db.bot_db.unlink_partners(user_id)
            bot.send_message(user_id, "💔 Так как вы были в паре, связь автоматически разорвана.", reply_markup=ui_manager.get_main_keyboard(user_id))
            try:
                initiator_text = get_text_by_gender(user_id, "Твой котик разорвал", "Твоя кошечка разорвала")
                bot.send_message(target_id, f"💔 {initiator_text} связь.", reply_markup=ui_manager.get_main_keyboard(target_id))
            except:
                pass
    else:
        db.bot_db.unblock_user(user_id, target_id)
        state.waiting_for_unblock.pop(user_id, None)
        
        target_name = get_user_display_name(target_id)
        bot.send_message(user_id, f"🔓 Котейка {target_name} больше не в черном списке.")
        
    send_menu(user_id)

# ==========================================
# ВАЖНЫЕ ДАТЫ И УДАЛЕНИЕ
# ==========================================

@bot.message_handler(commands=['adddate'])
def add_date_start(message):
    """
    @brief Начинает процесс добавления важной даты.
    """
    partner_id = db.bot_db.get_partner(message.chat.id)
    if not partner_id:
        bot.send_message(message.chat.id, "❌ У тебя нет пары! Сначала подключись через /connect")
        return

    state.waiting_for_date_partner[message.chat.id] = partner_id
    state.waiting_for_date_title[message.chat.id] = True

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))

    bot.send_message(message.chat.id, "📅 Введи название важной даты (например: «Годовщина свадьбы»):",
                     reply_markup=markup)


@bot.message_handler(func=lambda m: m.chat.id in state.waiting_for_date_title)
def get_date_title(message):
    """
    @brief Получает название важной даты.
    """
    if message.text.startswith('/'):
        state.waiting_for_date_title.pop(message.chat.id, None)
        state.waiting_for_date_partner.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    if message.text in ["💌 Послание", "❓ Помощь", "🔄 Перезапуск"]:
        state.waiting_for_date_title.pop(message.chat.id, None)
        state.waiting_for_date_partner.pop(message.chat.id, None)
        if message.text == "💌 Послание":
            love(message)
        elif message.text == "❓ Помощь":
            help_command(message)
        else:
            start(message)
        return

    state.waiting_for_date_title.pop(message.chat.id, None)
    state.waiting_for_date_value[message.chat.id] = message.text

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))
    bot.send_message(message.chat.id, "📆 Введи дату в формате ДД.ММ.ГГГГ (например: 14.02.2025):",
                     reply_markup=markup)


@bot.message_handler(func=lambda m: m.chat.id in state.waiting_for_date_value)
def get_date_value(message):
    """
    @brief Получает и валидирует значение важной даты.
    """
    if message.text.startswith('/'):
        state.waiting_for_date_value.pop(message.chat.id, None)
        state.waiting_for_date_partner.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    try:
        date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        event_date = date_obj.strftime("%Y-%m-%d")

        title = state.waiting_for_date_value.pop(message.chat.id, None)
        state.waiting_for_date_type[message.chat.id] = (title, event_date, message.text)

        markup = types.InlineKeyboardMarkup()
        btn_once = types.InlineKeyboardButton("Однократная 🔂", callback_data="date_type_once")
        btn_annual = types.InlineKeyboardButton("Ежегодная 🔁", callback_data="date_type_annual")
        btn_cancel = types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate")
        markup.add(btn_once, btn_annual)
        markup.add(btn_cancel)

        bot.send_message(message.chat.id, "🔄 Это повторяющаяся дата (каждый год) или однократная?",
                         reply_markup=markup)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат! Введи дату как ДД.ММ.ГГГГ (например: 14.02.2025)")


@bot.callback_query_handler(func=lambda call: call.data in ["date_type_once", "date_type_annual", "cancel_adddate"])
def process_date_type(call):
    """
    @brief Обрабатывает выбор типа даты (ежегодная/однократная).
    """
    user_id = call.message.chat.id

    if call.data == "cancel_adddate":
        for d in [state.waiting_for_date_title, state.waiting_for_date_value, state.waiting_for_date_type,
                  state.waiting_for_date_remind, state.waiting_for_date_partner]:
            d.pop(user_id, None)
        bot.edit_message_text("❌ Добавление даты отменено.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    is_annual = 1 if call.data == "date_type_annual" else 0
    title, event_date, original_date_str = state.waiting_for_date_type[user_id]
    state.waiting_for_date_type.pop(user_id, None)
    state.waiting_for_date_remind[user_id] = (title, event_date, is_annual, original_date_str)

    markup = types.InlineKeyboardMarkup()
    for days, label in [(1, "За 1 день"), (3, "За 3 дня"), (7, "За неделю"), (30, "За месяц")]:
        markup.add(types.InlineKeyboardButton(label, callback_data=f"remind_{days}"))
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_adddate"))

    bot.edit_message_text("⏰ За сколько дней до даты прислать напоминание?",
                          user_id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("remind_"))
def process_remind_days(call):
    """
    @brief Обрабатывает выбор количества дней для напоминания.
    """
    user_id = call.message.chat.id
    remind_days = int(call.data.split("_")[1])

    if user_id not in state.waiting_for_date_remind:
        bot.answer_callback_query(call.id, "❌ Сессия истекла, начни заново через /adddate")
        return

    title, event_date, is_annual, original_date_str = state.waiting_for_date_remind[user_id]
    partner_id = state.waiting_for_date_partner.get(user_id)

    if not partner_id:
        bot.edit_message_text("❌ Ошибка: партнёр не найден.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    state.waiting_for_date_confirm[user_id] = {
        'title': title,
        'event_date': event_date,
        'is_annual': is_annual,
        'remind_days': remind_days,
        'original_date_str': original_date_str,
        'partner_id': partner_id
    }

    state.waiting_for_date_remind.pop(user_id, None)
    state.waiting_for_date_partner.pop(user_id, None)

    date_display = original_date_str if not is_annual else original_date_str[:5]
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_date_add"),
        types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_date_add")
    )
    bot.edit_message_text(
        f"📅 Проверь данные:\n\nНазвание: {title}\nДата: {date_display}\n"
        f"Тип: {'Ежегодная' if is_annual else 'Однократная'}\n"
        f"Напоминание за {remind_days} дн.\n\nВсё верно?",
        user_id, call.message.message_id, reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data in ["confirm_date_add", "cancel_date_add"])
def confirm_date_add(call):
    """
    @brief Сохраняет важную дату после подтверждения.
    """
    user_id = call.message.chat.id
    if call.data == "cancel_date_add":
        state.waiting_for_date_confirm.pop(user_id, None)
        bot.edit_message_text("Добавление даты отменено.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    data = state.waiting_for_date_confirm.get(user_id)
    if not data:
        bot.edit_message_text("❌ Данные потеряны. Начни заново.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    db.bot_db.add_important_date(user_id, data['partner_id'], data['title'], data['event_date'], data['is_annual'], data['remind_days'])
    state.waiting_for_date_confirm.pop(user_id, None)

    date_display = data['original_date_str'] if not data['is_annual'] else data['original_date_str'][:5]
    bot.edit_message_text(
        f"✅ Дата «{data['title']}» ({date_display}) добавлена!\n⏰ Напоминание за {data['remind_days']} дн.",
        user_id, call.message.message_id
    )
    send_menu(user_id)


@bot.message_handler(commands=['mydates'])
def list_dates(message):
    """
    @brief Показывает все важные даты пользователя.
    """
    dates = db.bot_db.get_dates_for_user(message.chat.id)
    if not dates:
        bot.send_message(message.chat.id, "📭 У вас пока нет общих важных дат. Добавь через /adddate")
        return

    today = datetime.now().date()

    text = "📅 *Ваши общие важные даты:*\n\n"
    for date_id, title, event_date, is_annual, remind_days in dates:
        date_obj = datetime.strptime(event_date, "%Y-%m-%d").date()

        if is_annual:
            next_date = date_obj.replace(year=today.year)
            if next_date < today:
                next_date = next_date.replace(year=today.year + 1)
            days_left = (next_date - today).days
            date_str = f"каждый год {event_date[5:]}"
        else:
            days_left = (date_obj - today).days
            date_str = event_date

        if days_left >= 0:
            status = f" (через {days_left} дн.)"
        else:
            status = " (прошла)"

        text += f"• *{title}* — {date_str}{status}\n"
        text += f"  `id:{date_id}` | напом. за {remind_days} дн.\n"

    text += "\nУдалить: `/deldate <id>`"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


def delwish_interactive(user_id: int):
    """
    @brief Запускает процесс удаления элемента из вишлиста.
    """
    state.waiting_for_delwish_id[user_id] = True
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_delwish"))
    bot.send_message(user_id, "Введи ID элемента вишлиста, который хочешь удалить:", reply_markup=markup)


def deldate_interactive(user_id: int):
    """
    @brief Запускает процесс удаления важной даты.
    """
    state.waiting_for_deldate_id[user_id] = True
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить ❌", callback_data="cancel_deldate"))
    bot.send_message(user_id, "Введи ID важной даты, которую хочешь удалить:", reply_markup=markup)


@bot.message_handler(commands=['delwish'])
def delwish_command(message):
    """
    @brief Команда для удаления желания.
    """
    delwish_interactive(message.chat.id)


@bot.message_handler(commands=['deldate'])
def deldate_command(message):
    """
    @brief Команда для удаления важной даты.
    """
    deldate_interactive(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data in ["cancel_delwish", "cancel_deldate"])
def cancel_delete(call):
    """
    @brief Отменяет процесс удаления.
    """
    user_id = call.message.chat.id
    if call.data == "cancel_delwish":
        state.waiting_for_delwish_id.pop(user_id, None)
        bot.edit_message_text("Удаление вишлиста отменено.", user_id, call.message.message_id)
    else:
        state.waiting_for_deldate_id.pop(user_id, None)
        bot.edit_message_text("Удаление даты отменено.", user_id, call.message.message_id)
    send_menu(user_id)


@bot.message_handler(func=lambda m: m.chat.id in state.waiting_for_delwish_id or m.chat.id in state.waiting_for_deldate_id)
def process_delete_id(message):
    """
    @brief Обрабатывает ID для удаления вишлиста или даты.
    """
    user_id = message.chat.id
    is_wish = user_id in state.waiting_for_delwish_id
    if message.content_type != 'text':
        bot.send_message(user_id, "❌ Пожалуйста, отправь ID числом.")
        return
    try:
        item_id = int(message.text.strip())
    except ValueError:
        bot.send_message(user_id, "❌ ID должен быть числом. Попробуй ещё раз.")
        return

    if is_wish:
        wish = db.bot_db.get_wish_by_id(item_id)
        if not wish:
            bot.send_message(user_id, "❌ Элемент с таким ID не найден.")
            return
        if not db.bot_db.is_wish_owner(user_id, item_id):
            bot.send_message(user_id, "❌ У тебя нет прав на удаление этого элемента.")
            return
            
        wish_id, wish_type, title, description, creator_id = wish
        confirm_markup = types.InlineKeyboardMarkup()
        confirm_markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_delwish_{item_id}"),
            types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_delwish")
        )
        emoji = "🎁" if wish_type == "gift" else ("🌆" if wish_type == "date" else "💭")
        bot.send_message(user_id,
            f"Ты хочешь удалить:\n{emoji} *{title}*\n📝 {description}\n\nПодтверждаешь?",
            parse_mode="Markdown", reply_markup=confirm_markup)
        state.waiting_for_delwish_id.pop(user_id, None)
    else:
        date = db.bot_db.get_date_by_id(item_id)
        if not date:
            bot.send_message(user_id, "❌ Дата с таким ID не найдена.")
            return
        if not db.bot_db.is_date_owner(user_id, item_id):
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
        state.waiting_for_deldate_id.pop(user_id, None)

# ==========================================
# ВИШЛИСТ ПАРЫ (ДОБАВЛЕНИЕ И ПРОСМОТР)
# ==========================================

@bot.message_handler(commands=['addwish'])
def add_wish_start(message):
    """
    @brief Начинает процесс добавления элемента в вишлист.
    """
    partner_id = db.bot_db.get_partner(message.chat.id)
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
    """
    @brief Сохраняет тип добавляемого желания.
    """
    user_id = call.message.chat.id
    if call.data == "wish_cancel":
        state.waiting_for_wish_type.pop(user_id, None)
        state.waiting_for_wish_title.pop(user_id, None)
        state.waiting_for_wish_description.pop(user_id, None)
        bot.edit_message_text("Добавление отменено 🛑", user_id, call.message.message_id)
        send_menu(user_id)
        return

    if call.data == "wish_gift":
        wish_type = "gift"
    elif call.data == "wish_date":
        wish_type = "date"
    elif call.data == "wish_wish":
        wish_type = "wish"
    else:
        return

    state.waiting_for_wish_type[user_id] = wish_type
    state.waiting_for_wish_title[user_id] = True
    bot.edit_message_text("✍️ Введи название:", user_id, call.message.message_id)


@bot.message_handler(func=lambda m: m.chat.id in state.waiting_for_wish_title)
def get_wish_title(message):
    """
    @brief Сохраняет название желания.
    """
    if message.text.startswith('/'):
        state.waiting_for_wish_title.pop(message.chat.id, None)
        state.waiting_for_wish_type.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    state.waiting_for_wish_title.pop(message.chat.id, None)

    state.waiting_for_wish_description[message.chat.id] = {
        "title": message.text
    }

    bot.send_message(
        message.chat.id,
        "📝 Теперь введи описание:"
    )


@bot.message_handler(func=lambda m: m.chat.id in state.waiting_for_wish_description)
def get_wish_description(message):
    """
    @brief Сохраняет описание желания и выводит сводку для подтверждения.
    """
    if message.text.startswith('/'):
        state.waiting_for_wish_description.pop(message.chat.id, None)
        state.waiting_for_wish_type.pop(message.chat.id, None)
        send_menu(message.chat.id, "Отмена.")
        return

    user_id = message.chat.id
    title = state.waiting_for_wish_description[user_id]["title"]
    description = message.text
    wish_type = state.waiting_for_wish_type[user_id]

    state.waiting_for_wish_confirm[user_id] = {
        'type': wish_type,
        'title': title,
        'description': description
    }

    state.waiting_for_wish_description.pop(user_id, None)
    state.waiting_for_wish_type.pop(user_id, None)

    emoji = "🎁" if wish_type == "gift" else ("🌆" if wish_type == "date" else "💭")
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_wish_add"),
        types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_wish_add")
    )
    bot.send_message(user_id,
        f"📝 Проверь данные:\n\n{emoji} *{title}*\n📝 {description}\n\nВсё верно?",
        parse_mode="Markdown", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ["confirm_wish_add", "cancel_wish_add"])
def confirm_wish_add(call):
    """
    @brief Финализирует добавление элемента в вишлист и уведомляет партнера.
    """
    user_id = call.message.chat.id
    if call.data == "cancel_wish_add":
        state.waiting_for_wish_confirm.pop(user_id, None)
        bot.edit_message_text("Добавление вишлиста отменено.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    data = state.waiting_for_wish_confirm.get(user_id)
    if not data:
        bot.edit_message_text("❌ Данные потеряны. Начни заново.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    partner_id = db.bot_db.get_partner(user_id)
    if not partner_id:
        bot.edit_message_text("❌ У тебя нет пары.", user_id, call.message.message_id)
        send_menu(user_id)
        return

    db.bot_db.add_wish(user_id, partner_id, user_id, data['type'], data['title'], data['description'])
    state.waiting_for_wish_confirm.pop(user_id, None)

    emoji = "🎁" if data['type'] == "gift" else ("🌆" if data['type'] == "date" else "💭")
    bot.edit_message_text(f"✅ Добавлено в вишлист!\n\n{emoji} {data['title']}\n📝 {data['description']}", user_id, call.message.message_id)

    creator_text = get_text_by_gender(user_id, "Твой котик 🐈‍⬛", "Твоя кошечка 🐈")
    try:
        bot.send_message(partner_id, f"💕 {creator_text} добавил(а) новую идею в вишлист!\n\n{emoji} {data['title']}\n📝 {data['description']}")
    except:
        pass
    send_menu(user_id)


@bot.message_handler(commands=['wishlist'])
def wishlist(message):
    """
    @brief Показывает общий вишлист пары.
    """
    wishes = db.bot_db.get_wishlist(message.chat.id)

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
        else:
            emoji = "💭"

        creator = f"@{username}" if username else creator_id

        text += (
            f"`id:{wish_id}` {emoji} *{title}*\n"
            f"📝 {description}\n"
            f"👤 Добавил(а): {creator}\n\n"
        )

    text += "Удаление: `/delwish id`"

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown"
    )

# ==========================================
# ЛОВУШКА ДЛЯ СЛУЧАЙНЫХ СООБЩЕНИЙ
# ==========================================

@bot.message_handler(content_types=['text', 'photo', 'voice', 'video', 'video_note', 'document', 'sticker', 'audio', 'animation'])
def catch_all_messages(message):
    """
    @brief Ловушка для обработки нераспознанных сообщений.
    @details Срабатывает, если пользователь отправил случайный текст или очистил историю чата.
    """
    if db.bot_db.get_partner(message.chat.id):
        send_menu(message.chat.id, "Я не знаю такую команду 🥺\nНо вот твоё главное меню 👇")
    else:
        start(message)

# ==========================================
# СИСТЕМА НАПОМИНАНИЙ (ФОНОВЫЙ ПОТОК)
# ==========================================

def check_and_send_reminders():
    """
    @brief Проверяет наличие дат для напоминаний и рассылает их.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    dates_to_remind = db.bot_db.get_dates_to_remind(today_str)

    for date_id, user1_id, user2_id, title, event_date, is_annual, remind_days in dates_to_remind:
        current_year = datetime.now().year

        if db.bot_db.was_reminder_sent(date_id, current_year):
            continue

        for user_id in (user1_id, user2_id):
            try:
                if is_annual:
                    msg = f"🎉 *Ежегодное напоминание!*\nЧерез {remind_days} дн. — {title} ({event_date[5:]})"
                else:
                    msg = f"📅 *Напоминание!*\nЧерез {remind_days} дн. — {title} ({event_date})"

                bot.send_message(user_id, msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Не удалось отправить напоминание {user_id}: {e}")

        db.bot_db.mark_reminder_sent(date_id, current_year)


def reminder_loop():
    """
    @brief Фоновая задача для регулярной проверки напоминаний.
    """
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
    db.bot_db.init_db()

    reminder_thread = threading.Thread(target=reminder_loop, daemon=True)
    reminder_thread.start()

    print("Бот запущен и готов к работе (ООП версия)...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=90) 
        except Exception as e:
            print(f"⚠️ Ошибка связи с Telegram. Жду 5 секунд... Ошибка: {e}")
            time.sleep(5)