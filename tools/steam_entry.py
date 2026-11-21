#!/usr/bin/env python3
"""Optional: make Steam's own entry for a ported game show Play and start the Mac app.
(Generalised copy of buckshot-roulette/steam_entry.py: the game is chosen with --appid/--name/--exe.)

Steam lists the game as Windows-only. This adds a macOS launch option to the game
Roulette's record in Steam's local app cache, an install record, and a folder holding
a link to the app. Nothing else in Steam changes, and the game still checks ownership.
Steam must be closed. Steam may drop the button again when it refreshes the game's
data (for example after a game update); run `add` again then.

    python3 steam_entry.py --appid 3241660 --name "R.E.P.O." add [path/to/R.E.P.O.app]
    python3 steam_entry.py --appid 3241660 --name "R.E.P.O." remove
    python3 steam_entry.py --appid 3241660 --name "R.E.P.O." status
--name must equal Steam's name for the app; --exe defaults to the app's UnityPlayerExecutable / CFBundleExecutable.
"""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

APP_ID = 0
NAME = ""
EXE = ""
ARGS = ""
CLOUD = False
STEAM = Path.home() / "Library/Application Support/Steam"
DEFAULT_APP = FOLDER_NAME = LAUNCH_EXE = None


def configure(appid: int, name: str, exe: str = "", args: str = "") -> None:
    global APP_ID, NAME, EXE, ARGS, DEFAULT_APP, FOLDER_NAME, LAUNCH_EXE
    APP_ID, NAME, EXE, ARGS = appid, name, exe, args
    DEFAULT_APP = Path.home() / "Applications" / f"{NAME}.app"
    FOLDER_NAME = f"{NAME} Mac Port"
    LAUNCH_EXE = f"{NAME}.app"


def exe_of(app: Path) -> str:
    if EXE:
        return EXE
    import plistlib
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    return info.get("UnityPlayerExecutable") or info["CFBundleExecutable"]
MAGIC = 0x07564429  # appinfo.vdf format v41; anything else is refused unchanged


class SteamEntryError(ValueError):
    pass


def paths(steam: Path = STEAM) -> dict:
    return {
        "cache": steam / "appcache/appinfo.vdf",
        "manifest": steam / f"steamapps/appmanifest_{APP_ID}.acf",
        "folder": steam / "steamapps/common" / FOLDER_NAME,
        # Not in Caches: users are told they may delete that folder.
        "receipt": steam.parent / f"MacPorts-Unity/steam-entry-{APP_ID}.json",
    }


def steam_running() -> bool:
    return subprocess.run(["pgrep", "-x", "steam_osx"], capture_output=True).returncode == 0


# --- appinfo.vdf (binary KeyValues) -------------------------------------------------

def read_cache(path: Path):
    data = path.read_bytes()
    try:
        if struct.unpack_from("<II", data) != (MAGIC, 1):
            raise SteamEntryError("Steam's app cache has a format this version doesn't know; nothing changed")
        table, = struct.unpack_from("<Q", data, 8)
        count, = struct.unpack_from("<I", data, table)
        pos, strings = table + 4, []
        for _ in range(count):
            end = data.index(b"\0", pos)
            strings.append(data[pos:end].decode())
            pos = end + 1
        if pos != len(data):
            raise SteamEntryError("Unexpected data after Steam's string table; nothing changed")
        records, pos = [], 16
        while True:
            appid, = struct.unpack_from("<I", data, pos)
            if appid == 0:
                break
            size, = struct.unpack_from("<I", data, pos + 4)
            end = pos + 8 + size
            if size < 60 or end > table:
                raise SteamEntryError("Damaged record in Steam's app cache; nothing changed")
            records.append((appid, data[pos:end]))
            pos = end
        if pos + 4 != table:
            raise SteamEntryError("Unexpected layout in Steam's app cache; nothing changed")
    except SteamEntryError:
        raise
    except (struct.error, ValueError, UnicodeDecodeError) as error:
        raise SteamEntryError(f"Can't read Steam's app cache ({error}); nothing changed") from None
    return data, strings, records


def parse(payload: bytes, strings: list) -> dict:
    def obj(pos, depth=0):
        if depth > 64:
            raise SteamEntryError("App record nests too deeply")
        values = {}
        while True:
            kind = payload[pos]
            pos += 1
            if kind == 8:
                return values, pos
            key = strings[struct.unpack_from("<I", payload, pos)[0]]
            pos += 4
            if key in values:
                raise SteamEntryError("Duplicate key in app record")
            if kind == 0:
                value, pos = obj(pos, depth + 1)
            elif kind == 1:
                end = payload.index(b"\0", pos)
                value, pos = payload[pos:end].decode(), end + 1
            elif kind in (2, 3, 4, 6, 7, 10):
                size = 8 if kind in (7, 10) else 4
                value, pos = payload[pos:pos + size], pos + size
                if len(value) != size:
                    raise SteamEntryError("Truncated app record")
            else:
                raise SteamEntryError(f"Unknown value type {kind} in app record")
            values[key] = (kind, value)
    try:
        tree, pos = obj(0)
    except SteamEntryError:
        raise
    except (IndexError, ValueError, struct.error, UnicodeDecodeError):
        raise SteamEntryError("Damaged app record; nothing changed") from None
    if pos != len(payload):
        raise SteamEntryError("Unexpected data after app record; nothing changed")
    return tree


