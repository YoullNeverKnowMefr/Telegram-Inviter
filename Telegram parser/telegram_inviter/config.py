import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SESSION_PATH = BASE_DIR / "session"


@dataclass
class Settings:
    api_id: int
    api_hash: str
    phone: str
    invite_delay: float
    batch_size: int

    @classmethod
    def from_env(cls) -> "Settings":
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        phone = os.getenv("PHONE")

        if not api_id or not api_hash or not phone:
            raise ValueError(
                "Заполните API_ID, API_HASH и PHONE в .env (см. .env.example)"
            )

        return cls(
            api_id=int(api_id),
            api_hash=api_hash,
            phone=phone,
            invite_delay=float(os.getenv("INVITE_DELAY", "3")),
            batch_size=int(os.getenv("BATCH_SIZE", "1")),
        )


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    return DATA_DIR
