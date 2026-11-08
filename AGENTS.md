# AGENTS.md

`C:\appbox` is a personal portable-apps box, not a source repo: no build system, no tests, no git. Each subfolder is an extracted portable Windows build of a "Crafting App" from https://github.com/storytold/. Treat the `README.md` files as upstream docs, not editable source.

## Layout

- One folder per app: `deckcraft`, `designcraft`, `effectcraft`, `filmcraft`, `gridcraft`, `lightcraft`, `pdfcraft`, `photocraft`, `vectorcraft`, `wordcraft`.
- Each contains `<app>.exe`, `<app>-cli.exe`, upstream `README.md`, `LICENSE-MIT`/`LICENSE-APACHE`, and `OFL-*.txt` font licenses.
- `pdfcraft\models\` holds the OCR models (`text-detection.rten`, `text-recognition.rten`) and must stay beside `pdfcraft.exe`.
- `photocraft\PhotoCraftData\` and `pdfcraft\PdfCraftData\` hold settings, UI state, recovery autosaves and logs (portable mode).
- Windows Start Menu shortcuts live in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\AppBox` (created by `install_apps.py shortcuts`), so the apps are indexed by Windows Search.

## Portable mode rules

- `photocraft`, `pdfcraft`, `designcraft`, `effectcraft`, `filmcraft` and `vectorcraft` ship `portable.txt` next to the exe: settings/logs/recovery stay in the `<App>Data` folder (or `data` for filmcraft) beside the exe and nothing is written to `%APPDATA%`/`%LOCALAPPDATA%` (except effectcraft's disk/media caches, which still use `%LOCALAPPDATA%`). Keep `portable.txt` and move the whole folder together. Delete `portable.txt` to fall back to per-user folders.
- `lightcraft` supports portable mode optionally via `portable.txt` or `LightCraft.portable` (not shipped by default); data folder `LightCraftData`. Create one of those files to make it portable.
- `wordcraft`, `gridcraft`, `deckcraft` do NOT support `portable.txt` (verified: no reference in their binaries). Their settings live in `%APPDATA%\WordCraft` / `GridCraft` / `DeckCraft`. Do not create `portable.txt` for them; it is ignored. `*_NO_PREFS=1` runs them with no saved settings and logs to stderr only (agent/test mode).
- Moving all of `C:\appbox` carries the portable apps' settings; wordcraft/gridcraft/deckcraft (and lightcraft unless made portable) settings stay on the machine.

## Adding or updating an app

Manual: download the portable zip from `https://github.com/storytold/<app>/releases/latest` (`<app>-<ver>-windows-x64-portable.zip`), verify SHA-256 against `SHA256SUMS.txt`, scan on VirusTotal if possible, then extract into a fresh `C:\appbox\<app>\` folder, keeping `portable.txt` (photocraft/pdfcraft) and `pdfcraft\models\`.

Automated (preferred): run `python install_apps.py` from this folder. It detects the repo root from the script location, downloads latest releases, verifies SHA-256, optionally checks VirusTotal (set `VT_API_KEY` or use `--skip-vt`), asks for confirmation before running, and preserves existing `<App>Data` settings on update.

Travel/quick setup: clone this repo, then `python install_apps.py` (app folders are gitignored, so they are (re)installed locally).

Commands:
- `python install_apps.py` / `install` — install or update all apps (prompts first)
- `python install_apps.py update` — update only installed apps
- `python install_apps.py install wordcraft pdfcraft` — subset
- `python install_apps.py run <app>` — launch an app
- `python install_apps.py list` — show installed versions
- `python install_apps.py shortcuts` — create/update Windows Start Menu shortcuts (AppBox folder)
- `python install_apps.py assoc` — register per-user (HKCU) file associations for the configured extensions
- `python install_apps.py assoc <apps>` — subset of apps
- `python install_apps.py assoc --remove` — unregister associations (restores previous handlers)
- Flags: `--yes` (skip prompts), `--skip-vt`, `--root <dir>`

## Installed versions

| App | Exe | CLI | Version |
|---|---|---|---|
| deckcraft | deckcraft.exe | deckcraft-cli.exe | 0.16.0 |
| designcraft | designcraft.exe | designcraft-cli.exe | 0.18.0 |
| effectcraft | effectcraft.exe | effectcraft-cli.exe | 0.22.0 |
| filmcraft | filmcraft.exe | filmcraft-cli.exe | 0.18.0 |
| gridcraft | gridcraft.exe | gridcraft-cli.exe | 0.17.0 |
| lightcraft | lightcraft.exe | lightcraft-cli.exe | 0.19.0 |
| pdfcraft | pdfcraft.exe | pdfcraft-cli.exe | 0.19.0 |
| photocraft | photocraft.exe | photocraft-cli.exe | 0.21.0 |
| vectorcraft | vectorcraft.exe | vectorcraft-cli.exe | 0.22.0 |
| wordcraft | wordcraft.exe | wordcraft-cli.exe | 0.16.0 |

## File associations

Registered per-user (HKCU) by `install_apps.py assoc` (backed up in `HKCU\\Software\\PortableCraft\\Backup`):

| App | Extensions |
|---|---|
| wordcraft | .docx, .doc, .odt, .rtf |
| photocraft | .psd, .psb |
| gridcraft | .xlsx, .xls, .csv, .ods |
| deckcraft | .pptx, .ppt, .odp |
| designcraft | .designcraft, .design |
| effectcraft | .effectcraft, .efc |
| filmcraft | .filmcraft, .fc |
| lightcraft | .lightcraft, .lrc |
| vectorcraft | .svg, .ai, .eps, .vectorcraft |

(pdfcraft intentionally not associated.)

## Logs and data locations

| App | Log file |
|---|---|
| deckcraft | `%APPDATA%\DeckCraft\logs\deckcraft.log` (rotates `.1.log`/`.2.log`) |
| designcraft | `designcraft\DesignCraftData\logs\designcraft.log` |
| effectcraft | `effectcraft\EffectCraftData\logs\effectcraft.log` |
| filmcraft | `filmcraft\data\logs\filmcraft.log` (portable) / `%APPDATA%\FilmCraft\Logs\filmcraft.log` |
| gridcraft | `%APPDATA%\GridCraft\logs\gridcraft.log` |
| lightcraft | `%APPDATA%\LightCraft\logs\lightcraft.log` (default) / `lightcraft\LightCraftData\logs\lightcraft.log` (portable) |
| pdfcraft | `pdfcraft\PdfCraftData\logs\pdfcraft.log` |
| photocraft | `photocraft\PhotoCraftData\logs\photocraft.log` |
| vectorcraft | `vectorcraft\VectorCraftData\logs\vectorcraft.log` |
| wordcraft | `%APPDATA%\WordCraft\logs\wordcraft.log` |

## Driving the apps (agents)

- Each app exposes a CLI (`<app>-cli.exe`) and an MCP server (`<app>-cli mcp`) over stdio; see the per-app `README.md` for tool lists.
- Desktop UI automation: `<app> --control <file>` then `<app>-cli ui --control <file> ...` (loopback, token-gated). See `docs/control-protocol.md` in each repo.
- Keep `*_NO_PREFS=1` for clean, side-effect-free agent runs.

## Do not

- Edit or delete the upstream `README.md` files as if they were project docs.
- Delete `<App>Data` folders (settings/recovery).
- Install MSI installers into this box; portable zips only.
- Add `portable.txt` to wordcraft/gridcraft/deckcraft (unsupported).
- Expect VirusTotal automation to exist locally.