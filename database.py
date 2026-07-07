"""
Локальный кэш закрытых сделок в SQLite.
Bybit хранит историю closed-pnl ограниченное время, поэтому бот сохраняет
всё, что видит, себе в базу — так статистика не теряется со временем.
"""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from typing import Iterable, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS closed_trades (
    order_id        TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,
    qty             REAL NOT NULL,
    avg_entry_price REAL,
    avg_exit_price  REAL,
    closed_pnl      REAL NOT NULL,
    leverage        REAL,
    category        TEXT NOT NULL,
    created_time_ms INTEGER NOT NULL,
    updated_time_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_created_time ON closed_trades(created_time_ms);
CREATE INDEX IF NOT EXISTS idx_symbol ON closed_trades(symbol);

CREATE TABLE IF NOT EXISTS sync_state (
    category        TEXT PRIMARY KEY,
    last_synced_ms  INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert_trades(self, category: str, rows: Iterable[dict]) -> int:
        """Сохраняет записи Bybit closed-pnl. Возвращает число новых/обновлённых строк."""
        count = 0
        with self._conn() as conn:
            for r in rows:
                try:
                    conn.execute(
                        """
                        INSERT INTO closed_trades
                            (order_id, symbol, side, qty, avg_entry_price, avg_exit_price,
                             closed_pnl, leverage, category, created_time_ms, updated_time_ms)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(order_id) DO UPDATE SET
                            closed_pnl=excluded.closed_pnl,
                            updated_time_ms=excluded.updated_time_ms
                        """,
                        (
                            r["orderId"],
                            r["symbol"],
                            r["side"],
                            float(r.get("qty") or 0),
                            float(r.get("avgEntryPrice") or 0) if r.get("avgEntryPrice") else None,
                            float(r.get("avgExitPrice") or 0) if r.get("avgExitPrice") else None,
                            float(r.get("closedPnl") or 0),
                            float(r.get("leverage") or 0) if r.get("leverage") else None,
                            category,
                            int(r["createdTime"]),
                            int(r["updatedTime"]),
                        ),
                    )
                    count += 1
                except (KeyError, ValueError):
                    continue
        return count

    def get_trades(
        self,
        since_ms: Optional[int] = None,
        until_ms: Optional[int] = None,
        symbol: Optional[str] = None,
    ) -> list[sqlite3.Row]:
        query = "SELECT * FROM closed_trades WHERE 1=1"
        params: list = []
        if since_ms is not None:
            query += " AND created_time_ms >= ?"
            params.append(since_ms)
        if until_ms is not None:
            query += " AND created_time_ms <= ?"
            params.append(until_ms)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        query += " ORDER BY created_time_ms ASC"
        with self._conn() as conn:
            return conn.execute(query, params).fetchall()

    def get_last_sync(self, category: str) -> Optional[int]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT last_synced_ms FROM sync_state WHERE category = ?", (category,)
            ).fetchone()
            return row["last_synced_ms"] if row else None

    def set_last_sync(self, category: str, ts_ms: int) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO sync_state (category, last_synced_ms) VALUES (?, ?)
                ON CONFLICT(category) DO UPDATE SET last_synced_ms=excluded.last_synced_ms
                """,
                (category, ts_ms),
            )