def encode(tree: dict, strings: list) -> bytes:
    index = {key: i for i, key in enumerate(strings)}

    def obj(values):
        out = bytearray()
        for key, (kind, value) in values.items():
            if key not in index:
                index[key] = len(strings)
                strings.append(key)
            out += bytes([kind]) + struct.pack("<I", index[key])
            out += obj(value) if kind == 0 else (value.encode() + b"\0" if kind == 1 else value)
        return out + b"\x08"
    return bytes(obj(tree))


def load(cache: Path):
    data, strings, records = read_cache(cache)
    raw = next((raw for appid, raw in records if appid == APP_ID), None)
    if raw is None:
        raise SteamEntryError(f"Steam has no data for {NAME} yet. Open its page in Steam once, quit Steam, then try again")
    if hashlib.sha1(raw[68:]).digest() != raw[48:68]:
        raise SteamEntryError(f"{NAME}'s cached record doesn't match its checksum; nothing changed")
    tree = parse(raw[68:], strings)
    if encode(tree, list(strings)) != raw[68:]:
        raise SteamEntryError("Can't reproduce Steam's record exactly; nothing changed")
    try:
        if tree["appinfo"][1]["common"][1]["name"][1] != NAME:
            raise KeyError
        tree["appinfo"][1]["config"][1]["launch"][1]
    except (KeyError, TypeError):
        raise SteamEntryError("Unexpected app record layout; nothing changed") from None
    return data, strings, records, raw, tree


def save(cache: Path, data: bytes, strings: list, records: list, raw: bytes, tree: dict) -> None:
    strings = list(strings)
    payload = encode(tree, strings)
    record = bytearray(raw[:68])
    struct.pack_into("<I", record, 4, 60 + len(payload))
    record[48:68] = hashlib.sha1(payload).digest()
    record += payload
    out = bytearray(data[:16]) + b"".join(bytes(record) if appid == APP_ID else r for appid, r in records) + struct.pack("<I", 0)
    struct.pack_into("<Q", out, 8, len(out))
    out += struct.pack("<I", len(strings)) + b"".join(s.encode() + b"\0" for s in strings)
    # Re-read the result before replacing: every other game's record must be byte-identical.
    temp = cache.with_name(cache.name + ".buckshot-mac.tmp")
    temp.write_bytes(out)
    try:
        _, _, new_records = read_cache(temp)
        if [a for a, _ in new_records] != [a for a, _ in records] or any(
                before != after for (appid, before), (_, after) in zip(records, new_records) if appid != APP_ID):
            raise SteamEntryError("Another game's record would change; nothing changed")
        if cache.read_bytes() != data:
            raise SteamEntryError("Steam changed its cache meanwhile; nothing changed")
        temp.replace(cache)
    finally:
        if temp.exists():
            temp.unlink()


# --- add / remove --------------------------------------------------------------------

def ours(entry) -> bool:
    values = entry[1] if entry[0] == 0 else {}
    config = values.get("config", (0, {}))[1]
    return values.get("executable", (1, ""))[1] == LAUNCH_EXE and config.get("oslist", (1, ""))[1] == "macos"


def app_archs(app: Path) -> set:
    result = subprocess.run(["lipo", "-archs", str(app / f"Contents/MacOS/{exe_of(app)}")], capture_output=True, text=True)
    return set(result.stdout.split())


def cloud_overrides(app_tree: dict, bundle_id: str) -> dict:
    """Steam Auto-Cloud rules for the Mac app: each Windows save root becomes ~/Library/Application Support/<bundle id>
    (a Unity Mac player keeps persistentDataPath there), replacing the leading "<Company>/<Product>" of each save path.
    Same shape as Mac releases use (e.g. Papers, Please: root/os/oscompare/useinstead/pathtransforms)."""
    ufs = app_tree.get("ufs", (0, {}))[1]
    out = {}
    for _, (_t, rule) in ufs.get("savefiles", (0, {}))[1].items():
        root, path = rule.get("root", (1, ""))[1], rule.get("path", (1, ""))[1]
        if not root.startswith("WinAppData") or path.count("/") < 1 or root in out:
            continue
        find = "/".join(path.split("/")[:2])
        out[root] = (0, {"os": (1, "macos"), "oscompare": (1, "="), "root": (1, root), "useinstead": (1, "MacAppSupport"),
                         "pathtransforms": (0, {"1": (0, {"find": (1, find), "replace": (1, bundle_id)})})})
    return out


