import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def parse_admin_ids(value: str) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        text = part.strip()
        if text and text.lstrip("-").isdigit():
            result.add(int(text))
    return result


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_chat_id: int
    admin_ids: set[int]
    gos_spreadsheet_id: str
    mvd_spreadsheet_id: str
    google_credentials_file: Path
    data_dir: Path
    database_path: Path


data_dir = Path(os.getenv("DATA_DIR", "./data"))
data_dir.mkdir(parents=True, exist_ok=True)

settings = Settings(
    bot_token=os.getenv("BOT_TOKEN", "").strip(),
    admin_chat_id=int(os.getenv("ADMIN_CHAT_ID", "0") or "0"),
    admin_ids=parse_admin_ids(os.getenv("ADMIN_IDS", "")),
    gos_spreadsheet_id=os.getenv("GOS_SPREADSHEET_ID", "").strip(),
    mvd_spreadsheet_id=os.getenv("MVD_SPREADSHEET_ID", "").strip(),
    google_credentials_file=Path(os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")),
    data_dir=data_dir,
    database_path=Path(os.getenv("DB_PATH", str(data_dir / "uslugigoss.db"))),
)


def validate_settings() -> None:
    if not settings.bot_token:
        raise RuntimeError("Не указан BOT_TOKEN")
    if not settings.admin_chat_id:
        raise RuntimeError("Не указан ADMIN_CHAT_ID")
    if not settings.admin_ids:
        raise RuntimeError("Не указаны ADMIN_IDS")
    if not settings.gos_spreadsheet_id:
        raise RuntimeError("Не указан GOS_SPREADSHEET_ID")
    if not settings.mvd_spreadsheet_id:
        raise RuntimeError("Не указан MVD_SPREADSHEET_ID")
    if not settings.google_credentials_file.exists():
        raise RuntimeError(f"Не найден Google-ключ: {settings.google_credentials_file}")
