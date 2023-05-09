import os

PRO_DIR= os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR= os.path.join(PRO_DIR, 'data')

TMP_DIR= os.path.join(PRO_DIR, 'tmp')

API_KEY_FILEPATH = os.path.join(PRO_DIR, "openai_api.key")

CONFIG_DIR = os.path.join(PRO_DIR, "configurations")