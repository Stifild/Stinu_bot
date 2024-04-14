import logging, json, requests, os, telebot, time
from config import (
    LOGS_PATH,
    JSON_PATH,
    FOLDER_ID,
    TELEGRAM_TOKEN,
    IAM_TOKEN_PATH,
    VJSON_PATH)


os.mkdir("./data/temp")

logging.basicConfig(
    filename=LOGS_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
)


class IOP:

    def __init__(self):
        self.db = self.read_json()

    def write_json(self, data: dict, path: str = JSON_PATH):
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    def read_json(self, path: str = JSON_PATH):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.decoder.JSONDecodeError:
            return {}

    def sing_up(self, id: int):
        self.db[str(id)] = {
            "limit": 500,
            "ban": False,
            "voice": None,
        }
        self.write_json(self.db)

    def tts(self, message: telebot.types.Message) -> bool | tuple[bool, str]:
        text = telebot.util.extract_arguments(message.text)
        id = message.from_user.id
        if (
            len(text) > 0
            and len(text) < 251
            and len(text) < int(self.db[str(id)]["limit"])
        ):
            status, result = SpeechKit.text_to_speech(text, str(id))
            if status:
                with open(f"./data/temp/{str(id)}.ogg", "wb") as f:
                    f.write(result)
                self.db[str(id)]["limit"] = int(self.db[str(id)]["limit"]) - len(text)
                self.write_json(self.db)
                return True
            else:
                return False, result
        else:
            return False, "Текст должен быть от 1 до 250 символов"

    def get_iam_token(self) -> str:
        try:
            with open(IAM_TOKEN_PATH, "r") as token_file:
                token_data = json.load(token_file)

            expires_at = token_data.get("expires_at")

            if expires_at <= time.time():
                self.create_new_iam_token()

        except FileNotFoundError:
            self.create_new_iam_token()

        with open(IAM_TOKEN_PATH, "r") as token_file:
            token_data = json.load(token_file)

        return token_data.get("access_token")

    def get_inline_keyboard(
        self, values: tuple[tuple[str, str]]
    ) -> telebot.types.InlineKeyboardMarkup:
        markup = telebot.types.InlineKeyboardMarkup()
        for value in values:
            markup.add(
                telebot.types.InlineKeyboardButton(
                    text=value[0], callback_data=value[1]
                )
            )
        return markup

    def get_reply_markup(
        self, values: tuple[str]
    ) -> telebot.types.ReplyKeyboardMarkup | None:
        if values:
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            for value in values:
                markup.add(value)
            return markup
        else:
            return None

    def tuple_voices(self) -> tuple[str]:
        return tuple(self.read_json(VJSON_PATH).keys())

    def tuple_emotions(self, id: int) -> tuple[str]:
        return tuple(self.read_json(VJSON_PATH)[self.db[str(id)]["voice"]])


class SpeechKit:

    def text_to_speech(text: str, id: str):
        iam_token = IOP.get_iam_token()
        folder_id = FOLDER_ID
        voice = str(IOP.db[id]["voice"])
        emotion = str(IOP.db[id]["emotion"])
        speed = str(IOP.db[id]["speed"])

        headers = {
            "Authorization": f"Bearer {iam_token}",
        }
        data = {
            "text": text,  # текст, который нужно преобразовать в голосовое сообщение
            "lang": "ru-RU",  # язык текста - русский
            "voice": voice,
            "emotion": emotion,
            "speed": speed,
            "folderId": folder_id,
        }
        response = requests.post(
            "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize",
            headers=headers,
            data=data,
        )

        if response.status_code == 200:
            return True, response.content
        else:
            logging.error(response.content)
            return (
                False,
                f"При запросе в SpeechKit возникла ошибка c кодом: {response.status_code}",
            )
