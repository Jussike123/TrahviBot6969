import argparse

from aiohttp import web

STORE = {}

async def player_location(request: web.Request) -> web.Response:
    username = request.query.get('username')
    if not username:
        return web.json_response({'error': 'username required'}, status=400)

    player_data = STORE.get(username.lower(), {'zipCode': '000'})
    return web.json_response(player_data)


async def set_location(request: web.Request) -> web.Response:
    username = request.query.get('username')
    zip_code = request.query.get('zipCode') or request.query.get('zip_code')
    place_name = request.query.get('placeName') or request.query.get('place')
    latitude = request.query.get('latitude')
    longitude = request.query.get('longitude')

    if not username or not zip_code:
        return web.json_response(
            {'error': 'username and zipCode are required'},
            status=400,
        )

    player_record = {'zipCode': str(zip_code)}
    if place_name:
        player_record['placeName'] = place_name
    if latitude is not None and longitude is not None:
        player_record['latitude'] = latitude
        player_record['longitude'] = longitude

    STORE[username.lower()] = player_record
    response_data = {'username': username, **player_record}
    return web.json_response(response_data)


async def reset_location(request: web.Request) -> web.Response:
    STORE.clear()
    return web.json_response({'status': 'reset'})


async def send_hint(request: web.Request) -> web.Response:
    data = await request.json()
    username = data.get('username')
    hint = data.get('hint')

    if not username or not hint:
        return web.json_response(
            {'error': 'username and hint are required'},
            status=400,
        )

    STORE.setdefault(username.lower(), {})['lastHint'] = hint
    return web.json_response({'username': username, 'hint': hint})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get('/player-location', player_location)
    app.router.add_get('/set-location', set_location)
    app.router.add_get('/reset', reset_location)
    app.router.add_post('/send-hint', send_hint)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description='Mock ERLC API server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind')
    args = parser.parse_args()

    app = create_app()
    web.run_app(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
