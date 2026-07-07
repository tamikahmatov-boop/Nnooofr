from __future__ import annotations
import logging
import time

from .bybit_client import BybitClient
from .database import Database

log = logging.getLogger(__name__)

# Bybit отдаёт closed-pnl максимум за последние ~2 года, окно запроса ограничено.
# Берём с запасом назад при самой первой синхронизации.
FIRST_SYNC_LOOKBACK_MS = 730 * 24 * 60 * 60 * 1000  # ~730 дней


def sync_once(client: BybitClient, db: Database, category: str) -> int:
    """Тянет новые закрытые сделки из Bybit и сохраняет в БД. Возвращает число сохранённых записей."""
    last_sync = db.get_last_sync(category)
    start_ms = last_sync if last_sync else int(time.time() * 1000) - FIRST_SYNC_LOOKBACK_MS

    rows = client.get_closed_pnl(category=category, start_time_ms=start_ms)
    saved = db.upsert_trades(category, rows)

    db.set_last_sync(category, int(time.time() * 1000))
    log.info("Синхронизация (%s): получено %d записей", category, saved)
    return saved
