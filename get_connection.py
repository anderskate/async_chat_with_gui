from contextlib import asynccontextmanager
import asyncio
import socket
import logging


logger = logging.getLogger(__file__)


def chat_is_available(host, port):
    """Check the chat connection for the given host and port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
        # Shutdown both halves of the connection
        s.shutdown(2)
        return True
    except socket.gaierror:
        return False


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

    while not chat_is_available(host, port):
        logger.warning(
            f'No chat connection. Reconnect after {default_timeout} seconds.'
            )
        await asyncio.sleep(default_timeout)
        default_timeout = timeout

    reader, writer = await asyncio.open_connection(
            host,
            port,
        )

    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()
