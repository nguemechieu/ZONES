# GitHub Release Checklist

## Preflight

- Confirm `src/version.py` matches the intended release version.
- Review release notes and breaking changes.
- Confirm no secrets, `.env`, local logs, or credentials are present in the release folder.

## Build And Verify

- Run `.\scripts\build_release.ps1`
- Verify tests passed.
- Verify `dist\ZONES-vX.Y.Z\app\ZONES\ZONES.exe` exists.
- Verify `dist\ZONES-vX.Y.Z\MT4\` contains the expected MT4 files.
- Verify `dist\ZONES-vX.Y.Z.zip` exists.
- Verify `dist\ZONES-vX.Y.Z\installer\ZONES-Setup-X.Y.Z.exe` exists if Inno Setup was available.

## GitHub Release Steps

- Create or update the release branch if needed.
- Create the git tag for `vX.Y.Z`.
- Push the tag to GitHub.
- Create the GitHub Release entry.
- Upload `ZONES-Setup-X.Y.Z.exe`.
- Upload `ZONES-vX.Y.Z.zip`.
- Paste release notes with highlights, fixes, known issues, and upgrade notes.

## Post Release

- Smoke test the installer on a clean Windows machine.
- Smoke test the zip package on a clean Windows machine.
- Confirm the dashboard opens and MT4 bridge ports are reachable.
- Confirm runtime files are being created under `%ProgramData%\ZONES`.
