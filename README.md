# Bybit Stats Bot

Telegram-бот, который ведёт статистику твоей торговли на Bybit: подтягивает закрытые
сделки через официальный API, сохраняет их в локальную базу и по команде показывает
винрейт, PnL, profit factor, просадку и разбивку по инструментам.

## Как это устроено

```
bybit-stats-bot/
├── bot/
│   ├── config.py        # чтение .env
│   ├── bybit_client.py  # обёртка над Bybit API (только чтение)
│   ├── database.py      # локальный кэш сделок в SQLite
│   ├── sync.py          # подтягивание новых сделок из Bybit в БД
│   ├── stats.py         # расчёт статистики (winrate, PnL, profit factor, просадка...)
│   ├── formatting.py    # красивый текст для Telegram
│   └── main.py           # сам бот: команды + планировщик
├── requirements.txt
├── .env.example
└── README.md
```

Почему так:
- **Данные кэшируются в SQLite.** Bybit хранит историю closed-pnl ограниченное время,
  поэтому бот один раз тянет всё, что доступно, а дальше только новые сделки —
  статистика не теряется и не нужно постоянно опрашивать биржу.
- **API-ключи только для чтения.** Боту не нужны права на торговлю или вывод средств —
  создавай ключ на Bybit с правами **Read-Only**.
- **Список разрешённых user_id.** Статистику своего счёта видишь только ты — бот
  проверяет Telegram user_id перед каждой командой.
- **Планировщик (APScheduler)** сам синхронизирует сделки каждые N минут и присылает
  дайджест дня в заданное время, не дожидаясь команд.

## Установка

1. Установи Python 3.11+.
2. Склонируй/скопируй проект и установи зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Создай бота через [@BotFather](https://t.me/BotFather), получи `BOT_TOKEN`.
4. Узнай свой Telegram `user_id` через [@userinfobot](https://t.me/userinfobot).
5. На Bybit создай API-ключ с правами **только на чтение**
   (Account → API Management → Create New Key → без прав Trade/Withdraw).
6. Скопируй `.env.example` в `.env` и заполни:
   ```bash
   cp .env.example .env
   ```
7. Запусти бота:
   ```bash
   python -m bot.main
   ```

## Команды

| Команда | Что делает |
|---|---|
| `/start` | Проверка доступа и справка |
| `/sync` | Вручную подтянуть новые сделки из Bybit |
| `/stats` | Статистика за всё время |
| `/today` | Статистика за сегодня |
| `/week` | Статистика за 7 дней |
| `/month` | Статистика за 30 дней |
| `/symbol BTCUSDT` | Статистика по конкретному инструменту |
| `/balance` | Текущий баланс кошелька |
| `/positions` | Открытые позиции с нереализованным PnL |

## Хостинг

Бот — обычный long-polling процесс, ему не нужен публичный IP или домен. Варианты:
- Дешёвый VPS (Timeweb, Selectel, Hetzner и т.п.) + `systemd`/`screen`/`tmux`, либо
  Docker-контейнер с `restart: unless-stopped`.
- Локальный сервер/Raspberry Pi дома, если он всегда включён.

Пример systemd-юнита (`/etc/systemd/system/bybit-stats-bot.service`):
```ini
[Unit]
Description=Bybit Stats Bot
After=network.target

[Service]
WorkingDirectory=/opt/bybit-stats-bot
ExecStart=/opt/bybit-stats-bot/.venv/bin/python -m bot.main
Restart=always
EnvironmentFile=/opt/bybit-stats-bot/.env

[Install]
WantedBy=multi-user.target
```

## Что можно добавить дальше

- Графики equity-кривой (matplotlib) прямо в сообщении.
- Отдельная статистика по long/short.
- Сравнение периодов (эта неделя vs прошлая).
- Экспорт сделок в CSV/Excel по команде.
- Поддержка нескольких категорий одновременно (linear + spot + inverse).

Скажи, что из этого добавить — сделаю.
