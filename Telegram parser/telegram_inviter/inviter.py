import asyncio
from dataclasses import dataclass

from telethon import TelegramClient
from telethon.errors import (
    ChatAdminRequiredError,
    FloodWaitError,
    PeerFloodError,
    UserAlreadyParticipantError,
    UserChannelsTooMuchError,
    UserNotMutualContactError,
    UserPrivacyRestrictedError,
)
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import InputPeerUser

from .config import Settings, ensure_data_dir
from .parser import ParsedUser
from .storage import load_json, save_json


@dataclass
class InviteStats:
    invited: int = 0
    skipped: int = 0
    failed: int = 0
    already_in: int = 0
    privacy_restricted: int = 0
    not_mutual: int = 0
    channels_full: int = 0
    flood_waits: int = 0


def load_invited_ids() -> set[int]:
    data = load_json(ensure_data_dir() / "invite_progress.json", {"invited_ids": []})
    return set(data.get("invited_ids", []))


def save_invited_ids(invited_ids: set[int]) -> None:
    save_json(ensure_data_dir() / "invite_progress.json", {"invited_ids": sorted(invited_ids)})


async def get_channel_member_ids(client: TelegramClient, channel: str) -> set[int]:
    entity = await client.get_entity(channel)
    ids: set[int] = set()
    async for user in client.iter_participants(entity):
        ids.add(user.id)
    return ids


async def invite_user(
    client: TelegramClient,
    channel_entity,
    user: ParsedUser,
) -> str:
    if user.access_hash is None:
        return "failed"

    input_user = InputPeerUser(user_id=user.user_id, access_hash=user.access_hash)

    try:
        await client(InviteToChannelRequest(channel_entity, [input_user]))
        return "invited"
    except UserAlreadyParticipantError:
        return "already_in"
    except UserPrivacyRestrictedError:
        return "privacy_restricted"
    except UserNotMutualContactError:
        return "not_mutual"
    except UserChannelsTooMuchError:
        return "channels_full"
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 1)
        return "flood_wait"
    except (ChatAdminRequiredError, PeerFloodError):
        raise


async def invite_users(
    client: TelegramClient,
    settings: Settings,
    channel: str,
    users: list[ParsedUser],
    *,
    skip_existing: bool = True,
) -> InviteStats:
    channel_entity = await client.get_entity(channel)
    stats = InviteStats()
    invited_ids = load_invited_ids()

    existing_ids: set[int] = set()
    if skip_existing:
        existing_ids = await get_channel_member_ids(client, channel)

    for user in users:
        if user.user_id in invited_ids:
            stats.skipped += 1
            continue
        if user.user_id in existing_ids:
            stats.already_in += 1
            invited_ids.add(user.user_id)
            continue

        try:
            result = await invite_user(client, channel_entity, user)
        except (ChatAdminRequiredError, PeerFloodError) as e:
            print(f"\nКритическая ошибка: {e}")
            break

        if result == "invited":
            stats.invited += 1
            invited_ids.add(user.user_id)
            print(f"  + {user.display_name}")
        elif result == "already_in":
            stats.already_in += 1
            invited_ids.add(user.user_id)
        elif result == "privacy_restricted":
            stats.privacy_restricted += 1
            stats.failed += 1
        elif result == "not_mutual":
            stats.not_mutual += 1
            stats.failed += 1
        elif result == "channels_full":
            stats.channels_full += 1
            stats.failed += 1
        elif result == "flood_wait":
            stats.flood_waits += 1
            try:
                result = await invite_user(client, channel_entity, user)
                if result == "invited":
                    stats.invited += 1
                    invited_ids.add(user.user_id)
                    print(f"  + {user.display_name} (после flood wait)")
                else:
                    stats.failed += 1
            except Exception:
                stats.failed += 1
        else:
            stats.failed += 1

        save_invited_ids(invited_ids)
        await asyncio.sleep(settings.invite_delay)

    return stats
