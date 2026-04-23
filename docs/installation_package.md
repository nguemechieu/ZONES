# Installation Package

The first installable package is generated in `dist/`.

Build commands:

```powershell
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
Compress-Archive -Path dist\zones-1.0.0-py3-none-any.whl,README.md,docs\*.md,requirements.txt -DestinationPath dist\ZONES-1.0.0-installation.zip -Force
```

The zip includes the wheel, README, supporting docs, and dependency manifest.

Install from the wheel:

```powershell
python -m pip install dist\zones-1.0.0-py3-none-any.whl
```

Run after install:

```powershell
zones
```

Or run from source:

```powershell
python zones.py
```

Open the dashboard:

```text
http://127.0.0.1:8787
```

Key pages:

- `/chart` for TradingView plus local ZONES overlays.
- `/portfolio` for hedge fund style portfolio analysis.
- `/system` for runtime database, Telegram, and chart-symbol settings.
