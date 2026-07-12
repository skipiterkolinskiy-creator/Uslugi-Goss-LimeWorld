import json
import sqlite3
from datetime import datetime
from typing import Any

from config import settings
from services.google_sheets import google_sheets_service


class RequestsService:
    def create_local(self, request_type: str, user_id: int, payload: dict[str, Any]) -> int:
        text = json.dumps(payload, ensure_ascii=False)
        with sqlite3.connect(settings.database_path) as conn:
            cursor = conn.execute(
                "INSERT INTO pending_requests(request_type, user_id, payload_json) VALUES (?, ?, ?)",
                (request_type, user_id, text),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_local(self, request_id: int) -> dict[str, Any] | None:
        with sqlite3.connect(settings.database_path) as conn:
            row = conn.execute(
                "SELECT request_type, user_id, payload_json, status FROM pending_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row[2])
        except json.JSONDecodeError:
            payload = {}
        return {"type": row[0], "user_id": row[1], "payload": payload, "status": row[3]}

    def mark(self, request_id: int, status: str) -> None:
        with sqlite3.connect(settings.database_path) as conn:
            conn.execute("UPDATE pending_requests SET status=? WHERE request_id=?", (status, request_id))
            conn.commit()

    async def append_sheet(self, request_id: int, request_type: str, user_id: int, username: str, passport: str, fio: str, payload: dict[str, Any]) -> None:
        worksheet = google_sheets_service.worksheet("Заявки")
        worksheet.append_row(
            [
                request_id, request_type, user_id, username, passport, fio,
                json.dumps(payload, ensure_ascii=False), "На рассмотрении", "",
                datetime.now().strftime("%d.%m.%Y %H:%M"), "", "",
            ],
            value_input_option="USER_ENTERED",
        )


requests_service = RequestsService()
