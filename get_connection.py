from contextlib import asynccontextmanager
import asyncio
import socket
from loguru import logger


async def try_to_connect_chat(host, port):
    """Try to connect to the chat.
    If the connection was successful,
    return the reader and writer objects of the connection.
    """
    try:
        reader, writer = await asyncio.open_connection(
            host,
            port,
        )
        return reader, writer
    except socket.gaierror:
        return None


@asynccontextmanager
async def get_connection(host, port, timeout=30):
    """Get reader and writer objects.
    At the end of the work, be sure to close
    the writer object connection.
    By default, the timeout is set to 0 seconds
    so that the first reconnection attempt is fast.
    Then the value is taken from the specified in the arguments.
    """
    default_timeout = 0

    while True:
        connection = await try_to_connect_chat(host, port)
        if connection:
            reader, writer = connection
            break
        logger.warning(
            f'No chat connection. Reconnect after {default_timeout} seconds.'
        )
        await asyncio.sleep(default_timeout)
        default_timeout += timeout

    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()
