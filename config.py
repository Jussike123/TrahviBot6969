import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID', 0))
UNBELIEVA_API_TOKEN = os.getenv('UNBELIEVA_API_TOKEN')

# Citation fine multiplier (can be adjusted)
FINE_MULTIPLIER = 1.0
CITATION_ROLE_ID = int(os.getenv('CITATION_ROLE_ID', '1518010616290345000'))
