"""
Расчёт торговой статистики по списку сделок (строк из БД).
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Stats:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    max_drawdown: float = 0.0
    by_symbol: dict = field(default_factory=dict)  # symbol -> pnl


def compute_stats(trades) -> Stats:
    s = Stats()
    if not trades:
        return s

    pnls = [float(t["closed_pnl"]) for t in trades]
    s.total_trades = len(pnls)
    s.wins = sum(1 for p in pnls if p > 0)
    s.losses = sum(1 for p in pnls if p < 0)
    s.breakeven = s.total_trades - s.wins - s.losses
    s.win_rate = round(100 * s.wins / s.total_trades, 2) if s.total_trades else 0.0
    s.total_pnl = round(sum(pnls), 4)

    win_vals = [p for p in pnls if p > 0]
    loss_vals = [p for p in pnls if p < 0]
    s.avg_win = round(sum(win_vals) / len(win_vals), 4) if win_vals else 0.0
    s.avg_loss = round(sum(loss_vals) / len(loss_vals), 4) if loss_vals else 0.0

    gross_profit = sum(win_vals)
    gross_loss = abs(sum(loss_vals))
    s.profit_factor = round(gross_profit / gross_loss, 3) if gross_loss > 0 else (
        float("inf") if gross_profit > 0 else 0.0
    )

    s.best_trade = round(max(pnls), 4)
    s.worst_trade = round(min(pnls), 4)

    # Максимальная просадка по equity-кривой закрытых сделок
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    s.max_drawdown = round(max_dd, 4)

    by_symbol: dict[str, float] = {}
    for t in trades:
        by_symbol[t["symbol"]] = round(by_symbol.get(t["symbol"], 0.0) + float(t["closed_pnl"]), 4)
    s.by_symbol = dict(sorted(by_symbol.items(), key=lambda kv: kv[1], reverse=True))

    return s
