import telebot, logging, os
from config import LOGS_PATH, TELEGRAM_TOKEN, ADMIN_LIST
from iop import IOP, SpeechKit, GPT, Monetize, Database

db = Database()
io = IOP()
sk = SpeechKit()
gpt = GPT()
mt = Monetize()
rm = telebot.types.ReplyKeyboardRemove()

logging.basicConfig(
    filename=LOGS_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def is_ban(id):
    return db.get_user_data(id).get("ban")
@bot.message_handler(commands=["fire_exit"])
def fire_exit(message: telebot.types.Message):
    if message.from_user.id in ADMIN_LIST:
        for user in ADMIN_LIST:
            bot.send_message(user, "Запущена аварийная остановка бота!!!")
        bot.stop_polling()
        exit()


@bot.message_handler(commands=["start"])
def start(message: telebot.types.Message):
    bot.send_message(
        message.chat.id,
        "Привет! Я бот для работы с SpeachKit. Напиши /help для подробностей",
    )
    io.sing_up(message.from_user.id)


@bot.message_handler(commands=["help"])
def help(message):
    bot.send_message(
        message.chat.id,
        "Список команд:\n/tts <текст> - озвучить текст\n/menu - показать меню\n/stt - расшифровать аудио",
        reply_markup=(
            telebot.util.quick_markup(
                {
                    "Язык разметки tts": {
                        "url": "https://yandex.cloud/ru/docs/speechkit/tts/markup/tts-markup"
                    }
                }
            )
        ),
    )


@bot.message_handler(commands=["tts"])
def tts(message: telebot.types.Message):
    if not is_ban(message.from_user.id):
        bot.send_chat_action(message.chat.id, "record_voice")
        result: bool | tuple[bool, str] = sk.tts(message)
        if result == True:
            bot.send_message(message.chat.id, "Лови результат:")

            with open(f"./data/temp/{str(message.from_user.id)}.ogg", "rb") as file:
                bot.send_chat_action(message.chat.id, "upload_voice")
                bot.send_audio(
                    message.chat.id,
                    file,
                    reply_markup=telebot.util.quick_markup(
                        {"Меню": {"callback_data": "menu"}}
                    ),
                )
            os.remove(f"./data/temp/{str(message.from_user.id)}.ogg")
        elif not result[0]:
            bot.send_message(
                message.chat.id,
                result[1],
                reply_markup=(
                    telebot.util.quick_markup(
                        {
                            "Вики по кодам ошибок": {
                                "url": "https://ru.wikipedia.org/wiki/Список_кодов_состояния_HTTP#Обзорный_список"
                            },
                            "Меню": {"callback_data": "menu"},
                        },
                        1,
                    )
                    if "кодом:" in result[1]
                    else telebot.util.quick_markup({"Меню": {"callback_data": "menu"}})
                ),
            )


@bot.message_handler(commands=["stt"])
def stt_notification(message: telebot.types.Message):
    if not is_ban(message.from_user.id):
        bot.send_message(message.chat.id, "Присылай голос")
        bot.register_next_step_handler(message, stt)


def stt(message: telebot.types.Message):
    if not is_ban(message.from_user.id):
        if message.content_type != "voice":
            bot.send_message(message.chat.id, "Это не голос")
            return
        result: tuple[bool, str] = sk.stt(message, bot)
        if result[0]:
            bot.send_message(
                message.chat.id,
                result[1],
                reply_markup=telebot.util.quick_markup({"Меню": {"callback_data": "menu"}}),
            )
        elif not result[0]:
            bot.send_message(
                message.chat.id,
                result[1],
                reply_markup=(
                    telebot.util.quick_markup(
                        {
                            "Вики по кодам ошибок": {
                                "url": "https://ru.wikipedia.org/wiki/Список_кодов_состояния_HTTP#Обзорный_список"
                            },
                            "Меню": {"callback_data": "menu"},
                        },
                        1,
                    )
                    if "кодом:" in result[1]
                    else telebot.util.quick_markup({"Меню": {"callback_data": "menu"}})
                ),
            )


@bot.message_handler(commands=['debt'])
def update_debts(message: telebot.types.Message):
    mt.update_debts()


@bot.callback_query_handler(func=lambda call: call.data == "menu")
@bot.message_handler(commands=["menu"])
def menu(call):
    message: telebot.types.Message = (
        call.message
        if hasattr(call, "message")
        else call.message if isinstance(call, telebot.types.CallbackQuery) else call
    )

    if message is not None:
        bot.send_message(
            message.chat.id,
            "Меню:",
            reply_markup=io.get_inline_keyboard(
                (("Выбрать голос", "voice"), ("Выбрать скорость", "speed"), ("Показать счет", "debt"),
                 ("Отчистить историю чата", "clear"))))


@bot.callback_query_handler(func=lambda call: call.data == "clear")
def clear_history(call):
    message: telebot.types.Message = (
        call.message if call.message else call.callback_query.message
    )
    bot.delete_message(message.chat.id, message.message_id)
    db.update_value(message.from_user.id, "gpt_chat", "[]")
    bot.send_message(message.chat.id, "История чата очищена")


@bot.callback_query_handler(func=lambda call: call.data == "debt")
def get_debt(call):
    message: telebot.types.Message = (
        call.message if call.message else call.callback_query.message
    )
    bot.delete_message(message.chat.id, message.message_id)
    update_debts(message)
    id = message.chat.id
    stt = round(mt.cost_calculation(id, 'stt'), 2)
    tts = round(mt.cost_calculation(id, 'tts'), 2)
    gpt = round(mt.cost_calculation(id, 'gpt'), 2)
    all = round(mt.cost_calculation(id, 'stt') + mt.cost_calculation(id, 'tts') + mt.cost_calculation(id, 'gpt'), 2)
    bot.send_message(id,
                     f"Вот твой счет:\n\nЗа использование Speech to text: {stt}\nЗа использование Text to speech: {tts}"
                     f"\nЗа использование YaGPT: {gpt}\n **В Итоге:** {all}", parse_mode="Markdown")
    menu(message)


@bot.callback_query_handler(func=lambda call: call.data == "voice")
def choose_voice(call):
    message: telebot.types.Message = (
        call.message if call.message else call.callback_query.message
    )
    bot.delete_message(message.chat.id, message.message_id)
    bot.send_message(
        message.chat.id,
        "Выбери голос:",
        reply_markup=io.get_reply_markup(io.list_voices()),
    )
    bot.register_next_step_handler(message, select_voice)


def select_voice(message: telebot.types.Message):
    if message.text in io.list_voices():
        io.dbc.update_value(message.from_user.id, "voice", message.text)
        bot.send_message(
            message.chat.id,
            f'Теперь используется голос "{message.text}"\n\nВо избежание ошибок перевыберите эмоцию',
            reply_markup=telebot.util.quick_markup(
                {"Выбрать эмоцию": {"callback_data": "emotion"}}
            ),
        )
    else:
        bot.send_message(
            message.chat.id,
            "Неверный выбор. Попробуй ещё раз.",
            reply_markup=io.get_reply_markup(io.list_voices()),
        )
        bot.register_next_step_handler(message, select_voice)


@bot.callback_query_handler(func=lambda call: call.data == "emotion")
def choose_emotion(call):
    message: telebot.types.Message = (
        call.message if call.message else call.callback_query.message
    )
    bot.delete_message(message.chat.id, message.message_id)
    bot.send_message(
        message.chat.id,
        "Выбери эмоцию:",
        reply_markup=io.get_reply_markup(io.list_emotions(message.chat.id)),
    )
    bot.register_next_step_handler(message, select_emotion)


def select_emotion(message):
    if message.text in io.list_emotions(message.from_user.id):
        io.dbc.update_value(message.from_user.id, "emotion", message.text)
        bot.send_message(
            message.chat.id,
            f'Теперь используется эмоция "{message.text}"',
            reply_markup=rm,
        )
        menu(message)
    else:
        bot.send_message(
            message.chat.id,
            "Неверный выбор. Попробуй ещё раз.",
            reply_markup=io.get_reply_markup(io.list_emotions(message.from_user.id)),
        )
        bot.register_next_step_handler(message, select_emotion)


@bot.callback_query_handler(func=lambda call: call.data == "speed")
def choose_speed(call):
    message: telebot.types.Message = (
        call.message if call.message else call.callback_query.message
    )
    bot.delete_message(message.chat.id, message.message_id)
    bot.send_message(message.chat.id, "Задай скорость от 0.1 до 3")
    bot.register_next_step_handler(message, select_speed)


def select_speed(message):
    if float(message.text) >= 0.1 and float(message.text) <= 3.0:
        io.dbc.update_value(message.from_user.id, "speed", int(message.text))
        bot.send_message(
            message.chat.id, f'Теперь используется скорость "{message.text}"'
        )
        menu(message)
    else:
        bot.send_message(message.chat.id, "Неверный выбор. Попробуй ещё раз.")
        bot.register_next_step_handler(message, select_speed)


@bot.message_handler(commands=["log"])
def logs(message: telebot.types.Message):
    with open(LOGS_PATH, "rb") as file:
        (
            bot.send_document(message.chat.id, file)
            if message.from_user.id in ADMIN_LIST
            else None
        )


@bot.message_handler(content_types=["voice", "text"])
def gptp(message: telebot.types.Message):
    if not is_ban(message.from_user.id):
        if message.content_type == "voice":
            text: tuple[bool, str] = sk.stt(message, bot)
            if text[0]:
                bot.send_chat_action(message.chat.id, "typing")
                answer = gpt.asking_gpt(message.from_user.id, text[1], 1)
                bot.send_message(message.chat.id, answer, parse_mode="Markdown")
                bot.send_chat_action(message.chat.id, "record_voice")
                result: bool | tuple[bool, str] = sk.tts(answer, 1, message.from_user.id)
                if result == True:
                    try:
                        bot.send_chat_action(message.chat.id, "upload_voice")
                        with open(f"./data/temp/{str(message.from_user.id)}.ogg", "rb") as file:
                            bot.send_audio(
                                message.chat.id,
                                file,
                                reply_markup=telebot.util.quick_markup(
                                    {"Меню": {"callback_data": "menu"}}
                                ),
                            )
                            os.remove(f"./data/temp/{str(message.from_user.id)}.ogg")
                    except Exception as e:
                        logging.warning(f"Ошибка при отправке голосового сообщения: {e}")
                        bot.send_message(message.chat.id, f"При отправке голосового сообщения произошла ошибка: {e}")

                else:
                    bot.send_message(
                        message.chat.id,
                        result[1],
                        reply_markup=(
                            telebot.util.quick_markup(
                                {
                                    "Вики по кодам ошибок": {
                                        "url": "https://ru.wikipedia.org/wiki/Список_кодов_состояния_HTTP#Обзорный_список"
                                    },
                                    "Меню": {"callback_data": "menu"},
                                },
                                1,
                            )
                            if "кодом:" in result[1]
                            else telebot.util.quick_markup({"Меню": {"callback_data": "menu"}})
                        ),
                    )

            else:
                bot.send_message(
                    message.chat.id,
                    text[1],
                    reply_markup=(
                        telebot.util.quick_markup(
                            {
                                "Вики по кодам ошибок": {
                                    "url": "https://ru.wikipedia.org/wiki/Список_кодов_состояния_HTTP#Обзорный_список"
                                },
                                "Меню": {"callback_data": "menu"},
                            },
                            1,
                        )
                        if "кодом:" in text[1]
                        else telebot.util.quick_markup({"Меню": {"callback_data": "menu"}})
                    ),
                )
        else:
            bot.send_chat_action(message.chat.id, "typing")
            answer = gpt.asking_gpt(message.from_user.id, message.text)
            bot.send_message(message.chat.id, answer,
                             reply_markup=telebot.util.quick_markup({"Меню": {"callback_data": "menu"}}),
                             parse_mode="Markdown")


bot.infinity_polling()
