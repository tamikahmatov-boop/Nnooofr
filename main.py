"""
Telegram-бот статистики торговли на Bybit.

Команды:
  /start      — проверка доступа и краткая справка
  /sync       — вручную подтянуть новые сделки из Bybit
  /stats      — статистика за всё время
  /today      — статистика за сегодня
  /week       — статистика за 7 дней
  /month      — статистика за 30 дней
  /symbol XXX — статистика по конкретному инструменту (например /symbol BTCUSDT)
  /balance    — текущий баланс кошелька
  /positions  — открытые позиции
"""
from __future__ import annotations
import asyncio
import logging
import time
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import config
from .bybit_client import BybitClient
from .database import Database
from .stats import compute_stats
from .formatting import format_stats, fmt_money
from .sync import sync_once

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bybit-stats-bot")

router = Router()
db = Database(config.db_path)
bybit = BybitClient(config.bybit_api_key, config.bybit_api_secret, testnet=config.bybit_testnet)


def _allowed(message: Message) -> bool:
    if not config.allowed_user_ids:
        return True  # не рекомендуется, но не блокируем работу бота
    return message.from_user is not None and message.from_user.id in config.allowed_user_ids


async def _deny(message: Message) -> None:
    await message.answer("⛔ У тебя нет доступа к этому боту.")


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not _allowed(message):
        await _deny(message)
        return
    await message.answer(
        "👋 Бот статистики торговли Bybit запущен.\n\n"
        "Команды:\n"
        "/sync — подтянуть новые сделки\n"
        "/stats — статистика за всё время\n"
        "/today, /week, /month — статистика за период\n"
        "/symbol BTCUSDT — статистика по инструменту\n"
        "/balance — баланс кошелька\n"
        "/positions — открытые позиции"
    )


@router.message(Command("sync"))
async def cmd_sync(message: Message) -> None:
    if not _allowed(message):
        await _deny(message)
        return
    await message.answer("🔄 Синхронизирую сделки с Bybit…")
    try:
        saved = await asyncio.to_thread(sync_once, bybit, db, config.category)
        await message.answer(f"✅ Готово. Обработано записей: {saved}")
    except Exception as e:
        log.exception("Ошибка синхронизации")
        await message.answer(f"❌ Ошибка синхронизации: {e}")


async def _send_period_stats(message: Message, title: str, since: datetime | None) -> None:
    since_ms = _ms(since) if since else None
    trades = await asyncio.to_thread(db.get_trades, since_ms, None, None)
    s = compute_stats(trades)
    await message.answer(format_stats(title, s), parse_mode="Markdown")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _allowed(message):
        await _deny(message)
        return
    await _send_period_stats(message, "Статистика за всё время", None)


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    if not _allowed(message):
        await _deny(message)
        return
    since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    await _send_period_stats(message, "Статистика за сегодня", since)


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    if not _allowed(message):
        await _deny(message)
        return
    since = datetime.now() - timedelta(days=7)
    await _send_period_stats(message, "Статистика за 7 дней", since)


@router.message(Command("month"))
async def cmd_month(message: Message) -> None:
    if not _allowed(message):
        await _deny(message)
        return
    since = datetime.now() - timedelta(days=30)
    await _send_period_stats(message, "Статистика за 30 дней", since)


@router.message(Command("symbol"))
async def cmd_symbol(message: Message, command: CommandObject) -> None:
    if not _allowed(message):
        await _deny(message)
        return
    if not command.args:
        await message.answer("Укажи символ, например: /symbol BTCUSDT")
        return
    symbol = command.args.strip().upper()
    trades = await asyncio.to_thread(db.get_trades, None, None, symbol)
    s = compute_stats(trades)
    await message.answer(format_stats(f"Статистика по {symbol}", s), parse_mode="Markdown")


@router.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    if not _allowed(message):
        await _deny(message)
        return
    try:
        result = await asyncio.to_thread(bybit.get_wallet_balance)
        accounts = result.get("list", [])
        if not accounts:
            await message.answer("Не удалось получить данные баланса.")
            return
        acc = accounts[0]
        total_equity = float(acc.get("totalEquity") or 0)
        total_pnl_unrealized = float(acc.get("totalPerpUPL") or 0)
        lines = [
            "💰 *Баланс*",
            f"Общий эквити: {fmt_money(total_equity)} USD",
            f"Нереализованный PnL: {fmt_money(total_pnl_unrealized)} USD",
        ]
        await message.answer("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        log.exception("Ошибка получения баланса")
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("positions"))
async def cmd_positions(message: Message) -> None:
    if not _allowed(message):
        await _deny(message)
        return
    try:
        positions = await asyncio.to_thread(bybit.get_positions, config.category)
        open_pos = [p for p in positions if float(p.get("size") or 0) != 0]
        if not open_pos:
            await message.answer("Открытых позиций нет.")
            return
        lines = ["📈 *Открытые позиции*", ""]
        for p in open_pos:
            upl = float(p.get("unrealisedPnl") or 0)
            e = "🟢" if upl >= 0 else "🔴"
            lines.append(
                f"{e} {p['symbol']} {p['side']} размер {p['size']} "
                f"@ {p.get('avgPrice')} | PnL: {fmt_money(upl)}"
            )
        await message.answer("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        log.exception("Ошибка получения позиций")
        await message.answer(f"❌ Ошибка: {e}")


async def scheduled_sync() -> None:
    try:
        saved = await asyncio.to_thread(sync_once, bybit, db, config.category)
        log.info("Плановая синхронизация: %d записей", saved)
    except Exception:
        log.exception("Ошибка плановой синхронизации")


async def scheduled_digest(bot: Bot) -> None:
    if not config.allowed_user_ids:
        return
    since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    trades = await asyncio.to_thread(db.get_trades, _ms(since), None, None)
    s = compute_stats(trades)
    text = format_stats("Итоги дня", s)
    for user_id in config.allowed_user_ids:
        try:
            await bot.send_message(user_id, text, parse_mode="Markdown")
        except Exception:
            log.exception("Не удалось отправить дайджест пользователю %s", user_id)


async def main() -> None:
    errors = config.validate()
    for e in errors:
        log.warning("Проблема конфигурации: %s", e)
    if not config.bot_token or not config.bybit_api_key:
        log.error("BOT_TOKEN и BYBIT_API_KEY обязательны. Заполни .env и перезапусти.")
        return

    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    # Первая синхронизация при старте
    await scheduled_sync()

    scheduler = AsyncIOScheduler(timezone=config.timezone)
    scheduler.add_job(scheduled_sync, "interval", minutes=config.sync_interval_minutes)
    scheduler.add_job(
        scheduled_digest,
        CronTrigger(hour=config.daily_digest_hour, minute=config.daily_digest_minute),
        args=[bot],
    )
    scheduler.start()

    log.info("Бот запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
