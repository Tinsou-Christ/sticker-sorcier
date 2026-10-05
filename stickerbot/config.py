import os


def _int_list(value: str):
    out = []
    for part in (value or '').replace(';', ',').split(','):
        part = part.strip()
        if part.lstrip('-').isdigit():
            out.append(int(part))
    return out


BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
ADMINS = _int_list(os.environ.get('ADMINS', ''))

CREATOR_URL = os.environ.get('CREATOR_URL', 'https://t.me/telegram').strip()
CHANNEL_URL = os.environ.get('CHANNEL_URL', 'https://t.me/telegram').strip()
GROUP_URL = os.environ.get('GROUP_URL', 'https://t.me/telegram').strip()

DEFAULT_DB_PATH = '/var/data/bot.db' if os.environ.get('RENDER') else os.path.join(os.path.dirname(__file__), 'bot.db')
DB_PATH = os.environ.get('DB_PATH', DEFAULT_DB_PATH)
PORT = int(os.environ.get('PORT', '8080'))

# limites
MAX_STICKERS_PER_PACK = 120
WA_STICKERS_PER_FILE = 30

# performance / multi-utilisateurs
CONCURRENT_UPDATES = int(os.environ.get('CONCURRENT_UPDATES', '256'))
CONNECTION_POOL_SIZE = int(os.environ.get('CONNECTION_POOL_SIZE', '64'))
MAX_PARALLEL_CONVERSIONS = int(os.environ.get('MAX_PARALLEL_CONVERSIONS', '3'))

