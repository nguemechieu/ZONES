# Runtime Settings

The system page is available at:

```text
http://127.0.0.1:8787/system
```

It lets the user configure database credentials, Telegram notifications, and the default chart symbol without editing environment variables.

## Database Settings

Use the database section to enter:

- Database URL or host, for example `sqlite:///data/zones.db` or `postgresql://host:5432/zones`
- Database username
- Database password

ZONES stores the effective URL in runtime settings and masks secrets in the status view. If a password field is left blank on save, the existing stored password is kept.

## Telegram Settings

Use the Telegram section to enter the bot token and optionally enable notifications.

To discover the chat id:

1. Create or open the Telegram bot.
2. Send a message to the bot from the account, group, or channel that should receive ZONES updates.
3. Paste the bot token into `/system`.
4. Save runtime settings.

The app calls Telegram `getUpdates` and fills the chat id list from the latest bot updates. If no chat id is found, send another message to the bot and save again.

## Default Chart Symbol

The chart symbol section stores the default symbol used by `/chart` when no `symbol` query parameter is present.

Users can still override the symbol directly on the chart page:

```text
http://127.0.0.1:8787/chart?symbol=EURUSD&timeframe=5M
```

The ZONES candle terminal filters candles and zones to the selected symbol and timeframe.
