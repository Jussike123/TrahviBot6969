import aiohttp
import asyncio
import json
import os
import random
from pathlib import Path

import discord
from discord import app_commands
from discord.ui import View, Modal, TextInput, Select, Button

from erlc_client import ERLCClient

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / 'config.json'

if not CONFIG_PATH.exists():
    raise SystemExit('Missing config.json. Copy config.example.json to config.json and fill in credentials.')

with CONFIG_PATH.open('r', encoding='utf-8') as config_file:
    config = json.load(config_file)

TOKEN = config.get('token')
CLIENT_ID = config.get('clientId')
GUILD_ID = config.get('guildId')
ERLC_API_BASE_URL = config.get('erlcApiBaseUrl')
ERLC_API_KEY = config.get('erlcApiKey')
NOTIFY_DISCORD_ID = config.get('notifyDiscordId')
NOTIFY_CHANNEL_ID = config.get('notifyChannelId') or '1040589270991241239'
BOAT_API_BASE_URL = config.get('boatApiBaseUrl')
BOAT_API_TOKEN = config.get('boatApiToken')
BOAT_API_ENABLED = bool(BOAT_API_BASE_URL and BOAT_API_TOKEN)

if not all([TOKEN, CLIENT_ID, ERLC_API_BASE_URL, ERLC_API_KEY, NOTIFY_DISCORD_ID]):
    raise SystemExit('config.json must include token, clientId, erlcApiBaseUrl, erlcApiKey, and notifyDiscordId.')

# CCTV System constants
BLOKKER_ROLE_ID = 1519010309736763575
POLICE_ROLE_ID = 1518010616290345000
CCTV_ALERT_CHANNEL_ID = 1519677771842846873
TASK_COMPLETION_CHANNEL_ID = 1519680257471418479
CCTV_ALERT_FAILURE_CHANCE = 0.30  # 30% chance signal blocker fails

CHALLENGES = {
    'Pomm': {
        'display_name': 'Pomm',
        'reward': 'Pomm',
        'missions': [
            {
                'id': 'Pomm-1',
                'name': 'Eddie ülevaatuspunkt',
                'zip': '501',
                'building': None,
                'required_stay_sec': 180,
                'description': 'Ole seal 3 minutit'
            },
            {
                'id': 'Pomm-2',
                'name': 'Hiina tänava draakoni pood',
                'zip': '220',
                'building': '2201',
                'required_stay_sec': 180,
                'description': 'Ole seal 3 minutit'
            }
        ]
    },
    'klaasilõikur': {
        'display_name': 'Klaasilõikur',
        'reward': 'Klaasilõikur',
        'missions': [
            {
                'id': 'klaasilõikur-1',
                'name': 'Pärnu autoparandus',
                'zip': '211',
                'building': '2111',
                'required_stay_sec': 180,
                'description': 'Ole seal 3 minutit',
                'has_cctv': True
            },
            {
                'id': 'klaasilõikur-2',
                'name': 'Haapsalu autoparandus',
                'zip': '1108',
                'building': '11082',
                'required_stay_sec': 180,
                'description': 'Ole seal 3 minutit',
                'has_cctv': True
            }
        ]
    },
    'lasercutter': {
        'display_name': 'Laser cutter',
        'reward': 'Laserlõikur',
        'missions': [
            {
                'id': 'lasercutter-1',
                'name': 'Pärnu autoparandus',
                'zip': '211',
                'building': '2111',
                'required_stay_sec': 10,
                'description': 'Ole seal 3 minutit',
                'has_cctv': True
            },
            {
                'id': 'lasercutter-2',
                'name': 'Haapsalu autoparandus',
                'zip': '1108',
                'building': '11082',
                'required_stay_sec': 180,
                'description': 'Ole seal 3 minutit',
                'has_cctv': True
            }
        ]
    }
}

HEIST_LOCATIONS = {
    'juveelipood_seif': {
        'label': 'Juveelipood (Seif)',
        'zip': '403',
        'picture_reference': 'Pic nr 1',
        'image_url': 'https://via.placeholder.com/800x400.png?text=Pic+1',
        'has_cctv': True,
        'xmin': 879.0,
        'xmax': 902.0,
        'zmin': 1882.0,
        'zmax': 1908.0,
    },
    'pank_zip205': {
        'label': 'Pank',
        'zip': '205',
        'picture_reference': 'Pic nr 2',
        'image_url': 'https://via.placeholder.com/800x400.png?text=Pic+2',
        'has_cctv': True,
        'requires_gate': True
    },
    'juveelipood_deemandid': {
        'label': 'Juveelipood (Deemandid)',
        'zip': '403',
        'picture_reference': 'Pic nr 1',
        'image_url': 'https://via.placeholder.com/800x400.png?text=Pic+1',
        'has_cctv': True,
        'xmin': 879.0,
        'xmax': 902.0,
        'zmin': 1882.0,
        'zmax': 1908.0,
    }
}

DEEMAND_SELL_LOCATION = {
    'label': 'Pärnu eramajade juures olev punker',
    'zip': '701',
    'hint': 'Mine punkrisse sisse',
    'street': 'Fairfax Road',
    'x': 584.614,
    'z': 1848.681,
    'tolerance': 10.0,
}

LAUNDROMAT_LOCATION = {
    'label': '301',
    'zip': '301',
    'name': '301',
    'has_cctv': True,
    'x': 1629.722,
    'z': 2465.834,
    'tolerance': 20.0,
}

DEEMAND_SELL_PRICES = {
    'Deemand Suur': 10000,
    'Deemand Väike': 1000,
}

HEIST_INFO_CHOICES = [
    app_commands.Choice(name='Juveel', value='juveelid'),
    app_commands.Choice(name='Pank', value='pank'),
]

HEIST_INFO_LOCATIONS = {
    'juveelid': {
        'label': 'Juveel',
        'stage_one_location': HEIST_LOCATIONS['juveelipood_seif'],
        'stage_one_message': 'Mine juveelipoodi ja ole seal 5 sekundit.',
    },
    'pank': {
        'label': 'Pank',
        'stage_one_location': HEIST_LOCATIONS['pank_zip205'],
        'stage_one_message': 'Mine panka ja ole seal 5 sekundit.',
    },
}

HEIST_INFO_ELECTRONICS_AREA = {
    'zip': '403',
    'description': 'Elektroonikapood',
    'center_x': 837.268,
    'center_z': 1909.451,
    'tolerance': 25.0,
}

BLACK_MONEY_ITEM_NAME = config.get('blackMoneyItemName') or 'Must raha'
DISCORD_MONEY_ITEM_NAME = config.get('discordMoneyItemName') or 'Discord raha'

active_sessions = set()
active_heist_sessions: dict[int, dict] = {}
active_heist_info_sessions: dict[int, dict] = {}
active_laundering_sessions: set[int] = set()

intents = discord.Intents.default()
client = discord.Client(intents=intents)
bot = app_commands.CommandTree(client)

erlc_client = ERLCClient(ERLC_API_BASE_URL, ERLC_API_KEY)


async def send_public_notification(
    interaction: discord.Interaction | None,
    message: str,
    *,
    channel: discord.abc.Messageable | None = None,
    embed: discord.Embed | None = None,
) -> bool:
    # Public channel notifications are disabled. Keep all bot replies private.
    if interaction is not None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(message, embed=embed, ephemeral=True)
            return True
        except Exception as e:
            print(f'Error sending private notification fallback: {e}')

    return False


def normalize_postal_code(location_data: dict) -> str | None:
    if not isinstance(location_data, dict):
        return None

    postal_code = (
        location_data.get('PostalCode') or
        location_data.get('postalCode') or
        location_data.get('zipCode') or
        location_data.get('zip_code') or
        location_data.get('zip')
    )
    if postal_code is None:
        return None

    return str(postal_code).strip()


def normalize_building_number(location_data: dict) -> str | None:
    if not isinstance(location_data, dict):
        return None

    building_number = (
        location_data.get('BuildingNumber') or
        location_data.get('buildingNumber') or
        location_data.get('building_number') or
        location_data.get('building')
    )
    if building_number is None:
        return None

    return str(building_number).strip()


def location_matches(player_data: dict, location: dict) -> bool:
    if not player_data:
        return False

    # Support both ERLC server responses (nested 'location') and mock/simple responses
    # that return location fields at the top level (e.g., mock_erlc_server uses 'zipCode').
    location_data = None
    if isinstance(player_data, dict):
        nested_location = player_data.get('location')
        location_data = nested_location if isinstance(nested_location, dict) else player_data
    else:
        location_data = player_data

    if not isinstance(location_data, dict):
        return False

    postal_code = normalize_postal_code(location_data)
    if postal_code is None or postal_code != str(location['zip']):
        return False

    if location.get('building'):
        building_number = normalize_building_number(location_data)
        if building_number is None or building_number != location['building']:
            return False

    if any(key in location for key in ('xmin', 'xmax', 'zmin', 'zmax', 'center_x', 'center_z', 'tolerance')):
        x, z = get_player_coordinates(location_data)
        if x is None or z is None:
            return False

        if 'xmin' in location and x < float(location['xmin']):
            return False
        if 'xmax' in location and x > float(location['xmax']):
            return False
        if 'zmin' in location and z < float(location['zmin']):
            return False
        if 'zmax' in location and z > float(location['zmax']):
            return False

        if 'center_x' in location and 'center_z' in location and 'tolerance' in location:
            if (
                abs(x - float(location['center_x'])) > float(location['tolerance']) or
                abs(z - float(location['center_z'])) > float(location['tolerance'])
            ):
                return False

    return True


def get_mission_by_id(challenge_key: str, mission_id: str) -> dict | None:
    challenge = CHALLENGES.get(challenge_key)
    if not challenge:
        return None
    return next((m for m in challenge['missions'] if m['id'] == mission_id), None)


def get_boat_headers() -> dict:
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {BOAT_API_TOKEN}'
    } if BOAT_API_ENABLED else {}


def get_boat_headers() -> dict:
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {BOAT_API_TOKEN}'
    } if BOAT_API_ENABLED else {}


async def get_boat_item_id(item_name: str) -> tuple[str | None, str | None]:
    if item_name.isdigit():
        return item_name, None

    guild_id = GUILD_ID
    if not guild_id:
        return None, 'No guild ID configured for BOAT item lookup.'

    url = f'{BOAT_API_BASE_URL.rstrip("/")}/guilds/{guild_id}/items'
    params = {'query': item_name, 'limit': 100, 'page': 1}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=get_boat_headers(), timeout=10) as response:
            text = await response.text()
            if response.status >= 400:
                try:
                    data = json.loads(text)
                    return None, data.get('error') or data.get('message') or f'HTTP {response.status}'
                except json.JSONDecodeError:
                    return None, text.strip() or f'HTTP {response.status}'

            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return None, 'Invalid JSON response from BOAT API item lookup.'

            items = payload.get('items') if isinstance(payload, dict) else None
            if not isinstance(items, list) or not items:
                return None, f'No BOAT store item found for "{item_name}".'

            exact_matches = [item for item in items if isinstance(item, dict) and item.get('name', '').lower() == item_name.lower()]
            if exact_matches:
                return exact_matches[0].get('id'), None

            substring_matches = [item for item in items if isinstance(item, dict) and item_name.lower() in item.get('name', '').lower()]
            if substring_matches:
                return substring_matches[0].get('id'), None

            first_item = items[0]
            if isinstance(first_item, dict) and first_item.get('id'):
                return first_item.get('id'), None

            return None, f'Unable to resolve BOAT item ID for "{item_name}".'