def installed_depots(depots: dict) -> dict:
    """Depots without an OS restriction now also apply to macOS: record them as installed at the public manifest,
    or Steam marks the app "Update Required" and downloads the Windows files on the first Play."""
    out = {}
    for key, (_, depot) in depots.items():
        if not key.isdigit() or not isinstance(depot, dict):
            continue
        config = depot.get("config", (0, {}))[1]
        oslist = config.get("oslist", (1, ""))[1] if isinstance(config, dict) else ""
        gid = depot.get("manifests", (0, {}))[1].get("public", (0, {}))[1]
        gid = gid.get("gid", (1, ""))[1] if isinstance(gid, dict) else gid
        if gid and (not oslist or "macos" in oslist):
            out[key] = gid
    return out


def manifest_text(buildid: int, depots: dict | None = None) -> str:
    fields = {"appid": APP_ID, "Universe": 1, "name": NAME, "StateFlags": 4, "installdir": FOLDER_NAME,
              "buildid": buildid, "LastUpdated": int(time.time()), "SizeOnDisk": 0, "UpdateResult": 0, "AutoUpdateBehavior": 1}
    text = '"AppState"\n{\n' + "".join(f'\t"{k}"\t\t"{v}"\n' for k, v in fields.items())
    if depots:
        text += '\t"InstalledDepots"\n\t{\n' + "".join(f'\t\t"{d}"\n\t\t{{\n\t\t\t"manifest"\t\t"{g}"\n\t\t\t"size"\t\t"0"\n\t\t}}\n' for d, g in depots.items()) + "\t}\n"
    return text + "}\n"


def our_manifest(path: Path) -> bool:
    return path.is_file() and f'"installdir"\t\t"{FOLDER_NAME}"' in path.read_text(errors="replace")


