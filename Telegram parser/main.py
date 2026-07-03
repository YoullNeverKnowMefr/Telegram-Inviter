import argparse
import asyncio
import sys

from telethon import TelegramClient

from telegram_inviter.config import SESSION_PATH, Settings, ensure_data_dir
from telegram_inviter.inviter import invite_users
from telegram_inviter.parser import (
    load_parsed_users,
    parse_multiple_chats,
    save_parsed_users,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Парсер участников чатов и инвайт в Telegram-канал"
    )
    sub = p.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Собрать участников из чатов")
    parse_cmd.add_argument(
        "sources",
        nargs="+",
        help="Юзернеймы или ссылки на чаты (@chat, t.me/chat)",
    )
    parse_cmd.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Лимит участников на каждый чат",
    )
    parse_cmd.add_argument(
        "--output",
        default="parsed_users.json",
        help="Имя файла в папке data/",
    )

    invite_cmd = sub.add_parser("invite", help="Пригласить пользователей в канал")
    invite_cmd.add_argument(
        "channel",
        help="Канал назначения (@channel или t.me/channel)",
    )
    invite_cmd.add_argument(
        "--input",
        default="parsed_users.json",
        help="Файл со списком пользователей из data/",
    )
    invite_cmd.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Не проверять текущих участников канала",
    )

    run_cmd = sub.add_parser("run", help="Парсинг + инвайт за один запуск")
    run_cmd.add_argument("channel", help="Канал назначения")
    run_cmd.add_argument("sources", nargs="+", help="Исходные чаты")
    run_cmd.add_argument("--limit", type=int, default=None)

    return p


async def with_client(coro):
    settings = Settings.from_env()
    ensure_data_dir()

    client = TelegramClient(str(SESSION_PATH), settings.api_id, settings.api_hash)
    await client.start(phone=settings.phone)

    try:
        return await coro(client, settings)
    finally:
        await client.disconnect()


async def cmd_parse(client: TelegramClient, settings: Settings, args) -> None:
    print(f"Парсинг {len(args.sources)} чат(ов)...")
    users = await parse_multiple_chats(client, args.sources, limit_per_chat=args.limit)
    path = save_parsed_users(users, args.output)
    print(f"Сохранено {len(users)} уникальных пользователей -> {path}")


async def cmd_invite(client: TelegramClient, settings: Settings, args) -> None:
    users = load_parsed_users(args.input)
    if not users:
        print("Список пользователей пуст. Сначала выполните parse.")
        return

    print(f"Инвайт {len(users)} пользователей в {args.channel}...")
    stats = await invite_users(
        client,
        settings,
        args.channel,
        users,
        skip_existing=not args.no_skip_existing,
    )

    print("\n--- Результат ---")
    print(f"Приглашено:           {stats.invited}")
    print(f"Уже в канале:         {stats.already_in}")
    print(f"Пропущено (ранее):    {stats.skipped}")
    print(f"Приватность:          {stats.privacy_restricted}")
    print(f"Не взаимный контакт:  {stats.not_mutual}")
    print(f"Лимит каналов:        {stats.channels_full}")
    print(f"Flood wait:           {stats.flood_waits}")
    print(f"Ошибки:               {stats.failed}")


async def cmd_run(client: TelegramClient, settings: Settings, args) -> None:
    await cmd_parse(client, settings, args)
    users = load_parsed_users()
    stats = await invite_users(client, settings, args.channel, users)
    print(f"\nГотово. Приглашено: {stats.invited}")


def main() -> None:
    args = build_parser().parse_args()

    try:
        if args.command == "parse":
            asyncio.run(with_client(lambda c, s: cmd_parse(c, s, args)))
        elif args.command == "invite":
            asyncio.run(with_client(lambda c, s: cmd_invite(c, s, args)))
        elif args.command == "run":
            asyncio.run(with_client(lambda c, s: cmd_run(c, s, args)))
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nОстановлено пользователем.")
        sys.exit(130)


if __name__ == "__main__":
    main()
