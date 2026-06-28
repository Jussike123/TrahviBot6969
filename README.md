# Discord ERLC Bot

Simple Discord bot for starting a Roblox location challenge and polling the ERLC API for player arrival.

## Features

- Start a location challenge with a slash command
- Poll the ERLC API for current player location data
- Notify a configured Discord user when the player arrives
- Support the mock ERLC server for local testing

## Setup

1. Copy `config.example.json` to `config.json`.
2. Fill in your Discord and ERLC values in `config.json`.
3. Keep your real secrets in your local `config.json`; it is ignored by Git and safe for private use while uploading the repository publicly.
4. Use `http://127.0.0.1:8080` for `erlcApiBaseUrl` while testing with the mock server.
5. For live player location lookup, do not use `erlc.dev`.
   - `erlcApiBaseUrl` should be `https://api.erlc.gg`.
   - `erlcApiKey` should be your ER:LC server key, sent in the `server-key` header.
   - `erlc.dev` is only for server dashboard/event access and does not provide the live /location API.
6. Install dependencies with `pip install -r requirements.txt`.
7. Start the mock API server with `python mock_erlc_server.py`.
8. Start the bot with `python bot.py`.

## Commands

- `/start username:<roblox username>`
- `/location username:<roblox username>`
- `/kill target:<player>`
- `/kill1`

## Mock API usage

While the mock server is running, set a player location with:

```powershell
python mock_erlc_server.py --host 127.0.0.1 --port 8080
```

Then, from another terminal:

```powershell
curl "http://127.0.0.1:8080/set-location?username=testuser&zipCode=205"
```

For the hint endpoint:

```powershell
curl -X POST "http://127.0.0.1:8080/send-hint" -H "Content-Type: application/json" -d "{\"username\":\"testuser\",\"hint\":\"START\"}"
```
