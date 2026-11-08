# 📦 PortableCraft

A portable-apps box for the "Crafting Apps" by [storytold](https://github.com/storytold), plus a stdlib-only Python installer/updater that downloads, verifies and runs them.

## 🚀 Quick initiate (copy to clipboard)

Paste this into OpenCode, Claude, Hermes, or any similar agent to get started:

```
Clone https://github.com/mendezrein/PortableCraft.git into the working directory,
check that Python 3.8+ is available, then ask the user for permission before running:
python install_apps.py
```

Or run it yourself:

```sh
git clone https://github.com/mendezrein/PortableCraft.git
cd PortableCraft
python --version
python install_apps.py        # asks for permission before installing/updating
```

## ✨ What it does

- Downloads the latest portable Windows zips for each Crafting App from `github.com/storytold/<app>/releases/latest`.
- Verifies every zip's SHA-256 against the release's `SHA256SUMS.txt`.
- Optionally checks the file on VirusTotal (set `VT_API_KEY`, or use `--skip-vt`).
- Extracts into `<app>/` folders beside the installer, preserving existing `<App>Data` settings on update.
- Creates Windows Start Menu shortcuts under `%APPDATA%\...\Programs\AppBox` so the apps are indexed by Windows Search.

Apps managed: deckcraft, designcraft, effectcraft, filmcraft, gridcraft, lightcraft, pdfcraft, photocraft, vectorcraft, wordcraft (artcraft excluded).

## 📋 Requirements

- Python 3.8+ (stdlib only, no pip installs).
- Windows (the apps ship Windows portable zips; the installer also runs on other OSes but there is nothing to launch there).
- Network access to GitHub releases (and optionally VirusTotal).
- Optional: `VT_API_KEY` environment variable for automated VirusTotal scans.

## 🛠️ Usage

```sh
python install_apps.py                 # install or update all apps (prompts first)
python install_apps.py update          # update only installed apps
python install_apps.py install wordcraft pdfcraft   # subset
python install_apps.py run <app>      # launch an app
python install_apps.py list            # show installed versions
python install_apps.py shortcuts       # create/update Start Menu shortcuts
python install_apps.py assoc           # register per-user file associations
python install_apps.py assoc --remove  # unregister (restores previous handlers)
```

Flags: `--yes` (skip prompts), `--skip-vt`, `--root <dir>`.

## 📁 Portable mode

- `photocraft`, `pdfcraft`, `designcraft`, `effectcraft`, `filmcraft`, `vectorcraft` ship `portable.txt`: settings/logs/recovery stay in an `<App>Data` folder (or `data` for filmcraft) beside the exe. Move the whole folder to carry them. Delete `portable.txt` to use `%APPDATA%`.
- `lightcraft` supports portable mode optionally via `portable.txt` or `LightCraft.portable`.
- `deckcraft`, `gridcraft`, `wordcraft` do NOT support `portable.txt`; their settings live in `%APPDATA%\DeckCraft` / `GridCraft` / `WordCraft`.

## 🔗 File associations

`python install_apps.py assoc` registers per-user (HKCU) default handlers for:
wordcraft (.docx/.doc/.odt/.rtf), photocraft (.psd/.psb), gridcraft (.xlsx/.xls/.csv/.ods),
deckcraft (.pptx/.ppt/.odp), designcraft, effectcraft, filmcraft, lightcraft, vectorcraft.
Existing handlers are backed up in `HKCU\\Software\\PortableCraft\\Backup` and restored with `--remove`.
(pdfcraft is intentionally not associated.)

## ✈️ Travel / quick setup

Clone this repo, then `python install_apps.py`. App folders are gitignored, so they are (re)installed locally; portable apps carry their settings inside the folder.

## 🙏 Credits

- The Crafting Apps themselves are built by [storytold](https://github.com/storytold) and are released under their own MIT/Apache licenses (see each app's `LICENSE-MIT` / `LICENSE-APACHE`). PortableCraft is only an installer/documentation wrapper and does not redistribute the apps.
- Original project docs: per-app `README.md` files inside each installed folder.

## 📄 License

PortableCraft's own files (`install_apps.py`, `AGENTS.md`, this README) are provided as-is. The bundled Crafting Apps retain their upstream licenses.