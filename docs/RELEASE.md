# ZONES Release Guide

## Release Outputs

The Windows release build creates:

- `dist\ZONES-vX.Y.Z\app\ZONES\...` for the PyInstaller app bundle
- `dist\ZONES-vX.Y.Z\MT4\...` for MT4 files kept separate from the Python app
- `dist\ZONES-vX.Y.Z\docs\...` for release docs
- `dist\ZONES-vX.Y.Z\installer\ZONES-Setup-X.Y.Z.exe` when Inno Setup is installed
- `dist\ZONES-vX.Y.Z.zip` for GitHub release upload

## Python Entry Point

The packaged executable starts from:

- `zones.py`

That launcher creates the desktop utility and starts:

- `DashboardServer`
- `WebSocketBridgeServer`
- `NamedPipeBridgeServer`

## PyInstaller

Release builds use:

- `ZONES.spec`

The spec bundles:

- `zones.py`
- `src/assets/Zones.png`
- `src/assets/Zones.ico`
- PySide6 runtime files
- WebSocket package metadata and hidden imports

## Build Command

From a clean Windows clone:

```powershell
.\scripts\build_release.ps1
```

Optional flags:

```powershell
.\scripts\build_release.ps1 -SkipInstaller
.\scripts\build_release.ps1 -SkipTests
.\scripts\build_release.ps1 -PythonExe C:\Python314\python.exe
```

## Build Script Responsibilities

The release script:

1. Removes prior build output.
2. Creates or reuses `.venv-release`.
3. Installs runtime, dev, and build dependencies.
4. Runs `unittest` discovery when tests exist.
5. Builds the app with PyInstaller.
6. Creates `dist\ZONES-vX.Y.Z`.
7. Copies docs and MT4 files into the release folder.
8. Builds the Inno Setup installer when `ISCC.exe` is available.
9. Creates `dist\ZONES-vX.Y.Z.zip`.

## MT4 Release Contents

The release currently packages the MT4 files required for the ZONES workflow:

- `Experts\ZONES.mq4`
- `Experts\ZONES.ex4` when present
- `Include\ZonesBridge.mqh`
- `Libraries\ZonesBridge.dll` when present
- `Indicators\ZigZag.mq4`
- `Indicators\ZigZag.ex4` when present
- `Presets\setting.set`
- `Images\zones_ea.ico`

This keeps MT4 content explicit and separate from the Python runtime.

## Installer

The installer source lives at:

- `installer\ZONES.iss`

Installer behavior:

- installs the application into `C:\Program Files\ZONES`
- creates a Start Menu shortcut
- can create a Desktop shortcut
- includes documentation
- includes MT4 files in `C:\Program Files\ZONES\MT4`
- keeps writable data under `%ProgramData%\ZONES`
- does not ship `.env`, secrets, logs, or local credentials

