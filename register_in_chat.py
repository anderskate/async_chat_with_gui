import tkinter
from get_connection import get_connection
import asyncio
import json
import argparse


async def register_user(host, port, entry_field, draw_obj):
    """Register a new user in the chat and save account hash in txt file.

    After user registration, closes the drawing object.
    """

    async with get_connection(host, port) as connection:
        reader, writer = connection
        nickname = entry_field.get()

        await reader.readline()

        writer.write('\n'.encode())
        await writer.drain()

        await reader.readline()

        formatted_nickname = nickname.replace('\n', '')
        writer.write(f'{formatted_nickname}\n'.encode())
        await writer.drain()

        data = await reader.readline()
        user_credentials = json.loads(data)
        account_hash = user_credentials.get('account_hash')

        writer.close()
        await writer.wait_closed()

        with open('user_token.txt', 'w') as f:
            f.write(account_hash)

        draw_obj.destroy()


def draw_register_block(host, port):
    """Draw register block for user."""
    root = tkinter.Tk()

    root.title('Регистрация в чате')

    lbl = tkinter.Label(text='Введите имя')
    ent = tkinter.Entry(width=40)
    but = tkinter.Button(text="Зарегистрироваться")

    but.bind("<Return>", lambda event: asyncio.run(
        register_user(host, port, ent, root))
    )

    lbl.pack()
    ent.pack()

    but["command"] = lambda: asyncio.run(
        register_user(host, port, ent, root)
    )
    but.pack()

    root.mainloop()


def main():
    parser = argparse.ArgumentParser(
        description='Script for register user in chat.'
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
        default=5050
    )
    args = parser.parse_args()
    host = args.host
    port = args.port

    draw_register_block(host, port)


if __name__ == '__main__':
    main()
