"""
Обёртка над pybit (Bybit API v5, unified trading) — только чтение.
Ключам API нужны права ТОЛЬКО на чтение (Read-Only), торговые права не нужны.
"""
from __future__ import annotations
import logging
from typing import Optional

from pybit.unified_trading import HTTP

log = logging.getLogger(__name__)


class BybitClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.session = HTTP(api_key=api_key, api_secret=api_secret, testnet=testnet)

    def get_closed_pnl(
        self,
        category: str = "linear",
        symbol: Optional[str] = None,
        start_time_ms: Optional[int] = None,
        limit: int = 200,
    ) -> list[dict]:
        """Возвращает все записи закрытых позиций (с пагинацией по курсору)."""
        results: list[dict] = []
        cursor = None
        while True:
            params = {"category": category, "limit": limit}
            if symbol:
                params["symbol"] = symbol
            if start_time_ms:
                params["startTime"] = start_time_ms
            if cursor:
                params["cursor"] = cursor

            resp = self.session.get_closed_pnl(**params)
            if resp.get("retCode") != 0:
                raise RuntimeError(f"Bybit API error: {resp.get('retMsg')}")

            data = resp.get("result", {})
            rows = data.get("list", [])
            results.extend(rows)

            cursor = data.get("nextPageCursor")
            if not cursor or not rows:
                break
        return results

    def get_wallet_balance(self, account_type: str = "UNIFIED") -> dict:
        resp = self.session.get_wallet_balance(accountType=account_type)
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit API error: {resp.get('retMsg')}")
        return resp["result"]

    def get_positions(self, category: str = "linear", settle_coin: str = "USDT") -> list[dict]:
        resp = self.session.get_positions(category=category, settleCoin=settle_coin)
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit API error: {resp.get('retMsg')}")
        return resp["result"].get("list", [])