async def add_boat_inventory_item(discord_id: str, item_id: str, quantity: int = 1) -> dict:
    """Add an item to a user's BOAT inventory using the guild-scoped inventory endpoint.

    The function expects an item ID (not a name) because callers already resolve the
    BOAT item ID via `get_boat_item_id()`.
    """
    if not BOAT_API_ENABLED:
        return {'error': 'UnbelivableBoat API is not configured.'}

    guild_id = GUILD_ID
    if not guild_id:
        return {'error': 'No guild ID configured for BOAT inventory update.'}

    if quantity <= 0:
        quantity = 1

    async with aiohttp.ClientSession() as session:
        url = f'{BOAT_API_BASE_URL.rstrip("/")}/guilds/{guild_id}/users/{discord_id}/inventory'
        payload = {'item_id': item_id, 'quantity': quantity}
        async with session.post(url, json=payload, headers=get_boat_headers(), timeout=10) as response:
            text = await response.text()
            if response.status >= 400:
                try:
                    data = json.loads(text)
                    return {'error': data.get('error') or data.get('message') or f'HTTP {response.status}'}
                except json.JSONDecodeError:
                    return {'error': text.strip() or f'HTTP {response.status}'}

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {'error': 'Invalid JSON response from BOAT API.'}


async def award_boat_item(discord_id: str, item_name: str, quantity: int = 1) -> tuple[bool, str]:
    """Award an item via the BOAT API and return success status plus message."""
    if not BOAT_API_ENABLED:
        return False, 'UnbelivableBoat API is not configured.'

    if 'example' in BOAT_API_BASE_URL:
        return False, 'BOAT API base URL appears to be a placeholder. Update boatApiBaseUrl in config.json to the real BOAT endpoint.'

    item_id, lookup_error = await get_boat_item_id(item_name)
    if lookup_error:
        return False, lookup_error

    result = await add_boat_inventory_item(discord_id, item_id, quantity=quantity)
    if isinstance(result, dict) and result.get('error'):
        return False, result['error']

    if isinstance(result, dict) and result.get('message'):
        return True, result['message']

    return True, f'{item_name} awarded via UNBELIVABLEBOAT.'


async def remove_boat_inventory_item(discord_id: str, item_id: str, quantity: int = 1) -> dict:
    if not BOAT_API_ENABLED:
        return {'error': 'UnbelivableBoat API is not configured.'}

    guild_id = GUILD_ID
    if not guild_id:
        return {'error': 'No guild ID configured for BOAT inventory update.'}

    if quantity <= 0:
        quantity = 1

    async with aiohttp.ClientSession() as session:
        url = f'{BOAT_API_BASE_URL.rstrip("/")}/guilds/{guild_id}/users/{discord_id}/inventory/{item_id}'
        params = {'quantity': quantity}
        async with session.delete(url, params=params, headers=get_boat_headers(), timeout=10) as response:
            text = await response.text()
            if response.status >= 400:
                try:
                    data = json.loads(text)
                    return {'error': data.get('error') or data.get('message') or f'HTTP {response.status}'}
                except json.JSONDecodeError:
                    return {'error': text.strip() or f'HTTP {response.status}'}

            if not text.strip():
                return {}

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {'error': 'Invalid JSON response from BOAT API.'}


async def remove_boat_item(discord_id: str, item_name: str, quantity: int = 1) -> tuple[bool, str]:
    if not BOAT_API_ENABLED:
        return False, 'UnbelivableBoat API is not configured.'

    if 'example' in BOAT_API_BASE_URL:
        return False, 'BOAT API base URL appears to be a placeholder. Update boatApiBaseUrl in config.json to the real BOAT endpoint.'

    item_id, lookup_error = await get_boat_item_id(item_name)
    if lookup_error:
        return False, lookup_error

    result = await remove_boat_inventory_item(discord_id, item_id, quantity=quantity)
    if isinstance(result, dict) and result.get('error'):
        return False, result['error']

    if isinstance(result, dict) and result.get('message'):
        return True, result['message']

    return True, f'{item_name} removed via UNBELIVABLEBOAT.'


async def get_boat_inventory(discord_id: str) -> tuple[bool, str | None, list[dict] | None]:
    if not BOAT_API_ENABLED:
        return False, 'UnbelivableBoat API is not configured.', None

    guild_id = GUILD_ID
    if not guild_id:
        return False, 'No guild ID configured for BOAT inventory lookup.', None

    url = f'{BOAT_API_BASE_URL.rstrip("/")}/guilds/{guild_id}/users/{discord_id}/inventory'
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_boat_headers(), timeout=10) as response:
            text = await response.text()
            if response.status >= 400:
                try:
                    data = json.loads(text)
                    return False, data.get('error') or data.get('message') or f'HTTP {response.status}', None
                except json.JSONDecodeError:
                    return False, text.strip() or f'HTTP {response.status}', None

            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return False, 'Invalid JSON response from BOAT API inventory lookup.', None

            items = None
            if isinstance(payload, dict):
                items = payload.get('inventory') or payload.get('items') or payload.get('data')
            if items is None and isinstance(payload, list):
                items = payload

            if not isinstance(items, list):
                return False, 'Unexpected BOAT inventory response format.', None

            return True, None, items


async def get_boat_item_quantity(discord_id: str, item_name: str) -> tuple[bool, str | None, int]:
    success, error, items = await get_boat_inventory(discord_id)
    if not success:
        return False, error, 0

    normalized_name = item_name.lower()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name', '')).lower()
        if normalized_name == name or normalized_name in name:
            quantity = item.get('quantity') or item.get('qty') or item.get('amount') or item.get('count')
            try:
                return True, None, int(quantity or 0)
            except (TypeError, ValueError):
                return True, None, 0

    return True, None, 0


async def award_boat_cash(discord_id: str, amount: int) -> tuple[bool, str]:
    if amount <= 0:
        return True, 'No cash awarded.'

    if not BOAT_API_ENABLED:
        return True, f'Would have awarded {amount} {BLACK_MONEY_ITEM_NAME}, but BOAT API is not configured.'

    return await award_boat_item(discord_id, BLACK_MONEY_ITEM_NAME, quantity=amount)


async def award_in_game_cash(username: str, amount: int) -> tuple[bool, str]:
    if amount <= 0:
        return True, 'No cash awarded.'

    if not username or not username.strip():
        return False, 'No Roblox username supplied for cash award.'

    command = f'!add-money {username.strip()} {amount}'
    try:
        result = await erlc_client.send_game_hint(username.strip(), command)
    except Exception as exc:
        return False, str(exc)

    # TEMP DEBUG: log raw result from ERLC client
    try:
        print(f'[DEBUG] award_in_game_cash send_game_hint result -> {result}')
    except Exception:
        pass

    if isinstance(result, dict) and result.get('error'):
        return False, result['error']

    return True, f'Added {amount} to {username.strip()} via in-game command.'


async def patch_boat_user_balance(discord_id: str, bank_delta: int, cash_delta: int = 0, reason: str = 'balance_update') -> tuple[bool, str]:
    """Patch the BOAT user balance using delta values.

    The BOAT patch endpoint applies provided bank/cash values as adjustments.
    Use a negative bank_delta to deduct funds.
    """
    if not BOAT_API_ENABLED:
        return False, 'UnbelivableBoat API is not configured.'

    guild_id = GUILD_ID
    if not guild_id:
        return False, 'No guild ID configured for BOAT balance update.'

    url = f'{BOAT_API_BASE_URL.rstrip('/')}/guilds/{guild_id}/users/{discord_id}'
    payload = {
        'cash': str(cash_delta),
        'bank': str(bank_delta),
        'reason': reason,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(url, json=payload, headers=get_boat_headers(), timeout=10) as response:
                text = await response.text()
                if response.status >= 400:
                    try:
                        data = json.loads(text)
                        return False, data.get('error') or data.get('message') or f'HTTP {response.status}'
                    except json.JSONDecodeError:
                        return False, text.strip() or f'HTTP {response.status}'

                try:
                    data = json.loads(text)
                    if isinstance(data, dict) and data.get('message'):
                        return True, data.get('message')
                except json.JSONDecodeError:
                    pass

                return True, 'BOAT balance updated.'
        except aiohttp.ClientError as exc:
            return False, str(exc)


async def get_boat_user_profile(discord_id: str) -> tuple[bool, str | None, dict | None]:
    if not BOAT_API_ENABLED:
        return False, 'UnbelivableBoat API is not configured.', None

    guild_id = GUILD_ID
    if not guild_id:
        return False, 'No guild ID configured for BOAT user profile lookup.', None

    url = f'{BOAT_API_BASE_URL.rstrip('/')}/guilds/{guild_id}/users/{discord_id}'
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=get_boat_headers(), timeout=10) as response:
                text = await response.text()
                if response.status >= 400:
                    try:
                        data = json.loads(text)
                        return False, data.get('error') or data.get('message') or f'HTTP {response.status}', None
                    except json.JSONDecodeError:
                        return False, text.strip() or f'HTTP {response.status}', None

                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    return False, 'Invalid JSON response from BOAT user profile lookup.', None

                return True, None, data
        except aiohttp.ClientError as exc:
            return False, str(exc), None


