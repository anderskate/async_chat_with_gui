import asyncio
import datetime
import logging
import gui
import argparse
import aiofiles
import json
from asyncio.queues import QueueEmpty
from tkinter import messagebox
from loguru import logger

from anyio import create_task_group, run
from async_timeout import timeout

from get_connection import get_connection


watchdog_logger = logging.getLogger(__file__)


class InvalidToken(Exception):
    """Called when user token is unknown."""
    pass


async def upload_old_msgs(filepath, queue):
    """Upload old messages in chat, stored in file."""
    async with aiofiles.open(filepath, mode='r') as f:
        old_msgs = []
        async for msg in f:
            formatted_msg = msg
            old_msgs.append(formatted_msg)

        for msg in old_msgs:
            queue.put_nowait(msg)


async def read_msgs(host, port, msg_queue,
                    save_msg_queue, status_queue, watchdog_queue):
    """Read messages from chat."""
    try:
        status_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)
        async with get_connection(host, port, timeout=40) as connection:
            reader, writer = connection

            status_queue.put_nowait(gui.ReadConnectionStateChanged.ESTABLISHED)

            while True:
                try:
                    async with timeout(3) as cm:
                        msg = await reader.readline()
                except asyncio.TimeoutError as e:
                    watchdog_queue.put_nowait(None)
                    continue
                formatted_msg = msg.decode()
                msg_queue.put_nowait(formatted_msg)

                watchdog_queue.put_nowait(
                    'Connection is alive. New message in chat'
                )
                save_msg_queue.put_nowait(formatted_msg)

                await asyncio.sleep(1)
                logger.debug(formatted_msg)
    finally:
        status_queue.put_nowait(gui.ReadConnectionStateChanged.CLOSED)


async def save_msgs(filepath, queue):
    """Save messages from chat to file."""
    while True:
        try:
            msg = queue.get_nowait()
        except QueueEmpty:
            msg = None

        if not msg:
            await asyncio.sleep(1)
        else:
            async with aiofiles.open(filepath, mode='a') as f:
                current_datetime = datetime.datetime.now()
                formatted_current_datetime = current_datetime.strftime(
                    "%d.%m.%y %H:%M"
                )
                log_msg = f'[{formatted_current_datetime}] {msg} \n'
                await f.write(log_msg)


async def authorise(reader, writer, account_hash):
    """Login to chat with user account hash.
    If account_hash is incorrect, it return an error,
    if correct, it return user credentials.
    """
    data = await reader.readline()
    logger.info(data)

    writer.write(f'{account_hash}\n'.encode())
    await writer.drain()

    credentials = await reader.readline()
    logger.info(credentials)

    if json.loads(credentials) is None:
        error_msg = 'Неизвестный токен. ' \
                    'Проверьте его или зарегистрируйте заново.'
        messagebox.showerror("Неверный токен", error_msg)
        raise InvalidToken(
            'Неизвестный токен. '
            'Проверьте его или зарегистрируйте заново.'
            )

    user_name = json.loads(credentials).get('nickname')
    logger.info(f'Выполнена авторизация. Пользователь "{user_name}"')

    return user_name


async def send_msgs(host, port, queue, status_queue,
                    watchdog_queue, account_hash):
    """Send messages to chat."""
    try:
        status_queue.put_nowait(gui.SendingConnectionStateChanged.INITIATED)
        async with get_connection(host, port, timeout=40) as connection:
            reader, writer = connection

            user_name = await authorise(reader, writer, account_hash)
            event = gui.NicknameReceived(user_name)
            status_queue.put_nowait(event)
            status_queue.put_nowait(
                gui.SendingConnectionStateChanged.ESTABLISHED
            )

            while True:
                try:
                    async with timeout(5) as cm:
                        msg = await queue.get()
                except asyncio.TimeoutError:
                    msg = ''

                logger.info(f'Пользователь написал: {msg}')

                formatted_message = msg.replace('\n', '')
                writer.write(f'{formatted_message}\n\n'.encode())
                await writer.drain()

                watchdog_queue.put_nowait('Connection is alive. Message sent')
    finally:
        status_queue.put_nowait(gui.SendingConnectionStateChanged.CLOSED)


async def watch_for_connection(watchdog_queue):
    """Investigate the state of the connection."""
    while True:
        try:
            msg = watchdog_queue.get_nowait()
            if not msg:
                raise ConnectionError
        except QueueEmpty:
            msg = None

        if msg:
            watchdog_logger.info(msg)

        await asyncio.sleep(1)


async def handle_connection(
        host, port_1, messages_queue, sending_queue,
        status_updates_queue, saving_msgs_queue, token):
    """Function to manage connections for reading, sending and analyze."""
    watchdog_queue = asyncio.Queue()
    while True:
        try:
            async with create_task_group() as tg:
                tg.start_soon(
                    read_msgs, host, port_1, messages_queue,
                    saving_msgs_queue, status_updates_queue, watchdog_queue
                )
                tg.start_soon(
                    send_msgs, host, 5050, sending_queue,
                    status_updates_queue, watchdog_queue, token
                )
                tg.start_soon(
                    watch_for_connection, watchdog_queue
                )
        except ConnectionError:
            tg.cancel_scope.cancel()


async def main():
    parser = argparse.ArgumentParser(
        description='Program for streaming and sending messages in chat'
    )
    parser.add_argument(
        '--host',
        help='Host to connect',
        default='minechat.dvmn.org'
    )
    parser.add_argument(
        '--port',
        help='Port to connect',
        type=int,
        default=5000
    )
    parser.add_argument(
        '--token',
        help='Authorization token',
    )
    parser.add_argument(
        '--history',
        help='The path to the file with the storage of messages',
        default='log.txt'
    )
    args = parser.parse_args()
    host = args.host
    port = args.port
    token = args.token
    history_path = args.history

    logging.basicConfig(
        format='[%(created).0f] %(message)s',
        level=logging.INFO
    )

    messages_queue = asyncio.Queue()
    saving_msgs_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()

    while True:
        async with create_task_group() as tg:
            tg.start_soon(upload_old_msgs, history_path, messages_queue)
            tg.start_soon(save_msgs, history_path, saving_msgs_queue)
            tg.start_soon(
                handle_connection, host, port,
                messages_queue, sending_queue, status_updates_queue,
                saving_msgs_queue, token
            )
            tg.start_soon(gui.draw, messages_queue,
                          sending_queue, status_updates_queue)


if __name__ == '__main__':
    try:
        run(main)
    except KeyboardInterrupt:
        pass
    except gui.TkAppClosed:
        pass
