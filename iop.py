import logging, json, requests, os, telebot, time, sqlite3
from config import (
    LOGS_PATH,
    JSON_PATH,
    FOLDER_ID,
    IAM_TOKEN_PATH,
    VJSON_PATH,
    IAM_TOKEN_ENDPOINT,
    DB_PATH,
    TABLE_NAME,
    TTS_LIMIT,
    STT_LIMIT,
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
        Database()

    def sing_up(self, id: int):
        """
        Adds a new user to the database.

        Args:
            id (int): The ID of the user.
        """
        ids = [user[1] for user in Database.get_all_users()]
        if id not in ids:
            Database.add_user(id)

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
            len(text) > 2
            and len(text) < 251
            and len(text) < int(self.db(id)["tts_limit"])
        ):
            status, result = SpeechKit.text_to_speech(text, str(id))
            if status:
                with open(f"./data/temp/{str(id)}.ogg", "wb") as f:
                    f.write(result)
                Database.update_value(id, "tts_limit", int(self.db(id)["tts_limit"]) - len(text)) 
                logging.info("Успешная генерация (IOP.tts)")
                return True
            else:
                logging.warning(f"Проблема с запросом (IOP.tts): {result}")
                return tuple(False, result)
        else:
            logging.warning("Ошибка со стороны пользователя (IOP.tts)")
            return (
                False,
                f"Проблема с запросом. {'У вас закончился лимит' if len(text) > int(self.db(id)['tts_limit']) else 'Cлишком длинный текст' if len(text) > 250 else 'Слишком короткий текст'}",
            )

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
                logging.info(
                    "Время жизни IAM-токена истек. Запуск получения нового токена. (IOP.get_iam_token)"
                )
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
            logging.error("Не удалось выполнить запрос (IOP.create_new_iam_token):", e)
            logging.info("Токен не получен (IOP.create_new_iam_token)")

        else:
            if response.status_code == 200:
                token_data = {
                    "access_token": response.json().get("access_token"),
                    "expires_at": response.json().get("expires_in") + time.time(),
                }

                with open(IAM_TOKEN_PATH, "w") as token_file:
                    json.dump(token_data, token_file)

            else:
                logging.error(
                    "Ошибка при получении ответа (IOP.create_new_iam_token):",
                    response.status_code,
                )
                logging.info("Токен не получен (IOP.create_new_iam_token)")

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

    def list_voices(self) -> list[str]:
        """
        Lists available voices.

        Returns:
            list[str]: The list of available voices.
        """
        return list(self.read_json(VJSON_PATH).keys())

    def list_emotions(self, id: int) -> list[str]:
        """
        Lists available emotions for a user.

        Args:
            id (int): The ID of the user.

        Returns:
            list[str]: The list of available emotions.
        """
        voice = self.db(id)["voice"]
        return self.read_json(VJSON_PATH)[voice]
    
    def db(id: int):
        return Database.get_user_data(id)


