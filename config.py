import os
from dotenv import load_dotenv


load_dotenv()

LOGS_PATH = "./data/logs.log"
JSON_PATH = "./data/users.json"
VJSON_PATH = "./data/voices.json"
DB_PATH = "./data/database.db"
TABLE_NAME = "texts"

FOLDER_ID = os.getenv("FOLDER_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

TTS_LIMIT = 500
STT_LIMIT = 500
GPT_LIMIT = 1000
ADMIN_LIST = [6303315695]
MAX_USERS = 2

IAM_TOKEN_ENDPOINT = (
    "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
)
GPT_MODEL = "yandexgpt-lite"
TEMPERATURE = 0.5
IAM_TOKEN_PATH = "data/token_data.json"
TOKENS_DATA_PATH = "data/DONT_DELETE_ME.json"
