#!/usr/bin/env python3
"""Install or update the portable Crafting Apps in this folder.

Downloads the latest portable Windows builds from github.com/storytold/<app>,
verifies SHA-256 against the release's SHA256SUMS.txt, optionally checks
VirusTotal, and extracts into C:\\appbox\\<app>\\ (or --root).

Usage:
    python install_apps.py                # install/update all apps (asks first)
    python install_apps.py install        # same
    python install_apps.py update         # update only already-installed apps
    python install_apps.py install wordcraft pdfcraft
    python install_apps.py run wordcraft  # launch an app
    python install_apps.py list          # show installed versions
    python install_apps.py --yes         # skip the confirmation prompt
    python install_apps.py --skip-vt     # skip VirusTotal check
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

try:
    import winreg
    import ctypes
    _WINREG_OK = True
except ImportError:
    _WINREG_OK = False
APPS = ["deckcraft", "designcraft", "effectcraft", "filmcraft", "gridcraft",
        "lightcraft", "pdfcraft", "photocraft", "vectorcraft", "wordcraft"]
PASCAL = {
    "deckcraft": "DeckCraft",
    "designcraft": "DesignCraft",
    "effectcraft": "EffectCraft",
    "filmcraft": "FilmCraft",
    "gridcraft": "GridCraft",
    "lightcraft": "LightCraft",
    "pdfcraft": "PdfCraft",
    "photocraft": "PhotoCraft",
    "vectorcraft": "VectorCraft",
    "wordcraft": "WordCraft",
}

# File associations to register (per-user, HKCU). PdfCraft is intentionally
# omitted: the user chose not to override the default PDF handler.
FILE_ASSOC = {
    "wordcraft": [".docx", ".doc", ".odt", ".rtf"],
    "photocraft": [".psd", ".psb"],
    "gridcraft": [".xlsx", ".xls", ".csv", ".ods"],
    "deckcraft": [".pptx", ".ppt", ".odp"],
    "designcraft": [".designcraft", ".design"],
    "effectcraft": [".effectcraft", ".efc"],
    "filmcraft": [".filmcraft", ".fc"],
    "lightcraft": [".lightcraft", ".lrc"],
    "vectorcraft": [".svg", ".ai", ".eps", ".vectorcraft"],
}

GITHUB_ORG = "storytold"
ARCH = "x64"


def root_dir() -> Path:
    # Work wherever this script (and the git checkout) lives.
    return Path(__file__).resolve().parent


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "appbox-installer/1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def latest_release(app: str):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{app}/releases/latest"
    data = json.loads(http_get(url))
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    return data.get("tag_name", ""), assets


def find_zip_asset(assets, app, arch=ARCH):
    # <app>-<ver>-windows-<arch>-portable.zip
    for name in assets:
        if name.endswith("-portable.zip") and f"-windows-{arch}-" in name and name.startswith(app + "-"):
            return name
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def parse_sha256sums(text: str):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            out[parts[-1].lstrip("*")] = parts[0].upper()
    return out


def vt_check(file_hash: str, api_key: str | None):
    """Return True if clean, False if malicious, None if unknown/skipped."""
    if not api_key:
        return None
    try:
        req = urllib.request.Request(
            f"https://www.virustotal.com/api/v3/files/{file_hash}",
            headers={"x-apikey": api_key},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        stats = data["data"]["attributes"]["last_analysis_stats"]
        if stats.get("malicious", 0) > 0 or stats.get("suspicious", 0) > 0:
            return False
        if stats.get("harmless", 0) + stats.get("undetected", 0) > 0:
            return True
        return None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # not yet scanned
        raise


def confirm(prompt: str, auto_yes: bool) -> bool:
    if auto_yes:
        return True
    ans = input(f"{prompt} [y/N]: ").strip().lower()
    return ans in ("y", "yes")


def is_installed(app: str, root: Path) -> bool:
    return (root / app / f"{app}.exe").is_file()


def backup_portable_state(target: Path, backup: Path):
    backup.mkdir(parents=True, exist_ok=True)
    data_dir = target / f"{PASCAL[target.name if target.name in PASCAL else '']}Data".replace("DataData", "Data")
    # target.name is lowercase app; build data dir name from PASCAL
    app = target.name
    data_dir = target / f"{PASCAL[app]}Data"
    if data_dir.is_dir():
        shutil.copytree(data_dir, backup / data_dir.name, dirs_exist_ok=True)
    portable = target / "portable.txt"
    if portable.is_file():
        shutil.copy2(portable, backup / "portable.txt")


def restore_portable_state(target: Path, backup: Path):
    app = target.name
    data_dir = target / f"{PASCAL[app]}Data"
    src_data = backup / f"{PASCAL[app]}Data"
    if src_data.is_dir():
        if data_dir.exists():
            shutil.rmtree(data_dir)
        shutil.move(str(src_data), str(data_dir))
    src_portable = backup / "portable.txt"
    if src_portable.is_file():
        shutil.copy2(src_portable, target / "portable.txt")


def install_one(app: str, root: Path, auto_yes: bool, skip_vt: bool, vt_key: str | None, update_only: bool):
    target = root / app
    if update_only and not is_installed(app, root):
        print(f"[{app}] not installed, skipping (update-only)")
        return True

    print(f"\n=== {app} ===")
    tag, assets = latest_release(app)
    print(f"latest release: {tag}")
    zip_name = find_zip_asset(assets, app)
    if not zip_name:
        print(f"[{app}] no portable zip asset found; skipping")
        return False
    zip_url = assets[zip_name]
    sums_name = next((n for n in assets if n.lower().startswith("sha256sums")), None)

    expected_hash = None
    if sums_name:
        sums_text = http_get(assets[sums_name]).decode("utf-8", "replace")
        parsed = parse_sha256sums(sums_text)
        expected_hash = parsed.get(zip_name)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        zip_path = td / zip_name
        print(f"downloading {zip_name} ...")
        zip_path.write_bytes(http_get(zip_url))
        actual_hash = sha256_file(zip_path)
        print(f"sha256: {actual_hash}")
        if expected_hash:
            if actual_hash != expected_hash:
                print(f"[{app}] CHECKSUM MISMATCH (expected {expected_hash}); aborting")
                return False
            print("checksum OK")
        else:
            print("[{app}] no SHA256SUMS entry; cannot verify checksum".format(app=app))

        if not skip_vt:
            vt_result = vt_check(actual_hash, vt_key)
            if vt_result is None:
                if vt_key:
                    print(f"[{app}] VirusTotal: no report yet (hash not found).")
                else:
                    print(f"[{app}] VirusTotal: no API key (set VT_API_KEY).")
                print(f"[{app}] VirusTotal: STOP - file not verified as clean. Please check manually:")
                print(f"  https://www.virustotal.com/gui/file/{actual_hash}")
                print(f"[{app}] aborted; verify on VirusTotal before proceeding.")
                return False
            elif vt_result is True:
                print(f"[{app}] VirusTotal: clean")
            else:
                print(f"[{app}] VirusTotal: MALICIOUS/SUSPICIOUS; aborting")
                print(f"  https://www.virustotal.com/gui/file/{actual_hash}")
                return False

        # extract
        extract_dir = td / "extracted"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)
        # find single top-level dir
        entries = [p for p in extract_dir.iterdir()]
        src = entries[0] if (len(entries) == 1 and entries[0].is_dir()) else extract_dir

        if not confirm(f"[{app}] install/update into {target}?", auto_yes):
            print(f"[{app}] aborted by user")
            return False

        backup = td / "backup"
        if target.exists():
            backup_portable_state(target, backup)
            # remove old target
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        # move extracted contents
        for item in src.iterdir():
            dest = target / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        # restore portable state (settings) from backup
        if backup.exists():
            restore_portable_state(target, backup)

        print(f"[{app}] installed {tag} -> {target}")
        try:
            create_shortcut(app, root)
        except Exception as e:
            print(f"[{app}] shortcut creation failed: {e}")
        return True


def cmd_list(root: Path):
    for app in APPS:
        target = root / app / f"{app}.exe"
        if target.is_file():
            cli = root / app / f"{app}-cli.exe"
            try:
                probe = cli if cli.is_file() else target
                out = subprocess.check_output([str(probe), "--version"], text=True, stderr=subprocess.DEVNULL, timeout=10).strip().splitlines()[0]
            except Exception:
                out = "(version unknown)"
            print(f"{app:10s} installed  {out}")
        else:
            print(f"{app:10s} not installed")


def _assoc_backup_key(ext: str) -> str:
    return "Software\\PortableCraft\\Backup\\" + ext.lstrip(".").replace(".", "_")


def _backup_previous(ext: str, prev: str | None):
    if not _WINREG_OK:
        return
    if not prev:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _assoc_backup_key(ext)) as k:
            winreg.SetValueEx(k, "ProgID", 0, winreg.REG_SZ, prev)
    except Exception:
        pass


def _restore_previous(ext: str) -> str | None:
    if not _WINREG_OK:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _assoc_backup_key(ext)) as k:
            return winreg.QueryValueEx(k, "ProgID")[0]
    except FileNotFoundError:
        return None
    except Exception:
        return None


def register_assoc(app: str, root: Path) -> bool:
    if not _WINREG_OK:
        print(f"[{app}] winreg unavailable (not Windows?)")
        return False
    exe = root / app / f"{app}.exe"
    if not exe.is_file():
        print(f"[{app}] not installed, skipping associations")
        return False
    progid = f"PortableCraft.{PASCAL[app]}"
    # Create ProgID
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{progid}") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"{PASCAL[app]} Document")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{progid}\\DefaultIcon") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{exe}",0')
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{progid}\\shell\\open\\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{exe}" "%1"')
    except Exception as e:
        print(f"[{app}] failed to create ProgID: {e}")
        return False

    for ext in FILE_ASSOC.get(app, []):
        # back up previous default handler
        prev = None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}") as k:
                prev = winreg.QueryValueEx(k, "")[0]
        except FileNotFoundError:
            prev = None
        except Exception:
            prev = None
        if prev and prev != progid:
            _backup_previous(ext, prev)
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, progid)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}\\OpenWithProgids") as k:
                winreg.SetValueEx(k, progid, 0, winreg.REG_NONE, b"")
        except Exception as e:
            print(f"[{app}] failed to register {ext}: {e}")
            continue
        print(f"[{app}] associated {ext} -> {progid}")
    return True


def unregister_assoc(app: str, root: Path) -> bool:
    if not _WINREG_OK:
        return False
    progid = f"PortableCraft.{PASCAL[app]}"
    for ext in FILE_ASSOC.get(app, []):
        try:
            restored = _restore_previous(ext)
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}", 0, winreg.KEY_SET_VALUE) as k:
                if restored:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, restored)
                else:
                    try:
                        winreg.DeleteValue(k, "")
                    except FileNotFoundError:
                        pass
            # remove from OpenWithProgids
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}\\OpenWithProgids", 0, winreg.KEY_SET_VALUE) as k:
                    try:
                        winreg.DeleteValue(k, progid)
                    except FileNotFoundError:
                        pass
            except FileNotFoundError:
                pass
            print(f"[{app}] unregistered {ext}")
        except Exception as e:
            print(f"[{app}] failed to unregister {ext}: {e}")
    # remove ProgID key tree
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{progid}\\shell\\open\\command")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{progid}\\shell\\open")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{progid}\\shell")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{progid}\\DefaultIcon")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{progid}")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[{app}] ProgID cleanup warning: {e}")
    return True


def _notify_shell():
    if not _WINREG_OK:
        return
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass


def cmd_assoc(root: Path, apps: list, remove: bool = False, yes: bool = False):
    if not _WINREG_OK:
        print("file associations require Windows (winreg unavailable)")
        return
    if not apps:
        apps = list(FILE_ASSOC.keys())
    apps = [a for a in apps if a in FILE_ASSOC]
    if not apps:
        print("no apps with file associations specified")
        return

    # only installed apps
    targets = []
    for app in apps:
        if (root / app / f"{app}.exe").is_file():
            targets.append(app)
        else:
            print(f"[{app}] not installed, skipping")
    if not targets:
        print("no installed apps to associate")
        return

    action = "unregister" if remove else "register"
    print(f"Will {action} file associations for: {', '.join(targets)}")
    for app in targets:
        print(f"  {PASCAL[app]}: {', '.join(FILE_ASSOC[app])}")
    if not remove:
        print("This changes per-user (HKCU) default open handlers. Existing handlers are backed up.")
    if not confirm("Continue?", yes):
        print("aborted")
        return
    for app in targets:
        if remove:
            unregister_assoc(app, root)
        else:
            register_assoc(app, root)
    _notify_shell()
    print("done (you may need to reopen Explorer windows)")


def start_menu_dir() -> Path:
    base = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "AppBox"
    base.mkdir(parents=True, exist_ok=True)
    return base


def create_shortcut(app: str, root: Path):
    exe = root / app / f"{app}.exe"
    if not exe.is_file():
        return False
    lnk = start_menu_dir() / f"{PASCAL[app]}.lnk"
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{str(lnk)}'); "
        f"$s.TargetPath = '{str(exe)}'; "
        f"$s.WorkingDirectory = '{str(root / app)}'; "
        f"$s.IconLocation = '{str(exe)},0'; "
        f"$s.Description = '{PASCAL[app]} portable app'; "
        "$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True)
    print(f"[{app}] shortcut -> {lnk}")
    return True


def cmd_run(app: str, root: Path):
    exe = root / app / f"{app}.exe"
    if not exe.is_file():
        print(f"{app} not installed; run install first")
        return False
    subprocess.Popen([str(exe)])
    print(f"launched {exe}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Install/update portable Crafting Apps")
    parser.add_argument("command", nargs="?", default="install", choices=["install", "update", "run", "list", "shortcuts", "assoc"])
    parser.add_argument("apps", nargs="*", help="subset of apps (default: all)")
    parser.add_argument("--root", type=Path, default=None, help="appbox root (default: script dir)")
    parser.add_argument("--yes", "-y", action="store_true", help="skip confirmation prompts")
    parser.add_argument("--skip-vt", action="store_true", help="skip the obligatory VirusTotal check (not recommended)")
    parser.add_argument("--remove", action="store_true", help="with 'assoc': unregister associations instead of registering")
    args = parser.parse_args()

    root = args.root if args.root else root_dir()
    root.mkdir(parents=True, exist_ok=True)
    vt_key = os.environ.get("VT_API_KEY")

    if args.command == "list":
        cmd_list(root)
        return
    if args.command == "shortcuts":
        for app in (args.apps if args.apps else APPS):
            if app in APPS:
                create_shortcut(app, root)
        return
    if args.command == "assoc":
        cmd_assoc(root, args.apps if args.apps else list(FILE_ASSOC.keys()), args.remove, args.yes)
        return
    if args.command == "run":
        if not args.apps:
            print("usage: run <app>")
            sys.exit(1)
        cmd_run(args.apps[0], root)
        return

    # VirusTotal check is obligatory. Ensure an API key is available.
    if not args.skip_vt and not vt_key:
        if args.yes:
            print("VirusTotal check is obligatory but VT_API_KEY is not set.")
            print("Get a free API key at https://www.virustotal.com/gui/my-apikey and set VT_API_KEY, or use --skip-vt to bypass.")
            sys.exit(1)
        else:
            print("VirusTotal API key not found (VT_API_KEY).")
            print("Get a free key at https://www.virustotal.com/gui/my-apikey")
            entered = input("Paste your VirusTotal API key (or leave blank to abort): ").strip()
            if entered:
                vt_key = entered
                os.environ["VT_API_KEY"] = entered
            else:
                print("Aborted. Set VT_API_KEY or use --skip-vt to bypass.")
                sys.exit(1)
    apps = args.apps if args.apps else APPS
    apps = [a for a in apps if a in APPS]
    if not apps:
        print("no valid apps specified")
        sys.exit(1)

    update_only = (args.command == "update")

    if not confirm(f"This will download and install/update {len(apps)} app(s) into {root}. Continue?", args.yes):
        print("aborted")
        sys.exit(0)

    ok = True
    for app in apps:
        if not install_one(app, root, args.yes, args.skip_vt, vt_key, update_only):
            ok = False
    cmd_list(root)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