class SpeechKit(IOP):

    def text_to_speech(self, text: str, id: str):
        iam_token = self.get_iam_token()
        folder_id = FOLDER_ID
        voice = str(self.db(id)["voice"])
        emotion = str(self.db(id)["emotion"]) if not None else ""
        speed = str(self.db(id)["speed"])

        headers = {
            "Authorization": f"Bearer {iam_token}",
        }
        data = {
            "text": text,
            "lang": "ru-RU",
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
            logging.error(
                f"Ошибка в запросе (SpeechKit.text_to_speech): {response.content}"
            )
            return (
                False,
                f"При запросе в SpeechKit возникла ошибка c кодом: {response.status_code}",
            )

    def speech_to_text(self, file: bin, id: str):
        iam_token = self.get_iam_token()
        folder_id = FOLDER_ID

        params = "&".join([
            "topic=general",
            f"folderId={folder_id}",
            "lang=ru-RU"
        ])

        headers = {
            'Authorization': f'Bearer {iam_token}',
        }
            
        response = requests.post(
                f"https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?{params}",
            headers=headers, 
            data=file
        )
        
        decoded_data = response.json()
        if decoded_data.get("error_code") is None:
            return (True, decoded_data.get("result"))
        else:
            logging.error(f"Ошибка в запросе (SpeechKit.speech_to_text): {decoded_data.get("error_code")}")
            return (False, f"При запросе в SpeechKit возникла ошибка с кодом: {decoded_data.get("error_code")}")

class GPT(IOP):
    ...

class Monetize(IOP):
    ...

class Database:
    def __init__(self):
        self.create_table()

    def executer(self, command: str, data: tuple = None):
        try:
            self.connection = sqlite3.connect(DB_PATH)
            self.cursor = self.connection.cursor()

            if data:
                self.cursor.execute(command, data)
                self.connection.commit()

            else:
                self.cursor.execute(command)

        except sqlite3.Error as e:
            logging.error("Ошибка при выполнении запроса (executer): ", e)

        else:
            result = self.cursor.fetchall()
            self.connection.close()
            return result


    def create_table(self):
        self.executer(
            f"""CREATE TABLE IF NOT EXISTS {TABLE_NAME}
            (id INTEGER PRIMARY KEY,
            user_id INTEGER,
            tts_limit INTEGER,
            stt_limit INTEGER,
            gpt_limit INTEGER,
            gpt_chat TEXT,
            ban INTEGER,
            voice TEXT,
            emotion TEXT,
            speed TEXT,
            debt INTEGER)
            """
            
        )
        logging.info(f"Таблица {TABLE_NAME} создана")


    def add_user(self, user_id: int, ban: int):
        try:
            self.executer(
                f"INSERT INTO {TABLE_NAME} "
                f"(user_id, tts_limit, stt_limit, ban, voice, emotion, speed) "
                f"VALUES (?, ?, ?, ?, zahar, Null, 1);", (user_id, TTS_LIMIT, STT_LIMIT, ban)
            )
            logging.info(f"Добавлен пользователь {user_id}")
        except Exception as e:
            logging.error(f"Возникла ошибка при добавлении пользователя {user_id} (DataBase.add_user): {e}")


    def check_user(self, user_id: int) -> bool:
        try:
            result = self.executer(f"SELECT user_id FROM {TABLE_NAME} WHERE user_id=?", (user_id,))
            return bool(result)
        except Exception as e:
            logging.error(f"Возникла ошибка при проверке пользователя {user_id}: {e}")
        


    def update_value(self, user_id: int, column: str, value):
        try:
            self.executer(f"UPDATE {TABLE_NAME} SET {column}=? WHERE user_id=?", (value, user_id))
            logging.info(f"Обновлено значение {column} для пользователя {user_id}")
        except Exception as e:
            logging.error(f"Возникла ошибка при обновлении значения {column} для пользователя {user_id}: {e}")


    def get_user_data(self, user_id: int):
        try:
            result = self.executer(f"SELECT * FROM {TABLE_NAME} WHERE user_id=?", (user_id,))
            presult = {
                "tts_limit": result[0][2],
                "stt_limit": result[0][3],
                "gpt_limit": result[0][4],
                "gpt_chat": result[0][5],
                "ban": result[0][6],
                "voice": result[0][7],
                "emotion": result[0][8],
                "speed": result[0][9],
                "debt": result[0][10]
            }
            return presult
        except Exception as e:
            logging.error(f"Возникла ошибка при получении данных пользователя {user_id}: {e}")
    
    def get_all_users(self) -> list[tuple[int, int, int, int, int, str, int, str, str, str]]:
        try:
            result = self.executer(f"SELECT * FROM {TABLE_NAME}")
            return result
        except Exception as e:
            logging.error(f"Возникла ошибка при получении данных всех пользователей: {e}")

    def delete_user(self, user_id: int):
        try:
            self.executer(f"DELETE FROM {TABLE_NAME} WHERE user_id=?", (user_id,))
            logging.warning(f"Удален пользователь {user_id}")
        except Exception as e:
            logging.error(f"Возникла ошибка при удалении пользователя {user_id}: {e}")