from dataclasses import asdict, dataclass
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import User

from .config import ensure_data_dir
from .storage import load_json, save_json


@dataclass
class ParsedUser:
    user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    access_hash: int | None
    source_chat: str

    @property
    def display_name(self) -> str:
        parts = [self.first_name or "", self.last_name or ""]
        name = " ".join(p for p in parts if p).strip()
        if self.username:
            return f"{name} (@{self.username})" if name else f"@{self.username}"
        return name or str(self.user_id)


def _user_key(user: ParsedUser) -> str:
    return str(user.user_id)


async def parse_chat_members(
    client: TelegramClient,
    source_chat: str,
    *,
    limit: int | None = None,
) -> list[ParsedUser]:
    entity = await client.get_entity(source_chat)
    members: list[ParsedUser] = []

    async for user in client.iter_participants(entity, limit=limit):
        if not isinstance(user, User):
            continue
        if user.bot or user.deleted:
            continue

        members.append(
            ParsedUser(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                access_hash=user.access_hash,
                source_chat=source_chat,
            )
        )

    return members


async def parse_multiple_chats(
    client: TelegramClient,
    source_chats: list[str],
    *,
    limit_per_chat: int | None = None,
) -> list[ParsedUser]:
    seen: set[str] = set()
    result: list[ParsedUser] = []

    for chat in source_chats:
        members = await parse_chat_members(client, chat, limit=limit_per_chat)
        for member in members:
            key = _user_key(member)
            if key in seen:
                continue
            seen.add(key)
            result.append(member)

    return result


def save_parsed_users(users: list[ParsedUser], filename: str = "parsed_users.json") -> Path:
    path = ensure_data_dir() / filename
    save_json(path, [asdict(u) for u in users])
    return path


def load_parsed_users(filename: str = "parsed_users.json") -> list[ParsedUser]:
    path = ensure_data_dir() / filename
    raw = load_json(path, [])
    return [ParsedUser(**item) for item in raw]
