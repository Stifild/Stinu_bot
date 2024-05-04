import telebot, logging, os
from config import LOGS_PATH, TELEGRAM_TOKEN, ADMIN_LIST
from iop import IOP, SpeechKit, GPT, Monetize

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
    result: bool | tuple[bool, str] = sk.tts(message)
    if result == True:
        bot.send_message(message.chat.id, "Лови результат:")
        with open(f"./data/temp/{str(message.from_user.id)}.ogg", "rb") as file:
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
    bot.send_message(message.chat.id, "Присылай голос")
    bot.register_next_step_handler(message, stt)

def stt(message: telebot.types.Message):
    if message.content_type != "voice":
        bot.send_message(message.chat.id, "Это не голос")
        return
    result: tuple[bool, str] = sk.stt(message, bot)
    if result[0] == True:
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

@bot.message_handler(commands=['/debt'])
def update_debts(message:telebot.types.Message):
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
                (
                    ("Выбрать голос", "voice"),
                    ("Выбрать скорость", "speed"),
                    ("Показать счет", "debt")
                )
            ),
        )
    else:
        logging.error("Message is None")

@bot.callback_query_handler(func=lambda call: call.data == "debt")
def get_debt(call):
    message: telebot.types.Message = (
        call.message if call.message else call.callback_query.message
    )
    update_debts(message)
    id = message.from_user.id
    bot.send_message(id, f"Вот твой счет:\n\nЗа использование Speech to text: {mt.cost_calculation(id, 'stt')}\nЗа использование Text to speech: {mt.cost_calculation(id, 'tts')}\nЗа использование YaGPT: {mt.cost_calculation(id, 'gpt')}\n **В Итоге:** {io.db(id)['debt']}")
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


def select_voice(message):
    if message.text in io.list_voices():
        io.db[str(message.from_user.id)]["voice"] = message.text
        bot.send_message(
            message.chat.id,
            f'Теперь используется голос "{message.text}"',
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
        io.db[str(message.from_user.id)]["emotion"] = message.text
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
        io.db[str(message.from_user.id)]["speed"] = message.text
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
    if message.content_type == "voice":
        text: tuple[bool, str] = sk.stt(message, bot)
        if text[0] == True:
            answer = gpt.asking_gpt(message.from_user.id, text[1])
            bot.send_message(message.chat.id, answer, reply_markup=telebot.util.quick_markup({"Меню": {"callback_data": "menu"}}))
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
        answer = gpt.asking_gpt(message.from_user.id, message.text)
        bot.send_message(message.chat.id, answer, reply_markup=telebot.util.quick_markup({"Меню": {"callback_data": "menu"}}))


bot.infinity_polling()