def read_receipt(path: Path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {"oslist": False, "osextended": []}


def add(app: Path = DEFAULT_APP, steam: Path = STEAM) -> str:
    p = paths(steam)
    app = app.expanduser().resolve()
    if not (app / f"Contents/MacOS/{exe_of(app)}").is_file():
        raise SteamEntryError(f"No built app at {app}; run the installer first")
    if steam_running():
        raise SteamEntryError("Quit Steam completely first (Steam → Quit Steam); nothing changed")
    if p["manifest"].exists() and not our_manifest(p["manifest"]):
        raise SteamEntryError(f"Steam already lists another {NAME} install on this Mac; nothing changed")
    link = p["folder"] / LAUNCH_EXE
    if link.exists() and not link.is_symlink():
        raise SteamEntryError(f"{link} is not this installer's link; nothing changed")
    data, strings, records, raw, tree = load(p["cache"])
    app_tree = tree["appinfo"][1]
    common, launch = app_tree["common"][1], app_tree["config"][1]["launch"][1]
    receipt = read_receipt(p["receipt"])

    oslist = [s for s in common.get("oslist", (1, ""))[1].split(",") if s]
    if "macos" not in oslist:
        common["oslist"] = (1, ",".join(oslist + ["macos"]))
        receipt["oslist"] = True
    # Only claim what the binary really contains; no Apple notarization claim.
    if "osextended" not in common:
        receipt["osextended_created"] = True
    flags = [s for s in common.get("osextended", (1, ""))[1].split(",") if s]
    for flag in ["macos64"] + (["macosapplesilicon"] if "arm64" in app_archs(app) else []):
        if flag not in flags:
            flags.append(flag)
            receipt["osextended"].append(flag)
    common["osextended"] = (1, ",".join(flags))
    if CLOUD:                                                   # Steam Cloud for the native saves (receipt-tracked)
        import plistlib
        bundle = plistlib.loads((app / "Contents/Info.plist").read_bytes())["CFBundleIdentifier"]
        ufs = app_tree.setdefault("ufs", (0, {}))[1]
        ro = ufs.setdefault("rootoverrides", (0, {}))[1]
        for k in receipt.get("cloud_keys", []): ro.pop(k, None)
        receipt["cloud_keys"] = []
        for i, rule in enumerate(cloud_overrides(app_tree, bundle).values()):
            k = f"mp{i}"; ro[k] = rule; receipt["cloud_keys"].append(k)
    for key in [k for k, entry in launch.items() if ours(entry)]:   # re-add fresh: picks up a new label / arguments
        del launch[key]
    launch[str(max(map(int, launch), default=-1) + 1)] = (0, {
        "executable": (1, LAUNCH_EXE),
        "description": (1, f"Play {NAME} Metal (Unofficial)"),
        **({"arguments": (1, ARGS)} if ARGS else {}),
        "config": (0, {"oslist": (1, "macos"), "osarch": (2, struct.pack("<I", 64))}),
    })
    receipt.setdefault("windows_only", [])
    for key, (_t, entry) in launch.items():                     # an .exe entry with no OS limit shows on Mac too: limit it to Windows
        if ours((_t, entry)) or not entry.get("executable", (1, ""))[1].lower().endswith(".exe"): continue
        cfg = entry.setdefault("config", (0, {}))[1]
        if "oslist" not in cfg:
            cfg["oslist"] = (1, "windows"); receipt["windows_only"].append(entry["executable"][1])
    changed = encode(tree, list(strings)) != raw[68:]
    if changed:
        save(p["cache"], data, strings, records, raw, tree)

    p["receipt"].parent.mkdir(parents=True, exist_ok=True)
    p["receipt"].write_text(json.dumps(receipt, indent=2) + "\n")
    buildid = struct.unpack("<I", app_tree["depots"][1]["branches"][1]["public"][1]["buildid"][1])[0]
    p["manifest"].write_text(manifest_text(buildid, installed_depots(app_tree["depots"][1])))
    p["folder"].mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()
    link.symlink_to(app, target_is_directory=True)
    return "Play button added" if changed else "Play button was already there; link updated"


def remove(steam: Path = STEAM) -> str:
    p = paths(steam)
    if steam_running():
        raise SteamEntryError("Quit Steam completely first (Steam → Quit Steam); nothing changed")
    receipt = read_receipt(p["receipt"])
    if p["cache"].is_file():
        data, strings, records, raw, tree = load(p["cache"])
        common, launch = tree["appinfo"][1]["common"][1], tree["appinfo"][1]["config"][1]["launch"][1]
        for key in [k for k, entry in launch.items() if ours(entry)]:
            del launch[key]
        for _, entry in launch.values():
            cfg = entry.get("config", (0, {}))[1]
            if entry.get("executable", (1, ""))[1] in receipt.get("windows_only", []) and cfg.get("oslist", (1, ""))[1] == "windows":
                del cfg["oslist"]
                if not cfg: del entry["config"]
        ro = tree["appinfo"][1].get("ufs", (0, {}))[1].get("rootoverrides", (0, {}))[1]
        for k in receipt.get("cloud_keys", []): ro.pop(k, None)
        if receipt["oslist"] and "oslist" in common:
            common["oslist"] = (1, ",".join(s for s in common["oslist"][1].split(",") if s and s != "macos"))
        if "osextended" in common:
            kept = [s for s in common["osextended"][1].split(",") if s and s not in receipt["osextended"]]
            if kept or not receipt.get("osextended_created"):
                common["osextended"] = (1, ",".join(kept))
            else:
                del common["osextended"]
        if encode(tree, list(strings)) != raw[68:]:
            save(p["cache"], data, strings, records, raw, tree)
    if our_manifest(p["manifest"]):
        p["manifest"].unlink()
    link = p["folder"] / LAUNCH_EXE
    if link.is_symlink():
        link.unlink()
    if p["folder"].is_dir() and not any(p["folder"].iterdir()):
        p["folder"].rmdir()
    if p["receipt"].is_file():
        p["receipt"].unlink()
    return "Play button removed; Steam shows Install again"


def status(steam: Path = STEAM) -> str:
    p = paths(steam)
    try:
        *_, tree = load(p["cache"])
    except (SteamEntryError, OSError):
        return "unknown (can't read Steam's app cache)"
    launch = tree["appinfo"][1]["config"][1]["launch"][1]
    link = p["folder"] / LAUNCH_EXE
    if any(ours(e) for e in launch.values()) and our_manifest(p["manifest"]) and link.exists():
        return f"on: Play starts {link.resolve()}"
    return "off"


def main(argv: list) -> int:
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--appid", type=int, required=True); ap.add_argument("--name", required=True); ap.add_argument("--exe", default=""); ap.add_argument("--args", default="", help="launch arguments Steam passes to the app"); ap.add_argument("--cloud", action="store_true", help="also map Steam Cloud saves to ~/Library/Application Support/<bundle id>")
    ap.add_argument("rest", nargs="*"); a = ap.parse_args(argv[1:]); configure(a.appid, a.name, a.exe, a.args); globals()["CLOUD"] = a.cloud; argv = [argv[0]] + a.rest
    command = argv[1] if len(argv) > 1 else "status"
    try:
        if command == "add":
            print(add(Path(argv[2]) if len(argv) > 2 else DEFAULT_APP) + ". Reopen Steam.")
        elif command == "remove":
            print(remove() + ". Reopen Steam.")
        elif command == "status":
            print(status())
        else:
            print(__doc__)
            return 2
    except SteamEntryError as error:
        print(f"Stopped: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
