import os
from dotenv import load_dotenv

load_dotenv()

# NOTE: It's best to leave sensitive credentials like API_HASH 
# and BOT_TOKEN blank in the code and enforce them via .env or OS environment.

API_ID = int(os.getenv('API_ID', '')) 
API_HASH = os.getenv('API_HASH', '')  
BOT_TOKEN = os.getenv('BOT_TOKEN', '') 

# Variables that can have reasonable defaults
BOT_NAME = os.getenv('BOT_NAME', 'moxi - YT downloader')
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '300'))

# Variables that often require external configuration and should remain flexible
MONGO_URI = os.getenv('MONGO_URI', '')
FORCE_JOIN_CHANNEL = os.getenv('FORCE_JOIN_CHANNEL', '')

# Variables that are usually required integers
# If OWNER_ID isn't set, it will be None
owner_id_str = os.getenv('OWNER_ID', '')
OWNER_ID = int(owner_id_str) if owner_id_str else None
