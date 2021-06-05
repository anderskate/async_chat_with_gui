import asyncio
from asyncio.queues import QueueEmpty
from tkinter import messagebox
import gui
import argparse
import aiofiles
import json

from get_connection import get_connection

from time import time
import datetime


class InvalidToken(Exception):
    """Called when user token is unknown."""
    pass


async def generate_msgs(queue):
    while True:
        time_now = time()
        msg = f'Ping {time_now}'
        queue.put_nowait(msg)

        await asyncio.sleep(1)


async def upload_old_msgs(filepath, queue):
    async with aiofiles.open(filepath, mode='r') as f:
        old_msgs = []
        async for msg in f:
            formatted_msg = msg
            old_msgs.append(formatted_msg)

        for msg in old_msgs:
            queue.put_nowait(msg)


async def read_msgs(host, port, msg_queue, save_msg_queue):
    async with get_connection(host, port, timeout=40) as connection:
        reader, writer = connection
        # await save_data_to_log_file('Установлено соединение', history_path)

        while True:
            msg = await reader.readline()
            formatted_msg = msg.decode()
            msg_queue.put_nowait(formatted_msg)
            save_msg_queue.put_nowait(formatted_msg)

            await asyncio.sleep(1)
            # logger.debug(data.decode())


async def save_msgs(filepath, queue):
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
    # logger.info(data)

    writer.write(f'{account_hash}\n'.encode())
    await writer.drain()

    credentials = await reader.readline()
    # logger.info(credentials)

    if json.loads(credentials) is None:
        error_msg = 'Неизвестный токен. ' \
                    'Проверьте его или зарегистрируйте заново.'
        messagebox.showerror("Неверный токен", error_msg)
        raise InvalidToken(
            'Неизвестный токен. '
            'Проверьте его или зарегистрируйте заново.'
            )

    user_name = json.loads(credentials).get('nickname')
    print(f'Выполнена авторизация. Пользователь "{user_name}"')

    # return credentials


async def send_msgs(host, port, queue):
    async with get_connection(host, port, timeout=40) as connection:
        reader, writer = connection
        await authorise(reader, writer, '')

        while True:
            msg = await queue.get()
            print(f'Пользователь написал: {msg}')

            formatted_message = msg.replace('\n', '')
            writer.write(f'{formatted_message}\n\n'.encode())
            await writer.drain()


async def main():
    # loop = asyncio.get_event_loop()

    # {"nickname": "Cool anderskate",
    # "account_hash": ""}

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
        default=None
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

    messages_queue = asyncio.Queue()
    saving_msgs_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()

    # messages_queue.put_nowait('Иван: Привет всем в этом чатике!')
    # messages_queue.put_nowait('Иван: Как дела?')

    await asyncio.gather(
        upload_old_msgs(history_path, messages_queue),
        read_msgs(host, port, messages_queue, saving_msgs_queue),
        save_msgs(history_path, saving_msgs_queue),
        send_msgs(host, 5050, sending_queue),
        gui.draw(messages_queue, sending_queue, status_updates_queue)
    )

    # loop.run_until_complete()


if __name__ == '__main__':
    asyncio.run(main())