async def update_boat_user_bank(discord_id: str, bank_amount: int, cash_amount: int | None = None) -> tuple[bool, str]:
    if not BOAT_API_ENABLED:
        return False, 'UnbelivableBoat API is not configured.'

    guild_id = GUILD_ID
    if not guild_id:
        return False, 'No guild ID configured for BOAT balance update.'

    if cash_amount is None:
        cash_amount = 0

    url = f'{BOAT_API_BASE_URL.rstrip('/')}/guilds/{guild_id}/users/{discord_id}'
    payload = {
        'cash': str(cash_amount),
        'bank': str(bank_amount),
        'reason': 'signaaliblokker',
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(url, json=payload, headers=get_boat_headers(), timeout=10) as response:
                text = await response.text()
                if response.status >= 400:
                    try:
                        data = json.loads(text)
                        return False, data.get('error') or data.get('message') or f'HTTP {response.status}'
                    except json.JSONDecodeError:
                        return False, text.strip() or f'HTTP {response.status}'

                try:
                    data = json.loads(text)
                    if isinstance(data, dict) and data.get('message'):
                        return True, data.get('message')
                except json.JSONDecodeError:
                    pass

                return True, 'BOAT bank balance updated.'
        except aiohttp.ClientError as exc:
            return False, str(exc)


def format_player_location(player_data: dict) -> str:
    if not player_data:
        return 'Location data is not available.'

    if 'error' in player_data:
        return f"API error: {player_data['error']}"

    location = player_data.get('location')
    if isinstance(location, dict):
        parts = []
        building_number = location.get('BuildingNumber')
        street_name = location.get('StreetName')
        postal_code = location.get('PostalCode')
        location_x = location.get('LocationX')
        location_z = location.get('LocationZ')

        if building_number and street_name:
            parts.append(f'{building_number} {street_name}')
        elif street_name:
            parts.append(street_name)

        if postal_code:
            parts.append(f'Postal code {postal_code}')

        if location_x is not None and location_z is not None:
            parts.append(f'Coordinates: {location_x}, {location_z}')

        if parts:
            return ' — '.join(parts)

    return json.dumps(player_data, indent=2)


def is_player_at_coordinates(player_data: dict, target_x: float, target_z: float, tolerance: float = 10.0) -> bool:
    # Use the shared helper which supports both nested `location` objects and
    # top-level latitude/longitude fields returned by the mock ERLC server.
    x, z = get_player_coordinates(player_data)
    if x is None or z is None:
        return False

    try:
        return (
            abs(float(x) - float(target_x)) <= float(tolerance) and
            abs(float(z) - float(target_z)) <= float(tolerance)
        )
    except (TypeError, ValueError):
        return False


KILL1_AREA = {
    'label': '2051 Freedom Avenue',
    'xmin': 574.0,
    'xmax': 602.0,
    'zmin': 2337.0,
    'zmax': 2361.0,
}


def get_player_coordinates(player_data: dict) -> tuple[float | None, float | None]:
    if not isinstance(player_data, dict):
        return None, None

    location = player_data.get('location') if isinstance(player_data.get('location'), dict) else player_data
    if not isinstance(location, dict):
        return None, None

    try:
        x = float(location.get('LocationX') or location.get('locationX') or location.get('latitude') or 0)
        z = float(location.get('LocationZ') or location.get('locationZ') or location.get('longitude') or 0)
        return x, z
    except (TypeError, ValueError):
        return None, None


def is_player_in_kill1_area(player_data: dict) -> bool:
    x, z = get_player_coordinates(player_data)
    if x is None or z is None:
        return False

    return (
        KILL1_AREA['xmin'] <= x <= KILL1_AREA['xmax'] and
        KILL1_AREA['zmin'] <= z <= KILL1_AREA['zmax']
    )


def get_player_username(player_data: dict) -> str | None:
    if not isinstance(player_data, dict):
        return None

    username = player_data.get('username')
    if isinstance(username, str) and username.strip():
        return username.strip()

    player_field = player_data.get('Player') or player_data.get('player')
    if isinstance(player_field, str):
        player_name, _, _ = player_field.partition(':')
        if player_name.strip():
            return player_name.strip()

    return None


def format_wait_duration(seconds: int) -> str:
    total_seconds = max(0, int(seconds))
    if total_seconds >= 60:
        minutes, remainder = divmod(total_seconds, 60)
        if remainder == 0:
            return '1 minut' if minutes == 1 else f'{minutes} minutit'
        return f'{minutes} minutit {remainder} sekundit'
    return '1 sekund' if total_seconds == 1 else f'{total_seconds} sekundit'


async def ensure_player_stays(user_id: int, username: str, location: dict, duration: int, interaction: discord.Interaction | None = None, check_interval: float = 2.0) -> bool:
    """Ensure the player remains at `location` for `duration` seconds.

    Returns True if the player stayed the full duration, False if they left.
    If an `interaction` is provided we will send a brief ephemeral failure message when
    the player leaves.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + float(duration)
    last_update_time = None
    while loop.time() < deadline:
        try:
            player_data = await erlc_client.get_player_location(username)
            if not location_matches(player_data, location):
                if interaction is not None:
                    try:
                        await interaction.followup.send(
                            'Toiming ebaõnnestus: sa lahkusid asukohast enne protsessi lõppu.',
                            ephemeral=True,
                        )
                    except Exception:
                        pass
                # Clean up the heist session if present
                cleanup_heist_session(user_id)
                return False
        except Exception:
            # If we can't fetch location, be conservative and continue polling
            pass

        now = loop.time()
        remaining = max(0, int(deadline - now))
        if interaction is not None and (last_update_time is None or now - last_update_time >= 15.0):
            try:
                await interaction.followup.send(
                    f'Jäänud aeg: {format_wait_duration(remaining)}',
                    ephemeral=True,
                )
            except Exception:
                pass
            last_update_time = now

        await asyncio.sleep(check_interval)

    return True


async def kill_players_in_kill1_area(interaction: discord.Interaction) -> tuple[list[str], list[str]]:
    player_locations = await erlc_client.get_all_player_locations()
    if isinstance(player_locations, dict) and player_locations.get('error'):
        return [], [player_locations['error']]

    if not isinstance(player_locations, list):
        return [], ['Unexpected player location format']

    targets = []
    seen_usernames = set()
    for player in player_locations:
        if not is_player_in_kill1_area(player):
            continue

        username = get_player_username(player)
        if username and username not in seen_usernames:
            seen_usernames.add(username)
            targets.append(username)

    if not targets:
        return [], []

    killed = []
    failed = []

    # Send a single combined kill command to reduce load on the ERLC API.
    # If there's one target, use `:kill USERNAME`. If multiple, comma-separate: `:kill user1,user2`.
    try:
        usernames = [u for u in targets if u]
        if not usernames:
            return [], []

        if len(usernames) == 1:
            kill_command = f':kill {usernames[0]}'
        else:
            # No spaces between commas to match expected in-game kill format
            kill_command = f":kill {','.join(usernames)}"

        result = await erlc_client.send_game_hint('', kill_command)
        if isinstance(result, dict) and result.get('error'):
            # Treat as a single failure for the whole batch
            failed.append(result.get('error'))
            return [], failed
        # Assume success if no explicit error returned
        return usernames, []
    except Exception as exc:
        return [], [str(exc)]


def get_cctv_location_display_name(location_name: str) -> str:
    if not location_name:
        return 'siia'

    cleaned = str(location_name).strip()
    lowered = cleaned.lower()
    if 'juveel' in lowered:
        return 'juveelipoes'
    if 'pank' in lowered:
        return 'pangas'
    return cleaned


async def send_cctv_alert(interaction: discord.Interaction, location_name: str, has_blocker: bool, alert_triggered: bool):
    """Send a CCTV alert to the alert channel and optionally DM the player if blocker failed."""
    try:
        # Get the guild and police role
        guild = interaction.guild
        if not guild:
            return
        
        police_role = discord.utils.get(guild.roles, id=POLICE_ROLE_ID)
        if not police_role:
            return
        
        # Determine alert status
        if not has_blocker:
            alert_status = "🚨 AKTIIVNE ALARM 🚨"
        elif alert_triggered:
            alert_status = "🚨 Signaaliblokker ebaõnnestus — alarm läks käima 🚨"
        else:
            alert_status = "✅ Signaaliblokker toimis — alarm ei aktiveerunud ✅"
        
        display_name = get_cctv_location_display_name(location_name)

        # Create embed message
        embed = discord.Embed(
            title="Aktiivne rööv",
            description=f"Keegi teatas, et {display_name} toimub midagi kahtlast.",
            color=discord.Color.red() if alert_triggered else discord.Color.green()
        )
        embed.add_field(name="Staatus", value=alert_status, inline=False)
        embed.add_field(name="Asukoht", value=display_name, inline=False)
        
        if alert_triggered:
            # Send alert message to the alert channel with police ping
            try:
                alert_channel = await client.fetch_channel(int(CCTV_ALERT_CHANNEL_ID))
                if alert_channel:
                    await alert_channel.send(
                        f"{police_role.mention}",
                        embed=embed
                    )
            except Exception as e:
                print(f"Error sending alert to channel: {e}")
            
            if has_blocker:
                await send_public_notification(
                    interaction,
                    f"Uhoh... Lekitatud info: keegi nägi sind {display_name} ja helistas politseisse!"
                )
        else:
            if has_blocker:
                await send_public_notification(
                    interaction,
                    "Hei! Boss ütleb, et politsei raadio tundub vaikne ja kaamerad võivad olla maas. Tegutse kiiresti!"
                )
    except Exception as e:
        print(f"Error sending CCTV alert: {e}")


async def check_cctv(interaction: discord.Interaction, user_id: int, mission_data: dict) -> bool:
    """Check CCTV and handle alert. Returns True if alert was triggered."""
    import random
    
    if not mission_data.get('has_cctv'):
        return False
    
    try:
        guild = interaction.guild
        if not guild:
            return False
        
        # Check if user has Blokker role
        member = await guild.fetch_member(user_id)
        blokker_role = discord.utils.get(guild.roles, id=BLOKKER_ROLE_ID)
        has_blokker_role = blokker_role in member.roles if blokker_role else False
        
        alert_triggered = False
        
        if not has_blokker_role:
            # No blocker role = immediate alert
            alert_triggered = True
        else:
            # Has blocker role = 30% chance to fail
            if random.random() < CCTV_ALERT_FAILURE_CHANCE:
                alert_triggered = True
        
        # Send the alert notification
        await send_cctv_alert(interaction, mission_data['name'], has_blokker_role, alert_triggered)
        
        return alert_triggered
    except Exception as e:
        print(f"Error checking CCTV: {e}")
        return False


async def send_movement_camera_alert(interaction: discord.Interaction) -> None:
    try:
        alert_message = (
            'Sissemurdmine\n'
            'Keegi on vanasse pesumajja sisse murdnud.\n'
            'Asukoht: Haapsalu vana tsiviilspawn. (11042)'
        )
        alert_channel = await client.fetch_channel(int(CCTV_ALERT_CHANNEL_ID))
        if alert_channel:
            await alert_channel.send(alert_message)
    except Exception as e:
        print(f"Error sending movement camera alert: {e}")


async def check_laundering_alerts(interaction: discord.Interaction) -> bool:
    import random

    cctv_triggered = await check_cctv(interaction, interaction.user.id, {
        'name': LAUNDROMAT_LOCATION['label'],
        'has_cctv': LAUNDROMAT_LOCATION['has_cctv'],
    })

    movement_triggered = random.random() < 0.30
    if movement_triggered and not cctv_triggered:
        await send_movement_camera_alert(interaction)

    return cctv_triggered or movement_triggered


async def poll_for_arrival(username: str, location: dict, interaction: discord.Interaction, timeout_seconds: int = 300, check_cctv_on_arrival: bool = True) -> tuple[bool, bool]:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    arrived = False
    cctv_checked = False
    alert_triggered = False

    while asyncio.get_event_loop().time() < deadline:
        try:
            player_data = await erlc_client.get_player_location(username)
            if location_matches(player_data, location):
                arrived = True
                
                if check_cctv_on_arrival and not cctv_checked and location.get('has_cctv'):
                    cctv_checked = True
                    alert_triggered = await check_cctv(interaction, interaction.user.id, location)
                
                return arrived, alert_triggered
        except Exception:
            pass

        await asyncio.sleep(10)

    return arrived, alert_triggered


async def poll_for_zip_arrival(
    username: str,
    location: dict,
    timeout_seconds: int = 300,
) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout_seconds

    while asyncio.get_event_loop().time() < deadline:
        try:
            player_data = await erlc_client.get_player_location(username)
            if location_matches(player_data, location):
                return True
        except Exception:
            pass

        await asyncio.sleep(10)

    return False


async def poll_for_coordinate_arrival(
    username: str,
    target_x: float,
    target_z: float,
    tolerance: float,
    interaction: discord.Interaction,
    timeout_seconds: int = 300,
) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout_seconds

    while asyncio.get_event_loop().time() < deadline:
        try:
            player_data = await erlc_client.get_player_location(username)
            if is_player_at_coordinates(player_data, target_x, target_z, tolerance):
                return True
        except Exception:
            pass

        await asyncio.sleep(10)

    return False


async def monitor_heist_area(username: str, heist_key: str, interaction: discord.Interaction):
    user_id = interaction.user.id
    session = active_heist_sessions.get(user_id)
    if not session:
        return

    heist_data = HEIST_LOCATIONS.get(heist_key)
    if not heist_data:
        return

    while True:
        await asyncio.sleep(10)
        session = active_heist_sessions.get(user_id)
        if not session or not session.get('arrived'):
            return

        try:
            player_data = await erlc_client.get_player_location(username)
            if not location_matches(player_data, heist_data):
                await interaction.followup.send(
                    'Heist ebaõnnestus: sa lahkusid piirkonnast enne, kui raha oli tasku pistetud. Proovi uuesti hiljem.',
                    ephemeral=True,
                )
                cleanup_heist_session(user_id)
                return
        except Exception:
            pass


def cleanup_heist_session(user_id: int):
    active_sessions.discard(user_id)
    session = active_heist_sessions.pop(user_id, None)
    if session and session.get('monitor_task'):
        task = session['monitor_task']
        if not task.done():
            task.cancel()


def get_challenge_choices() -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=data['display_name'], value=key) for key, data in CHALLENGES.items()]


def get_mission_choices(challenge_key: str) -> list[app_commands.Choice[str]]:
    challenge = CHALLENGES.get(challenge_key)
    if not challenge:
        return []
    return [app_commands.Choice(name=mission['name'], value=mission['id']) for mission in challenge['missions']]


def get_heist_choices() -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=data['label'], value=key) for key, data in HEIST_LOCATIONS.items()]


def get_heist_info_choices() -> list[app_commands.Choice[str]]:
    return HEIST_INFO_CHOICES


async def heist_info_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    choices = get_heist_info_choices()
    return [c for c in choices if current.lower() in c.name.lower()][:25]


async def challenge_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    choices = get_challenge_choices()
    return [c for c in choices if current.lower() in c.name.lower()][:25]


async def heist_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    choices = get_heist_choices()
    return [c for c in choices if current.lower() in c.name.lower()][:25]


def format_heist_embed(location_data: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"Rööv: {location_data['label']}",
        description=f"ZIP {location_data['zip']} — siin on turvakaamerad.",
        color=discord.Color.dark_blue()
    )
    embed.add_field(name='Asukoht', value=location_data['label'], inline=False)
    embed.add_field(name='ZIP', value=location_data['zip'], inline=True)
    embed.add_field(name='Kaamerad', value='✅ Jah', inline=True)
    embed.set_image(url=location_data['image_url'])
    embed.set_footer(text=location_data['picture_reference'])
    return embed


class HeistInfoChoiceView(View):
    def __init__(self, user_id: int, heist_choice: str, username: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.heist_choice = heist_choice
        self.username = username

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('See valik pole sinu jaoks.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Yes', style=discord.ButtonStyle.success, custom_id='heistinfo_yes')
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        session = active_heist_info_sessions.get(self.user_id)
        if not session:
            await interaction.followup.send('Heist Info missioon on möödas või aegunud.', ephemeral=True)
            return

        if session.get('stage') != 'ask_blocker':
            await interaction.followup.send('See valik ei sobi praeguse sammuga.', ephemeral=True)
            return

        session['stage'] = 'electronics'
        await interaction.followup.send(
            'Mine elektroonikapoodi.\nZIP: 403\nPalun poodi siseneda.',
            ephemeral=True,
        )

        arrived = await poll_for_coordinate_arrival(
            self.username,
            HEIST_INFO_ELECTRONICS_AREA['center_x'],
            HEIST_INFO_ELECTRONICS_AREA['center_z'],
            HEIST_INFO_ELECTRONICS_AREA['tolerance'],
            interaction,
            timeout_seconds=300,
        )

        if not arrived:
            await interaction.followup.send(
                'Ebaõnnestunud: sa ei jõudnud elektroonikapoodi 5 minuti jooksul.',
                ephemeral=True,
            )
            active_heist_info_sessions.pop(self.user_id, None)
            return

        view = SignaaliblokkerPurchaseView(self.user_id)
        await interaction.followup.send(
            'Kas sa tahad osta signaaliblokkerit 25 000 eest? (Kestab 2 röövi)',
            view=view,
            ephemeral=True,
        )
        self.disable_all_items()

    @discord.ui.button(label='No', style=discord.ButtonStyle.danger, custom_id='heistinfo_no')
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        session = active_heist_info_sessions.pop(self.user_id, None)
        if not session:
            await interaction.followup.send('Heist Info missioon on möödas või aegunud.', ephemeral=True)
            return

        await interaction.followup.send('Okei, sa ei soovi osta. Head aega.', ephemeral=True)
        self.disable_all_items()

    def disable_all_items(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True


class CreditCardPurchaseView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('See valik pole sinu jaoks.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Jah', style=discord.ButtonStyle.success, custom_id='credit_card_yes')
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        updated, update_message = await patch_boat_user_balance(
            str(self.user_id),
            bank_delta=-25000,
            cash_delta=0,
            reason='krediitkaart_signaaliblokker',
        )
        self.disable_all_items()
        await interaction.edit_original_response(view=self)
        if not updated:
            await interaction.followup.send(
                f'Signaali blokkeri krediitkaardi ostmine ebaõnnestus: {update_message}',
                ephemeral=True,
            )
            return

        success, message = await award_boat_item(str(self.user_id), 'Signaali blokker')
        if success:
            await interaction.followup.send(
                'Te maksite krediitkaardiga 25 000. Raha võetakse ära ja te võite jääda miinustesse. Signaali blokker lisatud sinu inventuuri.',
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f'Te maksite krediitkaardiga 25 000, kuid signaali blokkeri lisamine inventuuri ebaõnnestus: {message}',
                ephemeral=True,
            )

    @discord.ui.button(label='Ei', style=discord.ButtonStyle.danger, custom_id='credit_card_no')
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        self.disable_all_items()
        await interaction.edit_original_response(view=self)
        await interaction.followup.send(
            'Okei, sa ei soovi krediitkaardiga maksta. Head aega.',
            ephemeral=True,
        )

    def disable_all_items(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True


class SignaaliblokkerPurchaseView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('See valik pole sinu jaoks.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Jah', style=discord.ButtonStyle.success, custom_id='buy_blocker_yes')
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not BOAT_API_ENABLED:
            self.disable_all_items()
            await interaction.edit_original_response(view=self)
            await interaction.followup.send('BOAT API pole konfigureeritud, ei saa osta.', ephemeral=True)
            return

        success, error, profile = await get_boat_user_profile(str(self.user_id))
        if not success or not profile:
            self.disable_all_items()
            await interaction.edit_original_response(view=self)
            await interaction.followup.send('Mügimees ütles, et teie kaardil pole piisavalt vahendeid.', ephemeral=True)
            return

        bank_amount = 0
        cash_amount = 0
        if isinstance(profile, dict):
            try:
                bank_amount = int(profile.get('bank', profile.get('Bank', 0) or 0))
            except (TypeError, ValueError):
                bank_amount = 0
            try:
                cash_amount = int(profile.get('cash', profile.get('Cash', 0) or 0))
            except (TypeError, ValueError):
                cash_amount = 0

        if bank_amount < 25000:
            self.disable_all_items()
            await interaction.edit_original_response(view=self)
            credit_view = CreditCardPurchaseView(self.user_id)
            await interaction.followup.send(
                'Selletõttu, et teil pole piisavalt vahendeid, kas te soovite krediitkaardiga maksta? (Raha võetakse ära ja võite jääda miinustesse)',
                view=credit_view,
                ephemeral=True,
            )
            return

        updated, update_message = await patch_boat_user_balance(
            str(self.user_id),
            bank_delta=-25000,
            cash_delta=0,
            reason='signaaliblokker',
        )
        if not updated:
            self.disable_all_items()
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(f'Signaali blokkeri ostmine ebaõnnestus: {update_message}', ephemeral=True)
            return

        success, message = await award_boat_item(str(self.user_id), 'Signaali blokker')
        self.disable_all_items()
        await interaction.edit_original_response(view=self)
        if success:
            await interaction.followup.send('Signaali blokker lisatud sinu inventuuri.', ephemeral=True)
        else:
            await interaction.followup.send(f'Signaali blokker osteti, kuid lisamine inventuuri ebaõnnestus: {message}', ephemeral=True)

    @discord.ui.button(label='Ei', style=discord.ButtonStyle.danger, custom_id='buy_blocker_no')
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        self.disable_all_items()
        await interaction.edit_original_response(view=self)
        await interaction.followup.send('Okei, sa ei soovi osta. Head aega.', ephemeral=True)

    def disable_all_items(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True


async def heistinfo(
    interaction: discord.Interaction,
    location: str,
    username: str,
):
    await interaction.response.defer(ephemeral=True)
    user_id = interaction.user.id
    if user_id in active_heist_info_sessions:
        await interaction.followup.send(
            'Sul on juba aktiivne HeistInfo missioon. Oota, kuni see lõpeb.',
            ephemeral=True,
        )
        return

    info = HEIST_INFO_LOCATIONS.get(location)
    if not info:
        await interaction.followup.send('Vali õige heistiga koht: Juveel või Pank.', ephemeral=True)
        return

    heist_location = info['stage_one_location']
    if location == 'juveelid':
        location_message = f"Sõida ZIP {heist_location['zip']}, {heist_location['label'].split(' (')[0]}"
    else:
        location_message = f"Sõida asukohta: {heist_location['label']}"

    active_heist_info_sessions[user_id] = {
        'username': username,
        'choice': location,
        'stage': 'arrive',
        'location': heist_location,
    }

    await interaction.followup.send(
        f'{location_message}',
        ephemeral=True,
    )

    arrived, _ = await poll_for_arrival(username, heist_location, interaction, timeout_seconds=60, check_cctv_on_arrival=False)
    if not arrived:
        await interaction.followup.send(
            'Ebaõnnetus: sa ei jõudnud valitud asukohta 1 minuti jooksul.',
            ephemeral=True,
        )
        active_heist_info_sessions.pop(user_id, None)
        return

    await interaction.followup.send('Sa uurid järgmised 10 sekundit ümbrust.', ephemeral=True)
    stay_start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - stay_start < 10:
        try:
            player_data = await erlc_client.get_player_location(username)
            if not location_matches(player_data, heist_location):
                await interaction.followup.send('Sa lahkusid asukohast enne 10 sekundi möödumist. Proovi uuesti.', ephemeral=True)
                active_heist_info_sessions.pop(user_id, None)
                return
        except Exception:
            pass
        await asyncio.sleep(10)

    session = active_heist_info_sessions.get(user_id)
    if not session:
        return
    session['stage'] = 'ask_blocker'

    view = HeistInfoChoiceView(user_id, location, username)
    await interaction.followup.send(
        'Hmm.. Tundub, et siin on turvakaamerad.\nBoss soovitab signaaliblokkerit.\nKas sa soovid seda?',
        view=view,
        ephemeral=True,
    )


@bot.command(name='heistinfo', description='Start the HeistInfo flow and get hidden electronics location')
@app_commands.describe(
    location='Which heist location to scout',
    username='Roblox username'
)
@app_commands.autocomplete(location=heist_info_autocomplete)
async def heistinfo_command(
    interaction: discord.Interaction,
    location: str,
    username: str,
):
    await heistinfo(interaction, location, username)


async def run_heist(interaction: discord.Interaction, heist_key: str, username: str):
    await interaction.response.defer(ephemeral=True)
    heist_data = HEIST_LOCATIONS.get(heist_key)
    if not heist_data:
        await interaction.followup.send('Invalid heist selection.', ephemeral=True)
        return

    user_id = interaction.user.id
    if user_id in active_sessions:
        await interaction.followup.send('Sul on juba aktiivne heist. Vali oma tööriist selle heisti jaoks.', ephemeral=True)
        return

    # Previously there was a strict pre-check for being inside the kill area here.
    # Remove that pre-check so the user receives the normal heist arrival prompt
    # and is given 5 minutes to reach the bank location.

    active_sessions.add(user_id)
    active_heist_sessions[user_id] = {
        'heist_key': heist_key,
        'username': username,
        'arrived': False,
        'alert_triggered': False,
        'stage': 'gate' if heist_data.get('requires_gate') else 'safe',
        'monitor_task': None,
    }

    embed = format_heist_embed(heist_data)
    await interaction.followup.send(embed=embed, ephemeral=True)
    await interaction.followup.send(
        (
            f'Mine {heist_data["label"]} ZIP {heist_data["zip"]} juurde.\n'
            'Sul on 5 minutit, et sinna jõuda.'
        ),
        ephemeral=True,
    )

    arrived, _ = await poll_for_arrival(username, heist_data, interaction, timeout_seconds=300, check_cctv_on_arrival=False)

    if not arrived:
        await interaction.followup.send('Ei õnnestunud: sa ei jõudnud asukohta õigeaegselt.', ephemeral=True)
        cleanup_heist_session(user_id)
        return

    session = active_heist_sessions.get(user_id)
    if session is None:
        await interaction.followup.send('Heist missioon kadus enne kui jõudsid kohale.', ephemeral=True)
        cleanup_heist_session(user_id)
        return

    session['arrived'] = True
    session['monitor_task'] = asyncio.create_task(monitor_heist_area(username, heist_key, interaction))

    view = HeistToolView(user_id, heist_key, heist_data, stage=session['stage'])
    if session['stage'] == 'gate':
        await interaction.followup.send(
            (
                'Okei. Enne kui sa pääsed seifini sa pead saama turvavärava lahti. '
                'Mida sa kasutad?'
            ),
            view=view,
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            (
                'Okei, sa oled nüüd kohal. Nüüd on sinu otsustada, mida sa järgmisena kasutad.'
            ),
            view=view,
            ephemeral=True,
        )


def get_boat_tool_item_name(tool_key: str) -> str:
    if tool_key == 'Pomm':
        return 'Pomm'
    if tool_key == 'laserlõikur':
        return 'Laserlõikur'
    return 'Klaasilõikur'


class HeistToolView(View):
    def __init__(self, user_id: int, heist_key: str, heist_data: dict, stage: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.heist_key = heist_key
        self.heist_data = heist_data
        self.stage = stage
        self.used = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('See nupuvalik pole sinu jaoks.', ephemeral=True)
            return False
        if self.used:
            await interaction.response.send_message('Sa oled juba tööriista valinud. Oota, kuni protsess lõpeb.', ephemeral=True)
            return False
        return True

    def disable_all_items(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label='Pauk', style=discord.ButtonStyle.primary, custom_id='heist_tool_pauk')
    @discord.ui.button(label='Pomm', style=discord.ButtonStyle.primary, custom_id='heist_tool_pomm')
    async def pomm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_tool(interaction, 'Pomm')

    @discord.ui.button(label='Laserlõikur', style=discord.ButtonStyle.success, custom_id='heist_tool_laser')
    async def laserlõikur_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_tool(interaction, 'laserlõikur')

    @discord.ui.button(label='Klaasilõikur', style=discord.ButtonStyle.danger, custom_id='heist_tool_klaas')
    async def klaasilõikur_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_tool(interaction, 'klaasilõikur')

    async def process_tool(self, interaction: discord.Interaction, tool_key: str):
        session = active_heist_sessions.get(self.user_id)
        if not session:
            await interaction.response.send_message('Heist missioon ei ole enam aktiivne.', ephemeral=True)
            return

        item_name = get_boat_tool_item_name(tool_key)
        owned, error, quantity = await get_boat_item_quantity(str(self.user_id), item_name)
        if not owned:
            await interaction.response.send_message(
                f'Inventuuri kontroll ebaõnnestus: {error}',
                ephemeral=True,
            )
            return

        if quantity <= 0:
            await interaction.response.send_message(
                f'Sul pole inventuuris tööriista {item_name}.',
                ephemeral=True,
            )
            return

        removed, remove_error = await remove_boat_item(str(self.user_id), item_name)
        if not removed:
            await interaction.response.send_message(
                f'Inventuuri uuendamine ebaõnnestus: {remove_error}',
                ephemeral=True,
            )
            return

        self.used = True
        self.disable_all_items()
        try:
            await interaction.response.edit_message(view=self)
        except Exception:
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

        await interaction.followup.send('Sa tegutsed... ⏳', ephemeral=True)

        alarm_sent = session.get('alert_triggered', False)
        is_bank_heist = self.heist_data.get('requires_gate') and 'pank' in (self.heist_data.get('label') or '').lower()

        if self.stage == 'gate':
            success, outcome_message, alert_triggered = await handle_bank_gate_tool(interaction, tool_key, self.heist_data)
            await interaction.followup.send(outcome_message, ephemeral=True)
            if alert_triggered:
                await send_cctv_alert(interaction, self.heist_data['label'], has_blocker=False, alert_triggered=True)
                session['alert_triggered'] = True
                alarm_sent = True
            if not success:
                active_sessions.discard(self.user_id)
                active_heist_sessions.pop(self.user_id, None)
                return

            session['stage'] = 'safe'
            view = HeistToolView(self.user_id, self.heist_key, self.heist_data, stage='safe')
            await interaction.followup.send(
                'Okei, tubli. Sa oled seifi juures. Millega sa seifi lahti teed?',
                view=view,
                ephemeral=True,
            )
            return

        is_juveel_heist = 'juveel' in (self.heist_data.get('label') or '').lower()
        if is_juveel_heist and not alarm_sent:
            await send_cctv_alert(interaction, self.heist_data['label'], has_blocker=False, alert_triggered=True)
            session['alert_triggered'] = True
            alarm_sent = True
        elif tool_key == 'Pomm' and not alarm_sent:
            await send_cctv_alert(interaction, self.heist_data['label'], has_blocker=False, alert_triggered=True)
            session['alert_triggered'] = True
            alarm_sent = True
        elif tool_key == 'laserlõikur' and is_bank_heist and not alarm_sent:
            await send_cctv_alert(interaction, self.heist_data['label'], has_blocker=False, alert_triggered=True)
            session['alert_triggered'] = True
            alarm_sent = True

        reward_amount, outcome_message, alert_triggered, items = await handle_bank_safe_tool(interaction, tool_key, self.heist_data)
        if alert_triggered and not alarm_sent:
            await send_cctv_alert(interaction, self.heist_data['label'], has_blocker=False, alert_triggered=True)
            session['alert_triggered'] = True

        await interaction.followup.send(outcome_message, ephemeral=True)

        # Handle item awards (for diamonds etc.)
        if items:
            for item_name, qty in items:
                success, boat_message = await award_boat_item(str(self.user_id), item_name, quantity=qty)
                if success:
                    await interaction.followup.send(f'{qty}x {item_name} lisatud sinu inventuuri.', ephemeral=True)
                else:
                    await interaction.followup.send(f'Heist lõpetatud, kuid esemete lisamine ebaõnnestus: {boat_message}', ephemeral=True)

        # Handle cash awards
        if reward_amount > 0:
            success, message = await award_boat_cash(str(self.user_id), reward_amount)
            if success:
                await interaction.followup.send(
                    f'{reward_amount} Mustraha on lisatud sinu inventuuri.',
                    ephemeral=True,
                )
                if reward_amount < 10000 and self.heist_data.get('requires_gate'):
                    await send_public_notification(
                        interaction,
                        'Ai. Tundub, et rahaauto oli vahepeal raha ära viinud. Ei vea... Sa võtsid mida sa said.'
                    )
            else:
                await interaction.followup.send(
                    f'Heist lõpetatud, kuid mustaraha lisamine ebaõnnestus: {message}',
                    ephemeral=True,
                )

        active_sessions.discard(self.user_id)
        active_heist_sessions.pop(self.user_id, None)
        self.disable_all_items()
        await interaction.message.edit(view=self)


async def resolve_heist_outcome(interaction: discord.Interaction, heist_data: dict, tool_key: str) -> tuple[int, str, bool]:
    if tool_key == 'klaasilõikur':
        return 0, (
            'Boss kutsus sind tauniks. Seif on tehtud metallist, mitte klaasist. '
            'Tõmba sealt kiiresti minema, alarm käivitus ja politsei on teel!'
        ), True
    if tool_key == 'laserlõikur':
        amount = random.randint(3000, 20000)
        return amount, (
            'Okei. Hea valik, sa said peaaegu kõik rahatähed endale. '
            'Laser oli võimas ja kõrvetas paar tähte tuhaks. '
            f'Sa lugesid kokku: {amount} mustaraha.'
        ), False

    amount = random.randint(0, 1000)
    return amount, (
        'Oi oi... Pomm lasi enamus raha õhku... '
        f'Sa lugesid kokku: {amount} mustaraha.'
    ), False


async def handle_bank_gate_tool(interaction: discord.Interaction, tool_key: str, heist_data: dict | None = None) -> tuple[bool, str, bool]:
    if tool_key == 'Pomm':
        # For bank gate bombs, present localized Estonian popups and avoid leaking raw
        # coordinate strings or English diagnostic text. The flow still returns the
        # same success/failure boolean semantics as before.
        if heist_data and heist_data.get('label', '').lower() == 'pank' and random.random() < 0.90:
            killed, failed = await kill_players_in_kill1_area(interaction)
            if killed:
                killed_list = ', '.join(killed)
                return False, (
                    'Uhoh. Sinu pomm oli halvasti ehitatud ja see plahvatas koheselt.\n'
                    'Su heist kukus läbi.'
                ), True
            if failed:
                failed_list = ', '.join(failed)
                return False, (
                    'Uhoh. Sinu pomm plahvatas, kuid mõned tapmiskäsud ebaõnnestusid:\n'
                    f'{failed_list}\n'
                    'Su heist kukus läbi.'
                ), True
            return False, (
                'Uhoh. Sinu pomm oli halvasti ehitatud ja see plahvatas koheselt, kuid piirkonnas ei leitud mingeid mängijaid.\n'
                'Su heist kukus läbi.'
            ), True

        return True, 'Sa asetasid pommi väravale. Värav lendas õhku ja pääsesid seifi juurde.', True
    if tool_key == 'laserlõikur':
        return True, '--Sa lõikad laseriga luku maha--', False

    dm_message = (
        'Boss kutsus sind tauniks. Väravad ei ole klaasist tehtud. '\
        'Tõmba nüüd kiiresti minekut. Sa kukkusid läbi. Pead uuesti proovima.'
    )
    await send_public_notification(interaction, dm_message)

    await send_cctv_alert(interaction, 'Pank värav', has_blocker=False, alert_triggered=True)
    return False, 'Sa kukkusid läbi. Pead uuesti proovima.', True


async def handle_bank_safe_tool(interaction: discord.Interaction, tool_key: str, heist_data: dict) -> tuple[int, str, bool, list]:
    # Special-case for the Juveelipoe safe heist and variants
    label = (heist_data.get('label') or '').lower() if heist_data else ''
    is_juveel = 'juveel' in label or 'juveelipoe' in label
    is_deemandid = 'deem' in label or 'deemandid' in label

    # Ensure Deemand-specific logic takes precedence over generic Juveel (seif) logic
    if is_deemandid:
        # Pomm destroys all diamonds
        if tool_key == 'Pomm':
            msg = 'Pomm purustas kõik deemandid. Sa ei saanud midagi.'
            return 0, msg, False, []

        # Laser or klaas: award large diamonds or fallback to small diamonds
        if tool_key in ('laserlõikur', 'klaasilõikur'):
            await interaction.followup.send('Sa lõikad seifi... ⏳ (4 minutit)', ephemeral=True)
            # ensure the player stays for the cutting duration
            session = active_heist_sessions.get(interaction.user.id)
            username = session.get('username') if session else None
            stayed = True
            if username:
                stayed = await ensure_player_stays(interaction.user.id, username, heist_data, 240, interaction)
            else:
                await asyncio.sleep(240)

            if not stayed:
                return 0, 'Heist ebaõnnestus: sa lahkusid seifi piirkonnast.', False, []

            await interaction.followup.send('Sa kogud teemante... ⏳ (1 minut)', ephemeral=True)
            if username:
                stayed = await ensure_player_stays(interaction.user.id, username, heist_data, 60, interaction)
            else:
                await asyncio.sleep(60)

            if not stayed:
                return 0, 'Heist ebaõnnestus: sa lahkusid seifi piirkonnast.', False, []
            # 10% chance to get 1-2 Deemand Suur; otherwise get 0-20 Deemand Väike
            if random.random() < 300:
                large_qty = random.randint(1, 2)
                small_qty = 0
            else:
                large_qty = 0
                small_qty = random.randint(0, 20)

            items = []
            parts = []
            if large_qty > 0:
                items.append(('Deemand Suur', large_qty))
                parts.append(f'{large_qty}x Deemand Suur')
            if small_qty > 0:
                items.append(('Deemand Väike', small_qty))
                parts.append(f'{small_qty}x Deemand Väike')
            msg = 'Sa läksid seifi kallale. Sa said: ' + ', '.join(parts)
            return 0, msg, False, items

    if is_juveel:
        if tool_key in ('laserlõikur', 'klaasilõikur'):
            await interaction.followup.send('Sa lõikad seifi... ⏳ (4 minutit)', ephemeral=True)
            session = active_heist_sessions.get(interaction.user.id)
            username = session.get('username') if session else None
            stayed = True
            if username:
                stayed = await ensure_player_stays(interaction.user.id, username, heist_data, 240, interaction)
            else:
                await asyncio.sleep(240)

            if not stayed:
                return 0, 'Heist ebaõnnestus: sa lahkusid seifi piirkonnast.', False, []

            await interaction.followup.send('Seif on avanenud. Kogud raha... ⏳ (1 minut)', ephemeral=True)
            if username:
                stayed = await ensure_player_stays(interaction.user.id, username, heist_data, 60, interaction)
            else:
                await asyncio.sleep(60)

            if not stayed:
                return 0, 'Heist ebaõnnestus: sa lahkusid seifi piirkonnast.', False, []
            if random.random() < 0.30:
                amount = random.randint(1000, 5000)
                msg = (
                    'Sinu käed värisesid lõikamise ajal ja osa rahast kõrbes. '
                    f'Sa said kokku {amount} mustaraha.'
                )
                return amount, msg, True, []
            amount = random.randint(2000, 10000)
            msg = f'Sa lõikad lahti ja saad kokku {amount} mustaraha.'
            return amount, msg, True, []

        # Pomm: 60% chance money blown up (0-100), else 2000-10000
        if tool_key == 'Pomm':
            await interaction.followup.send('Paigaldad pommi... ⏳ (30 sekundit)', ephemeral=True)
            session = active_heist_sessions.get(interaction.user.id)
            username = session.get('username') if session else None
            stayed = True
            if username:
                stayed = await ensure_player_stays(interaction.user.id, username, heist_data, 30, interaction)
            else:
                await asyncio.sleep(30)

            if not stayed:
                return 0, 'Heist ebaõnnestus: sa lahkusid enne pommi aktiveerumist.', False, []

            await interaction.followup.send('Seif on avanenud. Kogud raha... ⏳ (1 minut)', ephemeral=True)
            if username:
                stayed = await ensure_player_stays(interaction.user.id, username, heist_data, 60, interaction)
            else:
                await asyncio.sleep(60)

            if not stayed:
                return 0, 'Heist ebaõnnestus: sa lahkusid seifi piirkonnast.', False, []
            if random.random() < 0.60:
                amount = random.randint(0, 100)
                msg = (
                    'Pomm purustas suure osa rahatähtedest! '
                    f'Sa leidsid ainult {amount} mustaraha alles.'
                )
                return amount, msg, False, []
            amount = random.randint(2000, 10000)
            msg = f'Seif avanes ja sa kogusid kokku {amount} mustaraha.'
            return amount, msg, False, []

    # Deemand-specific behavior
    if is_deemandid:
        # Pomm destroys all diamonds
        if tool_key == 'Pomm':
            await interaction.followup.send('Paigaldad pommi... ⏳ (30 sekundit)', ephemeral=True)
            session = active_heist_sessions.get(interaction.user.id)
            username = session.get('username') if session else None
            stayed = True
            if username:
                stayed = await ensure_player_stays(interaction.user.id, username, heist_data, 30, interaction)
            else:
                await asyncio.sleep(30)

            if not stayed:
                return 0, 'Heist ebaõnnestus: sa lahkusid enne pommi aktiveerumist.', False, []

            msg = 'Pomm purustas kõik deemandid. Sa ei saanud midagi.'
            return 0, msg, False, []

        # Laser or klaas: award large diamonds or fallback to small diamonds
        if tool_key in ('laserlõikur', 'klaasilõikur'):
            await interaction.followup.send('Sa töötled seifi... ⏳ (4 minutit)', ephemeral=True)
            session = active_heist_sessions.get(interaction.user.id)
            username = session.get('username') if session else None
            stayed = True
            if username:
                stayed = await ensure_player_stays(interaction.user.id, username, heist_data, 240, interaction)
            else:
                await asyncio.sleep(240)

            if not stayed:
                return 0, 'Heist ebaõnnestus: sa lahkusid seifi piirkonnast.', False, []

            # 10% chance to get 1-2 Deemand Suur; otherwise get 0-20 Deemand Väike
            if random.random() < 0.10:
                large_qty = random.randint(1, 2)
                small_qty = 0
            else:
                large_qty = 0
                small_qty = random.randint(0, 20)

            items = []
            parts = []
            if large_qty > 0:
                items.append(('Deemand Suur', large_qty))
                parts.append(f'{large_qty}x Deemand Suur')
            if small_qty > 0:
                items.append(('Deemand Väike', small_qty))
                parts.append(f'{small_qty}x Deemand Väike')
            msg = 'Sa läksid seifi kallale. Sa said: ' + ', '.join(parts) if parts else 'Sa ei leidnud deemandeid.'
            return 0, msg, False, items

    # Fallback / generic behavior for other heists
    if tool_key == 'klaasilõikur':
        dm_message = (
            'Boss kutsus sind tauniks. Seif ei ole klaasist tehtud. Tõmba minekut.'
        )
        await send_public_notification(interaction, dm_message)
        return 0, 'Seif ei avanud. Alarm käivitub.', True, []

    if tool_key == 'laserlõikur':
        if 'pank' in (label or '') and heist_data.get('requires_gate'):
            await interaction.followup.send('Sa lõikad ust laseriga... ⏳ (30 sekundit)', ephemeral=True)
            await asyncio.sleep(30)
            await interaction.followup.send('Uks on avanenud. Kogud raha... ⏳ (3 minutit)', ephemeral=True)
            await asyncio.sleep(180)
            amount = random.randint(1500, 50000)
            return amount, (
                'Sa lõikad ust laseriga ja pääsed seifi juurde. '
                f'Sa saad {amount} mustaraha.'
            ), True, []

        await interaction.followup.send('Sa lõikad ust laseriga... ⏳ (5 sekundit)', ephemeral=True)
        await asyncio.sleep(5)
        if random.random() < 0.40:
            dm_message = 'Tundub, et uks on paksem kui laser suudab lõigata.'
            await send_public_notification(interaction, dm_message)
            return 0, 'Laser ei läbinud ust. Alarm käivitub.', True, []

        amount = random.randint(1500, 50000)
        return amount, (
            'Sa lõikad ust laseriga ja pääsed seifi juurde. '
            f'Sa saad {amount} mustaraha.'
        ), False, []

    # Pomm branch
    if 'pank' in (label or '') and heist_data.get('requires_gate'):
        await interaction.followup.send(
            'Paigaldad pommi... ⏳ (30 sekundit)',
            ephemeral=True,
        )
        await asyncio.sleep(30)
        await interaction.followup.send(
            'Seif on avanenud. Nüüd on sul 30 sekundit aega raha kokku koguda. ⏳',
            ephemeral=True,
        )
        await asyncio.sleep(30)
        amount = random.randint(1500, 50000)
        return amount, (
            'Paigaldad pommi ja seif tuli lahti. '
            'Nüüd kogusid raha kokku 5 sekundi jooksul. Alarm käivitub.\n'
            f'Sa said kokku {amount} mustaraha.'
        ), False, []

    await interaction.followup.send(
        'Paigaldad Pommi... ⏳ (5 sekundit)',
        ephemeral=True,
    )
    await asyncio.sleep(5)
    amount = random.randint(1500, 50000)
    await interaction.followup.send(
        'Seif on avanenud. Nüüd on sul 5 sekundit aega raha kokku koguda. ⏳',
        ephemeral=True,
    )
    await asyncio.sleep(5)
    return amount, (
        'Paigaldad pommi ja seif tuli lahti. '
        'Nüüd kogusid raha kokku 5 sekundi jooksul. Alarm käivitub.\n'
        f'Sa said kokku {amount} mustaraha.'
    ), False, []


async def mission_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    # Return all missions from all challenges
    all_missions = []
    for challenge in CHALLENGES.values():
        for mission in challenge['missions']:
            all_missions.append(app_commands.Choice(name=mission['name'], value=mission['id']))
    
    return [m for m in all_missions if current.lower() in m.name.lower()][:25]


@bot.command(name='test', description='Test command')
async def test(interaction: discord.Interaction):
    await interaction.response.send_message('Test õnnestus!', ephemeral=True)


@bot.command(name='testhint', description='Send a test in-game hint command')
@app_commands.describe(message='Hint text to send in game')
async def testhint(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)

    hint_command = message if message.startswith(':h') else f':h {message}'
    try:
        result = await erlc_client.send_game_hint('', hint_command)
        if isinstance(result, dict) and result.get('error'):
            await interaction.followup.send(f'Vihje saatmine ebaõnnestus: {result["error"]}', ephemeral=True)
        else:
            await interaction.followup.send(f'Vihje saadetud: {hint_command}', ephemeral=True)
    except Exception as exc:
        await interaction.followup.send(f'Failed to send test hint: {exc}', ephemeral=True)


@bot.command(name='prepstart', description='Start the Roblox arrival challenge')
@app_commands.describe(
    username='Roblox username',
    challenge='Challenge to complete'
)
@app_commands.autocomplete(challenge=challenge_autocomplete)
async def prepstart(
    interaction: discord.Interaction,
    username: str,
    challenge: str,
):
    challenge_key = challenge

    user_id = interaction.user.id

    if user_id in active_sessions:
        await interaction.response.send_message('You already have an active challenge.', ephemeral=True)
        return

    challenge_data = CHALLENGES.get(challenge_key)
    if not challenge_data:
        await interaction.response.send_message('Invalid challenge selection.', ephemeral=True)
        return

    # Randomly pick a mission from the challenge
    import random
    mission_data = random.choice(challenge_data['missions'])
    if not challenge_data or not mission_data:
        await interaction.response.send_message('Invalid challenge or mission selection.', ephemeral=True)
        return

    active_sessions.add(user_id)
    await interaction.response.send_message(
        f'Starting challenge: {challenge_data["display_name"]} — {mission_data["name"]}',
        ephemeral=True,
    )

    await interaction.followup.send(
        f'Väljakutse: {challenge_data["display_name"]}\n'
        f'Mine {mission_data["name"]} asukohaga ZIP {mission_data["zip"]}'
        f'{f", Building {mission_data["building"]}" if mission_data["building"] else ""}. '
        f'{mission_data["description"]}. Sul on 5 minutit aega, et kohale jõuda ja seal püsida.',
        ephemeral=True,
    )

    arrived, alert_triggered = await poll_for_arrival(username, mission_data, interaction, timeout_seconds=300)

    if not arrived:
        await interaction.followup.send('Ebaõnnestus: sa ei jõudnud sihtkohta 5 minuti jooksul.', ephemeral=True)
        active_sessions.discard(user_id)
        return

    if alert_triggered:
        await interaction.followup.send(
            'Hei boss siin. Keegi on politseisse helistanud ja teavitanud sinust. Tegutse kiiresti',
            ephemeral=True,
        )

    if mission_data.get('name') == 'Eddie ülevaatuspunkt':
        await interaction.followup.send(
            'Sa valmistad pommi järgmised 4 minutit.',
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            f'Sa jõudsid {mission_data["name"]}. Oota seal {format_wait_duration(mission_data["required_stay_sec"])}.',
            ephemeral=True,
        )

    stayed = await ensure_player_stays(
        user_id,
        username,
        mission_data,
        mission_data['required_stay_sec'],
        interaction,
        check_interval=2.0,
    )
    if not stayed:
        await interaction.followup.send(
            'Sa lahkusid piirkonnast enne nõutud aja möödumist. Väljakutse ebaõnnestus.',
            ephemeral=True,
        )
        active_sessions.discard(user_id)
        return

    try:
        await erlc_client.send_game_hint(username, ':h arrived')
    except Exception:
        pass

    await asyncio.sleep(10)

    # Completion notifications to public channels are disabled; keep the result private.
    success, boat_message = await award_boat_item(str(user_id), challenge_data['reward'])
    if success:
        success_message = f'Okei, tubli! Sa said vajaliku asja kätte. Tõmba nüüd kiiresti minema, et keegi ei märkaks.'
    else:
        success_message = (
            f'Õnnestus! {challenge_data["reward"]} valmis, kuid BOAT inventuuri uuendamine ebaõnnestus: {boat_message}'
        )

    await send_public_notification(interaction, success_message)
    await interaction.followup.send(success_message, ephemeral=True)
    active_sessions.discard(user_id)


@bot.command(name='heist', description='Start a heist and go to the location')
@app_commands.describe(
    heist='Heist location',
    username='Roblox username'
)
@app_commands.autocomplete(heist=heist_autocomplete)
async def heist(
    interaction: discord.Interaction,
    heist: str,
    username: str,
):
    await run_heist(interaction, heist, username)


@bot.command(name='location', description='Get the current Roblox player location')
@app_commands.describe(username='Roblox username')
async def location(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=True)

    player_data = await erlc_client.get_player_location(username)
    if not player_data or 'error' in player_data:
        error_text = player_data.get('error') if isinstance(player_data, dict) else 'unknown error'
        await interaction.followup.send(
            f'Ei õnnestunud saada asukohta mängijale {username}: {error_text}',
            ephemeral=True,
        )
        return

    location_text = format_player_location(player_data)
    if location_text.startswith('API error:') or location_text.startswith('{'):
        await interaction.followup.send(
            f'Asukoht mängijale {username}:\n```json\n{format_player_location(player_data)}\n```',
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            f'{username} asukoht: {location_text}',
            ephemeral=True,
        )


@bot.command(name='müü', description='Show the punker sell location and open the Deemand sell popup when inside')
@app_commands.describe(username='Roblox username to verify your location')
async def müü(
    interaction: discord.Interaction,
    username: str | None = None,
):
    await interaction.response.defer(ephemeral=True)

    location_message = (
        'Pärnus tegutseb tundmatu müügimees.\n'
        f'Jutud käivad, et tema müügikoht asub {DEEMAND_SELL_LOCATION["label"]} ({DEEMAND_SELL_LOCATION["zip"]})\n'
        f'Lisainfo: {DEEMAND_SELL_LOCATION["hint"]}'
    )

    if not username:
        await interaction.followup.send(location_message, ephemeral=True)
        return

    await interaction.followup.send(
        f'{location_message}\nSul on 5 minutit, et sinna jõuda.',
        ephemeral=True,
    )

    arrived = await poll_for_coordinate_arrival(
        username,
        DEEMAND_SELL_LOCATION['x'],
        DEEMAND_SELL_LOCATION['z'],
        DEEMAND_SELL_LOCATION['tolerance'],
        interaction,
        timeout_seconds=300,
    )

    if not arrived:
        await interaction.followup.send(
            'Sa ei jõudnud punkrisse 5 minuti jooksul, müügimees läks enne koju ära.',
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        'Oled punkris. Kui oled valmis, vali deemand mida sa müüa tahad ja sisesta kogus.',
        view=SellDeemandView(interaction.user.id),
        ephemeral=True,
    )


@bot.command(name='rahapesu', description='Convert must raha to discord money at the abandoned laundry')
@app_commands.describe(username='Roblox username to verify your location')
async def rahapesu(
    interaction: discord.Interaction,
    username: str | None = None,
):
    await interaction.response.defer(ephemeral=True)

    location_message = (
        'Pärnus tegutseb tundmatu müügimees.\n'
        'Jutud käivad, et tema müügikoht asub 301 läheduses.\n'
        f'Lisainfo: Mine lähedale koordinaatidele {LAUNDROMAT_LOCATION["x"]}, {LAUNDROMAT_LOCATION["z"]} (mitte täpselt, vaid ümberringi).'
    )

    if interaction.user.id in active_laundering_sessions:
        await interaction.followup.send(
            'Sul on juba aktiivne rahapesu. Oota, kuni see lõpeb enne uue käivitamist.',
            ephemeral=True,
        )
        return

    if not username:
        await interaction.followup.send(location_message, ephemeral=True)
        return

    try:
        await interaction.followup.send(
            'Hmmm... Sul on raha must?\n'
            'Ma tean ühte kohta.\n'
            f'Mine 301 lähedusse.\n'
            f'Asukoht: {LAUNDROMAT_LOCATION["x"]}, {LAUNDROMAT_LOCATION["z"]}.\n'
            'Sul on 5 minutit, et sinna jõuda.',
            ephemeral=True,
        )

        arrived = await poll_for_coordinate_arrival(
            username,
            LAUNDROMAT_LOCATION['x'],
            LAUNDROMAT_LOCATION['z'],
            LAUNDROMAT_LOCATION['tolerance'],
            interaction,
            timeout_seconds=300,
        )

        if not arrived:
            await interaction.followup.send(
                'Ebaõnnestunud: sa ei jõudnud 301 lähedusse 5 minuti jooksul.',
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            'Oled pesumajas. Vajuta nuppu "Pese raha", et valida summa ja alustada rahapesu.',
            view=LaunderingStartView(interaction.user.id, username),
            ephemeral=True,
        )
    except Exception as exc:
        await interaction.followup.send(f'Rahapesu käivitus ebaõnnestus: {exc}', ephemeral=True)


class LaunderingAmountModal(Modal):
    def __init__(self, user_id: int, username: str):
        super().__init__(title='Rahapesu')
        self.user_id = user_id
        self.username = username
        self.amount_input = TextInput(
            label='Kogus',
            placeholder='Sisesta summa 0-50000',
            style=discord.TextStyle.short,
            min_length=1,
            max_length=5,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('See valik pole sinu jaoks.', ephemeral=True)
            return

        try:
            amount = int(self.amount_input.value.strip())
        except ValueError:
            await interaction.response.send_message('Sisesta kehtiv number.', ephemeral=True)
            return

        if amount < 0 or amount > 50000:
            await interaction.response.send_message('Kogus peab olema 0 kuni 50000.', ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await process_laundering(interaction, amount, self.username)


class LaunderingStartView(View):
    def __init__(self, user_id: int, username: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.username = username

    @discord.ui.button(label='Pese raha', style=discord.ButtonStyle.primary, custom_id='laundering_start')
    async def laundering_start(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('See valik pole sinu jaoks.', ephemeral=True)
            return

        await interaction.response.send_modal(LaunderingAmountModal(self.user_id, self.username))


async def process_laundering(interaction: discord.Interaction, amount: int, username: str):
    if interaction.user.id in active_laundering_sessions:
        await interaction.followup.send(
            'Rahapesu on juba pooleli. Oota, kuni see lõpeb.',
            ephemeral=True,
        )
        return

    active_laundering_sessions.add(interaction.user.id)
    try:
        await interaction.followup.send(
            f'Rahapesu algab {amount} suuruse summaga. Oota 5 sekundit...',
            ephemeral=True,
        )

        alert_triggered = await check_laundering_alerts(interaction)
        # Ensure the player stays at the laundromat for the laundring duration (5s)
        stayed = await ensure_player_stays(interaction.user.id, username, LAUNDROMAT_LOCATION, 5, interaction)
        if not stayed:
            await interaction.followup.send('Rahapesu ebaõnnestus: sa lahkusid pesumaja piirkonnast.', ephemeral=True)
            return

        if amount <= 0:
            await interaction.followup.send('Rahapesu katkestati: sisestatud kogus oli 0.', ephemeral=True)
            return

        owned, error, qty = await get_boat_item_quantity(str(interaction.user.id), BLACK_MONEY_ITEM_NAME)
        if not owned:
            await interaction.followup.send(f'Inventuuri kontroll ebaõnnestus: {error}', ephemeral=True)
            return

        if qty < amount:
            await interaction.followup.send(
                f'Sul pole piisavalt mustraha. Vajad vähemalt {amount} mustraha, et seda rahapesu käivitada.',
                ephemeral=True,
            )
            return

        removed, remove_error = await remove_boat_item(str(interaction.user.id), BLACK_MONEY_ITEM_NAME, quantity=amount)
        if not removed:
            await interaction.followup.send(
                f'Mustraha eemaldamine ebaõnnestus: {remove_error}',
                ephemeral=True,
            )
            return

        if BOAT_API_ENABLED:
            # Credit washed amount into the user's BOAT bank balance and zero their cash.
            success, cash_message = await set_boat_user_balance(str(interaction.user.id), amount)
        else:
            # Fallback to in-game award (Roblox) when BOAT is not configured.
            success, cash_message = await award_in_game_cash(username, amount)
        if not success:
            await interaction.followup.send(
                f'Rahapesu õnnestus, kuid Discord-raha lisamine ebaõnnestus: {cash_message}',
                ephemeral=True,
            )
            return

        if alert_triggered:
            await interaction.followup.send(
                'Rahapesu lõppes, aga politsei sai teate. Ole ettevaatlik järgmisel korral.',
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f'Rahapesu õnnestus! Sa puhastasid {amount} mustraha ja said Discord-raha.',
                ephemeral=True,
            )
    finally:
        active_laundering_sessions.discard(interaction.user.id)


class SellDeemandQuantityModal(Modal):
    def __init__(self, user_id: int, item_key: str):
        super().__init__(title='Deemandite müük')
        self.user_id = user_id
        self.item_key = item_key
        self.quantity_input = TextInput(
            label='Kogus',
            placeholder='Sisesta müüdavate deemandite arv',
            style=discord.TextStyle.short,
            min_length=1,
            max_length=4,
        )
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('See modal ei ole sinu jaoks.', ephemeral=True)
            return

        try:
            quantity = int(self.quantity_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                'Palun sisesta kehtiv täisarv.',
                ephemeral=True,
            )
            return

        if quantity <= 0:
            await interaction.response.send_message(
                'Palun määra kogus suurem kui 0.',
                ephemeral=True,
            )
            return

        item_key = self.item_key
        owned, error, qty = await get_boat_item_quantity(str(self.user_id), item_key)
        if not owned:
            await interaction.response.send_message(
                f'Inventuuri kontroll ebaõnnestus: {error}',
                ephemeral=True,
            )
            return

        if qty < quantity:
            await interaction.response.send_message(
                f'Sul on ainult {qty}x {item_key}. Määratud kogus: {quantity}.',
                ephemeral=True,
            )
            return

        removed, remove_error = await remove_boat_item(str(self.user_id), item_key, quantity=quantity)
        if not removed:
            await interaction.response.send_message(
                f'{item_key} eemaldamine inventuuri ebaõnnestus: {remove_error}',
                ephemeral=True,
            )
            return

        total_cash = quantity * DEEMAND_SELL_PRICES[item_key]
        success, cash_message = await award_boat_cash(str(self.user_id), total_cash)
        if success:
            await interaction.response.send_message(
                (
                    f'Oled müünud {quantity}x {item_key} ja saanud {total_cash} mustraha. '
                    f'Müük toimus punkris: {DEEMAND_SELL_LOCATION["label"]}.'
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f'Müük õnnestus, kuid mustaraha lisamine ebaõnnestus: {cash_message}',
                ephemeral=True,
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(
            'Midagi läks valesti müügi modaliga.',
            ephemeral=True,
        )


class SellDeemandView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('See nupuvalik pole sinu jaoks.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Deemand Suur', style=discord.ButtonStyle.primary, custom_id='sell_deemand_suur')
    async def large_diamond(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SellDeemandQuantityModal(self.user_id, 'Deemand Suur'))

    @discord.ui.button(label='Deemand Väike', style=discord.ButtonStyle.secondary, custom_id='sell_deemand_vaike')
    async def small_diamond(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SellDeemandQuantityModal(self.user_id, 'Deemand Väike'))


@bot.command(name='hint', description='Send an in-game hint command')
@app_commands.describe(message='Hint text to send in game')
async def hint(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)

    hint_command = message if message.startswith(':h') else f':h {message}'
    try:
        result = await erlc_client.send_game_hint('', hint_command)
        if isinstance(result, dict) and result.get('error'):
            await interaction.followup.send(f'Vihje saatmine ebaõnnestus: {result["error"]}', ephemeral=True)
        else:
            await interaction.followup.send(f'Vihje saadetud: {hint_command}', ephemeral=True)
    except Exception as exc:
            await interaction.followup.send(f'Vihje saatmine ebaõnnestus: {exc}', ephemeral=True)


@bot.command(name='kill', description='Send an in-game kill command')
@app_commands.describe(target='Target player or kill parameter (optional)')
async def kill(interaction: discord.Interaction, target: str | None = None):
    await interaction.response.defer(ephemeral=True)

    kill_command = f':kill {target}' if target else ':kill'
    try:
        result = await erlc_client.send_game_hint('', kill_command)
        if isinstance(result, dict) and result.get('error'):
            await interaction.followup.send(f'Tapukäsk ebaõnnestus: {result["error"]}', ephemeral=True)
        else:
            await interaction.followup.send(f'Sent kill command: {kill_command}', ephemeral=True)
    except Exception as exc:
        await interaction.followup.send(f'Tapukäsk ebaõnnestus: {exc}', ephemeral=True)


@bot.command(name='kill1', description='Kill all players within the defined area')
async def kill1(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    player_locations = await erlc_client.get_all_player_locations()
    if isinstance(player_locations, dict) and player_locations.get('error'):
        await interaction.followup.send(
            f'Mängijate asukohtade päring ebaõnnestus: {player_locations["error"]}',
            ephemeral=True,
        )
        return

    if not isinstance(player_locations, list):
        await interaction.followup.send(
            'Unexpected response retrieving player locations.',
            ephemeral=True,
        )
        return

    targets = [player for player in player_locations if is_player_in_kill1_area(player)]
    if not targets:
        await interaction.followup.send(
            f'Piirkonnas {KILL1_AREA["label"]} ei leitud mingeid mängijaid.',
            ephemeral=True,
        )
        return

    killed = []
    failed = []
    for player in targets:
        username = player.get('username')
        if not username:
            continue

        kill_command = f':kill {username}'
        try:
            result = await erlc_client.send_game_hint('', kill_command)
            if isinstance(result, dict) and result.get('error'):
                failed.append(f'{username} ({result["error"]})')
            else:
                killed.append(username)
        except Exception as exc:
            failed.append(f'{username} ({exc})')

    response_lines = []
    if killed:
        response_lines.append(f'Tapetud mängijad: {", ".join(killed)}')
    if failed:
        response_lines.append(f'Tapmine ebaõnnestus: {", ".join(failed)}')

    await interaction.followup.send('\n'.join(response_lines), ephemeral=True)


@client.event
async def on_ready():
    print('on_ready fired:', 'config CLIENT_ID=', CLIENT_ID, 'client.application_id=', client.application_id, 'client.user.id=', client.user.id)

    if CLIENT_ID and str(CLIENT_ID) != str(client.application_id):
        print(f'WARNING: config clientId ({CLIENT_ID}) does not match token application id ({client.application_id}).')
    if GUILD_ID and CLIENT_ID and str(GUILD_ID) == str(CLIENT_ID):
        print('WARNING: guildId appears to be the same as clientId. Make sure guildId is your Discord server ID, not your application ID.')

    # Test both guild and global sync
    print('Attempting guild sync...')
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        try:
            synced = await bot.sync(guild=guild)
            print(f'Guild sync succeeded: {len(synced)} commands synced to guild {GUILD_ID}.')
            print(f'Synced command names: {[cmd.name for cmd in synced]}')
        except Exception as e:
            print(f'Guild sync failed: {type(e).__name__}: {e}')

    print('Attempting global sync...')
    try:
        synced = await bot.sync()
        print(f'Global sync succeeded: {len(synced)} global commands synced.')
        print(f'Synced command names: {[cmd.name for cmd in synced]}')
    except Exception as e:
        print(f'Global sync failed: {type(e).__name__}: {e}')

    print(f'Logged in as {client.user}.')

    print('Registered commands:', [command.name for command in bot.get_commands()])


def main():
    client.run(TOKEN)


if __name__ == '__main__':
    main()