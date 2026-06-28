import aiohttp
import json
from urllib.parse import urlparse

class ERLCClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.use_erlc_dev = 'erlc.dev' in self.base_url

    def _api_base(self) -> str:
        if self.use_erlc_dev:
            parsed = urlparse(self.base_url)
            # Only use the erlc.dev host and ignore extra webhook-style segments.
            return f'{parsed.scheme}://{parsed.netloc}/api'
        return self.base_url.rstrip('/')

    async def get_player_location(self, username: str) -> dict:
        if self.use_erlc_dev:
            return {
                'error': 'erlc.dev cannot provide live in-game player location. Use https://api.erlc.gg with a raw ER:LC server key.'
            }

        url = f"{self._api_base()}/v2/server"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'server-key': self.api_key
        }
        params = {'Players': 'true'}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params, headers=headers, timeout=10) as response:
                    text = await response.text()
                    if response.status >= 400:
                        try:
                            payload = json.loads(text)
                            error_msg = payload.get('error') or payload.get('message') or f'HTTP {response.status}'
                        except json.JSONDecodeError:
                            error_msg = text.strip() or f'HTTP {response.status}'
                        return {'error': error_msg}

                    if not text:
                        return {'error': f'Empty response from ERLC API (status {response.status})'}

                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        return {'error': f'Invalid JSON response from ERLC API: {text[:200]}' }

                    if not isinstance(payload, dict):
                        return {'error': f'Unexpected ERLC API response shape: {type(payload).__name__}'}

                    players = payload.get('Players', [])
                    for player in players:
                        player_field = player.get('Player', '')
                        player_name, _, player_id = player_field.partition(':')
                        if player_name.lower() == username.lower():
                            return {
                                'username': player_name,
                                'id': player_id or None,
                                'location': player.get('Location', {})
                            }

                    return {'error': 'Player not found or not in game.'}
            except aiohttp.ClientError as exc:
                return {'error': str(exc)}

    async def get_all_player_locations(self) -> list[dict] | dict:
        if self.use_erlc_dev:
            return {'error': 'erlc.dev cannot provide live in-game player location. Use https://api.erlc.gg with a raw ER:LC server key.'}

        url = f"{self._api_base()}/v2/server"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'server-key': self.api_key
        }
        params = {'Players': 'true'}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params, headers=headers, timeout=10) as response:
                    text = await response.text()
                    if response.status >= 400:
                        try:
                            payload = json.loads(text)
                            error_msg = payload.get('error') or payload.get('message') or f'HTTP {response.status}'
                        except json.JSONDecodeError:
                            error_msg = text.strip() or f'HTTP {response.status}'
                        return {'error': error_msg}

                    if not text:
                        return {'error': f'Empty response from ERLC API (status {response.status})'}

                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        return {'error': f'Invalid JSON response from ERLC API: {text[:200]}' }

                    if not isinstance(payload, dict):
                        return {'error': f'Unexpected ERLC API response shape: {type(payload).__name__}'}

                    players = payload.get('Players', [])
                    results = []
                    for player in players:
                        player_field = player.get('Player', '')
                        player_name, _, player_id = player_field.partition(':')
                        results.append({
                            'username': player_name,
                            'id': player_id or None,
                            'location': player.get('Location', {})
                        })
                    return results
            except aiohttp.ClientError as exc:
                return {'error': str(exc)}

    async def send_game_hint(self, username: str, hint: str) -> dict:
        if self.use_erlc_dev:
            return {'error': 'Game hint is not supported for erlc.dev API mode.'}

        url = f"{self._api_base().rstrip('/')}/v1/server/command"
        headers = {
            'server-key': self.api_key,
            'Content-Type': 'application/json'
        }
        # Include multiple keys to be compatible with both the real ERLC
        # command endpoint (which expects `command`) and the mock server
        # used for local testing (which expects `username` and `hint`).
        payload = {
            'command': hint,
            'username': username,
            'hint': hint,
        }

        # TEMP DEBUG: log payload so we can see what is sent to the server
        try:
            print(f'[DEBUG] send_game_hint payload -> url={url} headers={headers} payload={payload}')
        except Exception:
            pass

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                    text = await response.text()
                    # TEMP DEBUG: log primary endpoint response
                    try:
                        print(f'[DEBUG] send_game_hint primary response -> status={response.status} text={text}')
                    except Exception:
                        pass
                    if response.status >= 400:
                        # On failure, try the mock server endpoint as a fallback (/send-hint).
                        try:
                            data = json.loads(text)
                            main_error = data.get('error') or data.get('message') or f'HTTP {response.status}'
                        except json.JSONDecodeError:
                            main_error = text.strip() or f'HTTP {response.status}'

                        # If the main endpoint failed or didn't accept the payload, try the simpler mock endpoint.
                        fallback_url = f"{self._api_base().rstrip('/')}/send-hint"
                        try:
                            async with session.post(fallback_url, json={'username': username, 'hint': hint}, timeout=10) as fb_resp:
                                fb_text = await fb_resp.text()
                                # TEMP DEBUG: log fallback endpoint response
                                try:
                                    print(f'[DEBUG] send_game_hint fallback response -> url={fallback_url} status={fb_resp.status} text={fb_text}')
                                except Exception:
                                    pass
                                if fb_resp.status >= 400:
                                    try:
                                        fb_data = json.loads(fb_text)
                                        return {'error': main_error, 'status': response.status, 'body': data if 'data' in locals() else text, 'fallback_status': fb_resp.status, 'fallback_body': fb_data}
                                    except json.JSONDecodeError:
                                        return {'error': main_error, 'status': response.status, 'body': data if 'data' in locals() else text, 'fallback_status': fb_resp.status, 'fallback_body_text': fb_text}

                                try:
                                    return json.loads(fb_text)
                                except json.JSONDecodeError:
                                    return {'error': f'Unexpected fallback response', 'fallback_body_text': fb_text}
                        except aiohttp.ClientError:
                            return {'error': main_error, 'status': response.status}

                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {'error': f'Invalid JSON response from ERLC API command endpoint: {text[:200]}', 'body_text': text}
            except aiohttp.ClientError as exc:
                # If the primary request failed at network level, attempt mock endpoint as last resort.
                fallback_url = f"{self._api_base().rstrip('/')}/send-hint"
                try:
                    async with session.post(fallback_url, json={'username': username, 'hint': hint}, timeout=10) as fb_resp:
                        fb_text = await fb_resp.text()
                        try:
                            print(f'[DEBUG] send_game_hint primary network error -> {exc}; fallback url={fallback_url} response_status={fb_resp.status} response_text={fb_text}')
                        except Exception:
                            pass
                        if fb_resp.status >= 400:
                            try:
                                fb_data = json.loads(fb_text)
                                return {'error': str(exc), 'fallback_status': fb_resp.status, 'fallback_body': fb_data}
                            except json.JSONDecodeError:
                                return {'error': str(exc), 'fallback_status': fb_resp.status, 'fallback_body_text': fb_text}

                        try:
                            return json.loads(fb_text)
                        except json.JSONDecodeError:
                            return {'error': f'Unexpected fallback response', 'fallback_body_text': fb_text}
                except Exception:
                    return {'error': str(exc)}
