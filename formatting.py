from __future__ import annotations
from .stats import Stats


def fmt_money(v: float) -> str:
    sign = "+" if v > 0 else ""
    return f"{sign}{v:,.2f}".replace(",", " ")


def format_stats(title: str, s: Stats, top_n_symbols: int = 5) -> str:
    if s.total_trades == 0:
        return f"📊 *{title}*\n\nСделок не найдено за этот период."

    pnl_emoji = "🟢" if s.total_pnl >= 0 else "🔴"
    pf = "∞" if s.profit_factor == float("inf") else f"{s.profit_factor}"

    lines = [
        f"📊 *{title}*",
        "",
        f"{pnl_emoji} Итог: *{fmt_money(s.total_pnl)} USDT*",
        f"Сделок: {s.total_trades}  (🟢 {s.wins} / 🔴 {s.losses} / ⚪ {s.breakeven})",
        f"Winrate: *{s.win_rate}%*",
        f"Profit factor: {pf}",
        f"Средний профит: {fmt_money(s.avg_win)}",
        f"Средний убыток: {fmt_money(s.avg_loss)}",
        f"Лучшая сделка: {fmt_money(s.best_trade)}",
        f"Худшая сделка: {fmt_money(s.worst_trade)}",
        f"Макс. просадка (по закрытым): {fmt_money(-s.max_drawdown)}",
    ]

    if s.by_symbol:
        lines.append("")
        lines.append("*По инструментам:*")
        for i, (sym, pnl) in enumerate(s.by_symbol.items()):
            if i >= top_n_symbols:
                lines.append(f"…и ещё {len(s.by_symbol) - top_n_symbols}")
                break
            e = "🟢" if pnl >= 0 else "🔴"
            lines.append(f"{e} {sym}: {fmt_money(pnl)}")

    return "\n".join(lines)
