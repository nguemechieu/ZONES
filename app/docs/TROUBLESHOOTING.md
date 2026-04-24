# ZONES Packaging Troubleshooting

## Build Fails Because `python` Is Missing

Use an explicit interpreter:

```powershell
.\scripts\build_release.ps1 -PythonExe C:\Python314\python.exe
```

## PyInstaller Is Not Found

The release script installs PyInstaller through the build extra. Re-run:

```powershell
.\scripts\build_release.ps1
```

If dependency installation failed, inspect the pip output inside `.venv-release`.

## Inno Setup Installer Was Skipped

The build script only compiles the installer when `ISCC.exe` is present in a standard Inno Setup 6 install path.

Install Inno Setup 6, then re-run:

```powershell
.\scripts\build_release.ps1
```

Or explicitly skip it:

```powershell
.\scripts\build_release.ps1 -SkipInstaller
```

## Tests Fail During Release Build

Run the same command directly:

```powershell
python -m unittest discover -s tests
```

If you need a packaging-only dry run:

```powershell
.\scripts\build_release.ps1 -SkipTests
```

## Installed App Cannot Write Logs Or Database

The packaged app is designed to write under:

- `%ProgramData%\ZONES\data`
- `%ProgramData%\ZONES\logs`

If your environment restricts that location, override it with:

- `ZONES_HOME`
- `ZONES_DATA_DIR`
- `ZONES_LOG_DIR`
- `ZONES_DATABASE_URL`

## Dashboard Does Not Open

Check whether another process is already using:

- `127.0.0.1:8787` for the dashboard
- `127.0.0.1:8090` for the WebSocket bridge

You can override ports with environment variables before starting the app:

- `ZONES_DASHBOARD_PORT`
- `ZONES_WS_PORT`

## MT4 Cannot Find The Files

The installer does not place MT4 files into your terminal automatically. Copy the packaged files from:

- `C:\Program Files\ZONES\MT4`

into your MetaTrader 4 data folder structure.

## Secrets Or `.env` Show Up In A Release Folder

They should not. The release process only copies:

- the PyInstaller application output
- selected documentation
- selected MT4 files

Do not add `.env`, account exports, local logs, or database snapshots to the release folder before publishing.

