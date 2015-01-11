import asyncio
import logging

import quassel

l = logging.getLogger()
l.setLevel(logging.DEBUG)
l.addHandler(logging.StreamHandler())

loop = asyncio.get_event_loop()
connect = loop.create_connection(lambda: quassel.QuasselClientProtocol(loop, 'python', 'abcd'), '127.0.0.1', 4242)
loop.run_until_complete(connect)
loop.run_forever()
loop.close()