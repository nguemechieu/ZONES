# ZONES Install Guide

## What Gets Installed

The Windows release installs:

- the frozen Python utility that runs the ZONES launcher, dashboard, WebSocket bridge, and named-pipe bridge
- product documentation in `docs\`
- MT4 integration files in `MT4\`

The installer places the application under:

- `C:\Program Files\ZONES`

Writable runtime state is kept outside the install folder:

- `%ProgramData%\ZONES\data`
- `%ProgramData%\ZONES\logs`

That separation lets upgrades avoid overwriting user data or runtime configuration.

## Install From The Installer

1. Run `ZONES-Setup-x.y.z.exe` as an administrator.
2. Accept the install location or keep the default `C:\Program Files\ZONES`.
3. Choose whether to create a desktop shortcut.
4. Finish the wizard.
5. Launch `ZONES` from the Start Menu or desktop shortcut.

## After Install

When ZONES starts:

- the desktop utility opens
- the Python service stack starts in the background
- the dashboard becomes available at `http://127.0.0.1:8787`

MT4 files are installed into:

- `C:\Program Files\ZONES\MT4`

Copy those files into your MetaTrader 4 data folder as needed:

- `Experts\ZONES.mq4` or `Experts\ZONES.ex4`
- `Include\ZonesBridge.mqh`
- `Indicators\ZigZag.mq4` or `Indicators\ZigZag.ex4`
- `Presets\setting.set`

## Install From The Release Zip

If you use the release zip instead of the installer:

1. Extract `ZONES-vx.y.z.zip`.
2. Keep the `app\ZONES` folder structure intact.
3. Run `app\ZONES\ZONES.exe`.
4. Copy the packaged `MT4\` files into your MT4 terminal manually.

## Local Runtime Paths

Important runtime locations:

- Database: `%ProgramData%\ZONES\data\zones.db`
- Runtime settings: `%ProgramData%\ZONES\logs\runtime_settings.json`
- Signal model: `%ProgramData%\ZONES\logs\signal_model.json`
- Audit log: `%ProgramData%\ZONES\logs\ai_decisions.jsonl`

## Environment Overrides

You can override default paths with environment variables:

- `ZONES_HOME`
- `ZONES_DATA_DIR`
- `ZONES_LOG_DIR`
- `ZONES_DATABASE_URL`
- `ZONES_DATABASE_PATH`
- `ZONES_RUNTIME_SETTINGS`
- `ZONES_SIGNAL_MODEL`
- `ZONES_AUDIT_LOG`

