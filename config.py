import os
from dotenv import load_dotenv


load_dotenv()

LOGS_PATH = "./data/logs.log"
JSON_PATH = "./data/users.json"
VJSON_PATH = "./data/voices.json"

FOLDER_ID = os.getenv("FOLDER_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

MAX_ON_USER_TOKENS = 500
ADMIN_LIST = [6303315695]
MAX_USERS = 2

IAM_TOKEN_ENDPOINT = (
    "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
)
IAM_TOKEN_PATH = "data/token_data.json"
TOKENS_DATA_PATH = "data/DONT_DELETE_ME.json"
