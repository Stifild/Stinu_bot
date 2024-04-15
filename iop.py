import logging, json, requests, os, telebot, time
from config import (
    LOGS_PATH,
    JSON_PATH,
    FOLDER_ID,
    IAM_TOKEN_PATH,
    VJSON_PATH,
    IAM_TOKEN_ENDPOINT,
)


os.mkdir("./data/temp") if not os.path.exists("./data/temp") else None

logging.basicConfig(
    filename=LOGS_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
)


class IOP:
    """
    The IOP class represents an Input-Output Processor.

    It provides methods for reading and writing JSON files, managing user data,
    performing text-to-speech conversion, retrieving IAM tokens, creating inline
    keyboards and reply markups, and listing available voices and emotions.

    Attributes:
        db (dict): The user database stored as a dictionary.

    Methods:
        __init__(): Initializes the IOP object and reads the user database from a JSON file.
        write_json(data: dict, path: str = JSON_PATH): Writes data to a JSON file.
        read_json(path: str = JSON_PATH): Reads data from a JSON file.
        sing_up(id: int): Adds a new user to the database.
        tts(message: telebot.types.Message) -> bool | tuple[bool, str]: Converts text to speech.
        get_iam_token() -> str: Retrieves the IAM token for authentication.
        create_new_iam_token(): Creates a new IAM token.
        get_inline_keyboard(values: tuple[tuple[str, str]]) -> telebot.types.InlineKeyboardMarkup:
            Creates an inline keyboard markup.
        get_reply_markup(values: list[str]) -> telebot.types.ReplyKeyboardMarkup | None:
            Creates a reply markup.
        list_voices() -> tuple[str]: Lists available voices.
        list_emotions(id: int) -> tuple[str]: Lists available emotions for a user.
    """

    def __init__(self):
        self.db = self.read_json()

    def write_json(self, data: dict, path: str = JSON_PATH):
        """
        Writes data to a JSON file.

        Args:
            data (dict): The data to be written.
            path (str, optional): The path of the JSON file. Defaults to JSON_PATH.
        """
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    def read_json(self, path: str = JSON_PATH):
        """
        Reads data from a JSON file.

        Args:
            path (str, optional): The path of the JSON file. Defaults to JSON_PATH.

        Returns:
            dict: The data read from the JSON file.
        """
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.decoder.JSONDecodeError, FileNotFoundError):
            return {}

    def sing_up(self, id: int):
        """
        Adds a new user to the database.

        Args:
            id (int): The ID of the user.
        """
        self.db[str(id)] = {
            "limit": 500,
            "ban": False,
            "voice": "zahar",
            "emotion": "neutral",
            "speed": 1,
        }
        self.write_json(self.db)

    def tts(self, message: telebot.types.Message) -> bool | tuple[bool, str]:
        """
        Converts text to speech.

        Args:
            message (telebot.types.Message): The message containing the text to be converted.

        Returns:
            bool or tuple[bool, str]: True if the conversion is successful, otherwise a tuple
            containing False and an error message.
        """
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
                logging.debug("Успешная генерация")
                return True
            else:
                logging.debug("Проблема с запросом")
                return tuple(False, result)
        else:
            logging.debug("Ошибка со стороны пользователя")
            return (False, f"Проблема с запросом. {'У вас закончился лимит' if len(text) < int(self.db[str(id)]['limit']) else 'Cлишком длинный текст'}")

    def get_iam_token(self) -> str:
        """
        Retrieves the IAM token for authentication.

        Returns:
            str: The IAM token.
        """
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

    @classmethod
    def create_new_iam_token(cls):
        """
        Creates a new IAM token.
        """
        headers = {"Metadata-Flavor": "Google"}

        try:
            response = requests.get(IAM_TOKEN_ENDPOINT, headers=headers)

        except Exception as e:
            logging.error("Не удалось выполнить запрос:", e)
            logging.info("Токен не получен")

        else:
            if response.status_code == 200:
                token_data = {
                    "access_token": response.json().get("access_token"),
                    "expires_at": response.json().get("expires_in") + time.time(),
                }

                with open(IAM_TOKEN_PATH, "w") as token_file:
                    json.dump(token_data, token_file)

            else:
                logging.error("Ошибка при получении ответа:", response.status_code)
                logging.info("Токен не получен")

    def get_inline_keyboard(
        self, values: tuple[tuple[str, str]]
    ) -> telebot.types.InlineKeyboardMarkup:
        """
        Creates an inline keyboard markup.

        Args:
            values (tuple[tuple[str, str]]): The values for the inline keyboard buttons.

        Returns:
            telebot.types.InlineKeyboardMarkup: The created inline keyboard markup.
        """
        markup = telebot.types.InlineKeyboardMarkup()
        for value in values:
            markup.add(
                telebot.types.InlineKeyboardButton(
                    text=value[0], callback_data=value[1]
                )
            )
        return markup

    def get_reply_markup(
        self, values: list[str]
    ) -> telebot.types.ReplyKeyboardMarkup | None:
        """
        Creates a reply markup.

        Args:
            values (list[str]): The values for the reply keyboard buttons.

        Returns:
            telebot.types.ReplyKeyboardMarkup or None: The created reply markup, or None if
            the values list is empty.
        """
        if values:
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            for value in values:
                markup.add(value)
            return markup
        else:
            return None

    def list_voices(self) -> tuple[str]:
        """
        Lists available voices.

        Returns:
            tuple[str]: The list of available voices.
        """
        return list(self.read_json(VJSON_PATH).keys())

    def list_emotions(self, id: int) -> tuple[str]:
        """
        Lists available emotions for a user.

        Args:
            id (int): The ID of the user.

        Returns:
            tuple[str]: The list of available emotions.
        """
        voice = self.db[str(id)]["voice"]
        return self.read_json(VJSON_PATH)[voice]


class SpeechKit:

    def text_to_speech(text: str, id: str):
        io = IOP()
        iam_token = io.get_iam_token()
        folder_id = FOLDER_ID
        voice = str(io.db[id]["voice"])
        emotion = str(io.db[id]["emotion"]) if not None else ""
        speed = str(io.db[id]["speed"])

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
