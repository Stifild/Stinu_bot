import logging, json, requests, os, telebot, time, sqlite3, math, time
from config import (
    GPT_LIMIT,
    TEMPERATURE,
    GPT_MODEL,
    TOKENS_DATA_PATH,
    LOGS_PATH,
    FOLDER_ID,
    IAM_TOKEN_PATH,
    VJSON_PATH,
    IAM_TOKEN_ENDPOINT,
    DB_PATH,
    TABLE_NAME,
    TTS_LIMIT,
    STT_LIMIT,
    MAX_USERS,
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
    The IOP class represents the Input-Output Processor.

    It provides methods for user registration, IAM token retrieval, creating inline and reply keyboard markups,
    listing available voices and emotions, and accessing user data from the database.
    """

    def __init__(self):
        self.dbc = Database()
    
    def sing_up(self, id: int):
        """
        Adds a new user to the database.

        Args:
            id (int): The ID of the user.
        """
        ids = [user[1] for user in self.dbc.get_all_users()]
        if id not in ids and MAX_USERS < len(ids):
            self.dbc.add_user(id, 0)
            return
        elif id not in ids and MAX_USERS >= len(ids):
            self.dbc.add_user(id, 1)
            return
        else:
            return

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

    def split_voice_file(self, file_path: str, id: int) -> list[str]:
        """
        Splits a voice file into multiple files of 30 seconds each.

        Args:
            file_path (str): The path to the voice file.

        Returns:
            list[str]: The list of paths to the split voice files.
        """
        split_files = []
        with open(file_path, "rb") as f:
            voice_data = f.read()
            voice_size = len(voice_data)
            num_splits = math.ceil(
                voice_size / (30 * 16000 * 2)
            )  # Assuming 16kHz sample rate and 2 bytes per sample
            for i in range(num_splits):
                start = i * 30 * 16000 * 2
                end = min((i + 1) * 30 * 16000 * 2, voice_size)
                split_voice_data = voice_data[start:end]
                split_file_path = f"./data/temp/{str(id)}_{i}.ogg"
                with open(split_file_path, "wb") as split_file:
                    split_file.write(split_voice_data)
                split_files.append(split_file_path)
        return split_files

    def db(self, id: int):
        """
        Retrieves user data from the database.

        Args:
            id (int): The ID of the user.

        Returns:
            dict: The user data.
        """
        return self.dbc.get_user_data(id)


class SpeechKit(IOP):

    def text_to_speech(self, text: str, id: str):
        """
        Converts the given text to speech using the Yandex SpeechKit API.

        Args:
            text (str): The text to be converted to speech.
            id (str): The ID used to retrieve voice, emotion, and speed settings from the database.

        Returns:
            tuple: A tuple containing a boolean value indicating the success of the request and the response content.
                - If the request is successful, the first element of the tuple is True and the second element is the response content.
                - If the request fails, the first element of the tuple is False and the second element is an error message.
        """
        iam_token = self.get_iam_token()
        folder_id = FOLDER_ID
        voice = str(self.db(id)["voice"])
        emotion = str(self.db(id)["emotion"])
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

    def speech_to_text(self, file: bytes, id: str) -> tuple[bool, str]:
        """
        Converts speech to text using the Yandex SpeechKit API.

        Args:
            file (bin): The audio file to be converted.
            id (str): The ID associated with the audio file.

        Returns:
            tuple: A tuple containing a boolean value indicating the success of the conversion
            and the result of the conversion.

            If the conversion is successful, the first element of the tuple is True and the second
            element is the converted text.

            If an error occurs during the conversion, the first element of the tuple is False and
            the second element is an error message.
        """
        iam_token = self.get_iam_token()
        folder_id = FOLDER_ID

        params = "&".join(["topic=general", f"folderId={folder_id}", "lang=ru-RU"])

        headers = {
            "Authorization": f"Bearer {iam_token}",
        }

        response = requests.post(
            f"https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?{params}",
            headers=headers,
            data=file,
        )

        decoded_data = response.json()
        if decoded_data.get("error_code") is None:
            return (True, decoded_data.get("result"))
        else:
            logging.error(
                f'Ошибка в запросе (SpeechKit.speech_to_text): {decoded_data.get("error_code")}'
            )
            return (
                False,
                f'При запросе в SpeechKit возникла ошибка с кодом: {decoded_data.get("error_code")}',
            )

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
            status, result = self.text_to_speech(text, str(id))
            if status:
                with open(f"./data/temp/{str(id)}.ogg", "wb") as f:
                    f.write(result)
                self.dbc.update_value(
                    id, "tts_limit", int(self.db(id)["tts_limit"]) - len(text)
                )
                logging.info("Успешная генерация (SpeechKit.tts)")
                return True
            else:
                logging.warning(f"Проблема с запросом (SpeechKit.tts): {result}")
                return (False, result)
        else:
            logging.warning("Ошибка со стороны пользователя (SpeechKit.tts)")
            return (
                False,
                f"Проблема с запросом. {'У вас закончился лимит' if len(text) > int(self.db(id)['tts_limit']) else 'Cлишком длинный текст' if len(text) > 250 else 'Слишком короткий текст'}",
            )

    def stt(
        self, message: telebot.types.Message, bot: telebot.TeleBot
    ) -> tuple[bool, str]:
        db = self.db(message.from_user.id)
        duration = message.voice.duration
        id = message.from_user.id
        text = ""
        stt_blocks_num = math.ceil(duration / 15)
        if db["stt_limit"] - stt_blocks_num >= 0:
            file_id = message.voice.file_id
            file_info = bot.get_file(file_id)
            file = bot.download_file(file_info.file_path)
            if duration > 30:
                """
                with open(f"./data/temp/{str(id)}_full.ogg", "wb") as f:
                    f.write(file)
                files = self.split_voice_file(f"./data/temp/{str(id)}_full.ogg", id)
                for filer in files:
                    with open(filer, "rb") as f:
                        result = self.speech_to_text(f, id)
                    if result[0] == True:
                        text += result[1]
                    else:
                        os.remove(f"./data/temp/{str(id)}_full.ogg")
                        return (False, result[1])
                    os.remove(filer)
                os.remove(f"./data/temp/{str(id)}_full.ogg")
                """
                return (
                    False,
                    "Фича в разработке а пока голосовые только до 30 секунд)",
                )
            else:
                result = self.speech_to_text(file, id)
                if result[0] == True:
                    self.dbc.update_value(
                        id, "stt_limit", db["stt_limit"] - stt_blocks_num
                    )
                    logging.info("Успех (SpeechKit.stt)")
                    return (True, result[1])
                else:
                    return (False, result[1])
        else:
            logging.warning("Ошибка со стороны пользователя (SpeechKit.stt)")
            return (
                False,
                "Проблема с запросом. У вас закончился лимит",
            )


class GPT(IOP):

    def __init__(self):
        self.dbc = Database()
        self.max_tokens = GPT_LIMIT
        self.temperature = TEMPERATURE
        self.folder_id = FOLDER_ID
        self.gpt_model = GPT_MODEL
        self.tokens_data_path = TOKENS_DATA_PATH

    def count_tokens_in_dialogue(self, messages: list) -> int:
        iam_token = self.get_iam_token()

        headers = {
            "Authorization": f"Bearer {iam_token}",
            "Content-Type": "application/json",
        }
        data = {
            "modelUri": f"gpt://{self.folder_id}/{self.gpt_model}/latest",
            "maxTokens": self.max_tokens,
            "messages": [],
        }

        for row in messages:
            data["messages"].append({"role": row["role"], "text": row["content"]})

        return len(
            requests.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenizeCompletion",
                json=data,
                headers=headers,
            ).json()["tokens"]
        )

    def increment_tokens_by_request(self, messages: list[dict]):
        try:
            with open(self.tokens_data_path, "r") as token_file:
                tokens_count = json.load(token_file)["tokens_count"]

        except FileNotFoundError:
            tokens_count = 0

        current_tokens_used = self.count_tokens_in_dialogue(messages)
        tokens_count += current_tokens_used

        with open(self.tokens_data_path, "w") as token_file:
            json.dump({"tokens_count": tokens_count}, token_file)

    def ask_gpt(self, messages):
        iam_token = self.get_iam_token()

        url = f"https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {iam_token}",
            "Content-Type": "application/json",
        }

        data = {
            "modelUri": f"gpt://{self.folder_id}/{self.gpt_model}/latest",
            "completionOptions": {
                "stream": False,
                "temperature": self.temperature,
                "maxTokens": self.max_tokens,
            },
            "messages": [],
        }

        for row in messages:
            data["messages"].append({"role": row["role"], "text": row["content"]})

        try:
            response = requests.post(url, headers=headers, json=data)

        except Exception as e:
            logging.ERROR("Произошла непредвиденная ошибка.", e)

        else:
            if response.status_code != 200:
                logging.ERROR("Ошибка при получении ответа:", response.status_code)
            else:
                result = response.json()["result"]["alternatives"][0]["message"]["text"]
                messages.append({"role": "assistant", "content": result})
                self.increment_tokens_by_request(messages)
                return result

        with open(TOKENS_DATA_PATH, "r") as f:
            logging.INFO(
                "За всё время израсходовано:", json.load(f)["tokens_count"], "токенов"
            )
    
    def asking_gpt(self, user_id: int, task: str | None = None) -> str:
        try:
            message = json.loads(self.db(user_id)["gpt_chat"])
        except TypeError:
            message = []
        if task:
            message.append({"role": "user", "content": task})
        answer = self.ask_gpt(message)
        message.append({"role": "assistant", "content": answer})
        current_tokens_used = self.count_tokens_in_dialogue(message)
        self.dbc.update_value(user_id, "gpt_limit", self.db(user_id)["gpt_limit"]-current_tokens_used)
        self.dbc.update_value(user_id, "gpt_chat", json.dumps(message, ensure_ascii=False))
        return answer
    
    def count_tokens(self, text: str) -> int:
        iam_token = self.get_iam_token()

        headers = {
            "Authorization": f"Bearer {iam_token}",
            "Content-Type": "application/json",
        }
        data = {
            "modelUri": f"gpt://{self.folder_id}/{self.gpt_model}/latest",
            "messages": text,
        }

        return len(
            requests.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenize",
                json=data,
                headers=headers,
            ).json()["tokens"]
        )

    @classmethod
    def create_new_iam_token(cls):
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

class Monetize(IOP):
    def gpt_rate(self, tokens: int) -> float:
        return tokens * (0.20 / 1000)

    def speechkit_recog_rate(self, blocks: int) -> float:
        return blocks * 0.16

    def speechkit_synt_rate(self, symbols: int) -> float:
        return float(symbols * (1320 / 1000000))

    def cost_calculation(self, id: int, type: str) -> int:
        user = self.db(id)
        if type == "gpt":
            return self.gpt_rate(GPT_LIMIT - user["gpt_limit"])
        elif type == "stt":
            return self.speechkit_recog_rate(STT_LIMIT - user["stt_limit"])
        elif type == "tts":
            return self.speechkit_synt_rate(TTS_LIMIT - user["tts_limit"])
        else:
            Exception("Неверный тип технологии для вычесления стоймости")
    
    def update_debts(self):
        ids = [user[1] for user in self.dbc.get_all_users()]
        for id in ids:
            self.dbc.update_value(id, "debt", self.cost_calculation(id, "gpt") + self.cost_calculation(id, "stt") + self.cost_calculation(id, "tts"))
            logging.info(f"Обновление долга у пользователя {id}")


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
        """
        Adds a new user to the database.

        Args:
            user_id (int): The ID of the user.
            ban (int): The ban status of the user.
        """
        try:
            self.executer(
                f"INSERT INTO {TABLE_NAME} "
                f"(user_id, tts_limit, stt_limit, gpt_limit, ban, voice, emotion, speed) "
                f"VALUES (?, ?, ?, ?, ?, 'zahar', 'neutral', 1);",
                (user_id, TTS_LIMIT, STT_LIMIT, GPT_LIMIT, ban),
            )
            logging.info(f"Добавлен пользователь {user_id}")
        except Exception as e:
            logging.error(
                f"Возникла ошибка при добавлении пользователя {user_id} (DataBase.add_user): {e}"
            )

    def check_user(self, user_id: int) -> bool:
        """
        Checks if a user exists in the database.

        Args:
            user_id (int): The ID of the user.

        Returns:
            bool: True if the user exists, False otherwise.
        """
        try:
            result = self.executer(
                f"SELECT user_id FROM {TABLE_NAME} WHERE user_id=?", (user_id,)
            )
            return bool(result)
        except Exception as e:
            logging.error(f"Возникла ошибка при проверке пользователя {user_id}: {e}")

    def update_value(self, user_id: int, column: str, value):
        """
        Updates a value for a specific user in the database.

        Args:
            user_id (int): The ID of the user.
            column (str): The name of the column to update.
            value: The new value for the column.
        """
        try:
            self.executer(
                f"UPDATE {TABLE_NAME} SET {column}=? WHERE user_id=?", (value, user_id)
            )
            logging.info(f"Обновлено значение {column} для пользователя {user_id}")
        except Exception as e:
            logging.error(
                f"Возникла ошибка при обновлении значения {column} для пользователя {user_id}: {e}"
            )

    def get_user_data(self, user_id: int):
        """
        Retrieves the data for a specific user from the database.

        Args:
            user_id (int): The ID of the user.

        Returns:
            dict: A dictionary containing the user data.
        """
        try:
            result = self.executer(
                f"SELECT * FROM {TABLE_NAME} WHERE user_id=?", (user_id,)
            )
            presult = {
                "tts_limit": result[0][2],
                "stt_limit": result[0][3],
                "gpt_limit": result[0][4],
                "gpt_chat": result[0][5],
                "ban": result[0][6],
                "voice": result[0][7],
                "emotion": result[0][8],
                "speed": result[0][9],
                "debt": result[0][10],
            }
            return presult
        except Exception as e:
            logging.error(
                f"Возникла ошибка при получении данных пользователя {user_id}: {e}"
            )

    def get_all_users(
        self,
    ) -> list[tuple[int, int, int, int, int, str, int, str, str, str]]:
        """
        Retrieves the data for all users from the database.

        Returns:
            list[tuple[int, int, int, int, int, str, int, str, str, str]]: A list of tuples containing the user data.
        """
        try:
            result = self.executer(f"SELECT * FROM {TABLE_NAME}")
            return result
        except Exception as e:
            logging.error(
                f"Возникла ошибка при получении данных всех пользователей: {e}"
            )

    def delete_user(self, user_id: int):
        """
        Deletes a user from the database.

        Args:
            user_id (int): The ID of the user.
        """
        try:
            self.executer(f"DELETE FROM {TABLE_NAME} WHERE user_id=?", (user_id,))
            logging.warning(f"Удален пользователь {user_id}")
        except Exception as e:
            logging.error(f"Возникла ошибка при удалении пользователя {user_id}: {e}")
