async def app(scope, receive, send):
    assert scope['type'] == 'http'

    body = f'Received {scope["method"]} request to {scope["path"]}'.encode('utf-8')

    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
            [b'server', b'Server'],
            [b'Content-Length', str(len(body)).encode()],
        ]
    })
    await send({
        'type': 'http.response.body',
        'body': body,
    })
