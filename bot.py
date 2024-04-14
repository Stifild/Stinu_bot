import telebot, logging, iop, json
from config import LOGS_PATH, TELEGRAM_TOKEN
from iop import IOP

io = IOP()

logging.basicConfig(
    filename=LOGS_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
)

bot = telebot.TeleBot(TELEGRAM_TOKEN)


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
        "Список команд:\n/tts <текст> - озвучить текст\n/menu - показать меню",
    )


@bot.message_handler(commands=["tts"])
def tts(message):
    result: bool | tuple[bool, str] = io.tts(message)
    if result is not tuple:
        bot.send_message(message.chat.id, "Лови результат:")
        bot.send_voice(
            message.chat.id,
            f"./data/temp/{message.from_user.id}.mp3",
            inline_keyboard=telebot.util.quick_markup(
                {"Меню": {"callback_data": "menu"}}
            ),
        )
    else:
        bot.send_message(
            message.chat.id,
            result[1],
            inline_keyboard=(
                telebot.util.quick_markup(
                    {
                        "Вики по кодам ошибок": {
                            "url": "https://ru.wikipedia.org/wiki/Список_кодов_состояния_HTTP#Обзорный_список"
                        }
                    }
                )
                if "кодом:" in result[1]
                else None
            ),
        )


@bot.callback_query_handler(func=lambda call: call.data == "menu")
@bot.message_handler(commands=["menu"])
def menu(call):
    message: telebot.types.Message = (
    call.message
    if hasattr(call, 'message')
    else call.message if isinstance(call, telebot.types.CallbackQuery) else call
    )
    if message is not None:
        bot.send_message(
            message.chat.id,
            "Меню:",
            inline_keyboard=io.get_inline_keyboard(
                (
                    ("Выбрать голос", "voice"),
                    ("Выбрать эмоцию", "emotion"),
                    ("Выбрать скорость", "speed"),
                )
            ),
        )
    else:
        logging.error("Message is None")


@bot.callback_query_handler(func=lambda call: call.data == "voice")
def choose_voice(call):
    message: telebot.types.Message = (
        call.message if call.message else call.callback_query.message
    )
    bot.delete_message(message.chat.id, message.message_id)
    bot.send_message(
        message.chat.id,
        "Выбери голос:",
        reply_markup=io.get_reply_markup(io.tuple_voices()),
    )
    bot.register_next_step_handler(message, select_voice)


def select_voice(message):
    if message.text in io.tuple_voices():
        io.db[str(message.from_user.id)]["voice"] = message.text
        bot.send_message(message.chat.id, f'Теперь используется голос "{message.text}"')
        bot.send_message(
            message.chat.id,
            "Меню:",
            inline_keyboard=io.get_inline_keyboard(
                (
                    ("Выбрать голос", "voice"),
                    ("Выбрать эмоцию", "emotion"),
                    ("Выбрать скорость", "speed"),
                )
            ),
        )
    else:
        bot.send_message(
            message.chat.id,
            "Неверный выбор. Попробуй ещё раз.",
            reply_markup=io.get_reply_markup(io.tuple_voices()),
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
        reply_markup=io.get_reply_markup(io.tuple_emotions(message.from_user.id)),
    )
    bot.register_next_step_handler(message, select_emotion)


def select_emotion(message):
    if message.text in io.tuple_emotions(message.from_user.id):
        io.db[str(message.from_user.id)]["emotion"] = message.text
        bot.send_message(
            message.chat.id, f'Теперь используется эмоция "{message.text}"'
        )
        bot.send_message(
            message.chat.id,
            "Меню:",
            inline_keyboard=io.get_inline_keyboard(
                (
                    ("Выбрать голос", "voice"),
                    ("Выбрать эмоцию", "emotion"),
                    ("Выбрать скорость", "speed"),
                )
            ),
        )
    else:
        bot.send_message(
            message.chat.id,
            "Неверный выбор. Попробуй ещё раз.",
            reply_markup=io.get_reply_markup(io.tuple_emotions(message.from_user.id)),
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
        io.db[str(message.from_user.id)]["speed"] = message.text
        bot.send_message(
            message.chat.id, f'Теперь используется скорость "{message.text}"'
        )
        bot.send_message(
            message.chat.id,
            "Меню:",
            inline_keyboard=io.get_inline_keyboard(
                (
                    ("Выбрать голос", "voice"),
                    ("Выбрать эмоцию", "emotion"),
                    ("Выбрать скорость", "speed"),
                )
            ),
        )
    else:
        bot.send_message(message.chat.id, "Неверный выбор. Попробуй ещё раз.")
        bot.register_next_step_handler(message, select_speed)


bot.polling()
