#!/usr/bin/env python3
"""Make a ported .app start by double-click: adds Contents/MacOS/launch (a shell script, set as CFBundleExecutable) that does what
tools/launch.sh does (Metal HUD, tweaks + Steam overlay injection, Steam app id, player log, first-run shader warm-up) and checks Steam:
  * Steam not running -> dialog, start Steam, wait for sign-in;
  * the game quits because Steam could not confirm ownership -> dialog saying so.
Metal HUD is off; Steam Launch Options `-hud` (or HUD=1 in the environment) turns it on. BepInEx mods load when tools/mods installed
them (~/Library/Application Support/metalport/mods/<bundle id>); if a mod manager (r2modmac) applied a BepInEx folder to the game's
Steam install folder, those mods are used instead, with the tools/mods BepInEx core. Mods load only when asked for: Steam Launch Options `-mods`, MP_MODS=1, or a mod
manager's `--doorstop-enable true`; a normal launch is vanilla.  Environment set by the caller wins
(tests can pass MP_NO_ACTIVATE etc.; NO_OVERLAY=1 still works).
usage: make_launcher.py <App.app> --appid <steam app id> [--title "Display Name"]   then re-sign the app."""
import argparse, os, plistlib, stat
ap = argparse.ArgumentParser(); ap.add_argument('app'); ap.add_argument('--appid', required=True); ap.add_argument('--title'); a = ap.parse_args()
C = os.path.join(a.app, 'Contents'); info = os.path.join(C, 'Info.plist'); pl = plistlib.load(open(info, 'rb'))
exe = pl['CFBundleExecutable'] if pl['CFBundleExecutable'] != 'launch' else pl['UnityPlayerExecutable']
title = a.title or pl.get('CFBundleDisplayName') or pl.get('CFBundleName') or exe
script = r'''#!/bin/zsh
# Double-click launcher (made by tools/make_launcher.py).  Starts the game the way tools/launch.sh does, and explains Steam problems.
C="${0:A:h:h}"; EXE="@EXE@"; APPID=@APPID@; TITLE="@TITLE@"
say() { osascript -e "display dialog \"$1\" with title \"$TITLE\" buttons {$2} default button 1 with icon caution" 2>/dev/null | sed 's/.*://'; }
STEAM_LOG="$HOME/Library/Application Support/Steam/logs/connection_log.txt"
if ! pgrep -x steam_osx >/dev/null; then
  [[ "$(say "$TITLE needs Steam running and signed in with the account that owns it." '"Start Steam", "Cancel"')" == "Start Steam" ]] || exit 0
  before=$(wc -l < "$STEAM_LOG" 2>/dev/null || echo 0); open -g -a Steam
  for i in {1..90}; do tail -n +$((before + 1)) "$STEAM_LOG" 2>/dev/null | grep -q 'Logged On' && break; sleep 1; done
  tail -n +$((before + 1)) "$STEAM_LOG" 2>/dev/null | grep -q 'Logged On' || { say "Steam didn't finish signing in. Sign in to Steam, then open $TITLE again." '"OK"' >/dev/null; exit 0; }
fi
export SteamAppId=$APPID SteamGameId=$APPID SteamOverlayGameId=$APPID SteamMetalHook=1
args=(); skip=0; for a in "$@"; do                      # Steam Launch Options: -hud, -mods (mods are off unless asked for)
  if (( skip )); then skip=0; [[ "$a" == true ]] && MP_MODS=1; continue; fi
  case "$a" in -hud|HUD=1) HUD=1;; -mods) MP_MODS=1;; -nomods) MP_NO_MODS=1;; --doorstop-enable|--doorstop-enabled) skip=1;; *) args+=("$a");; esac
done; set -- "${args[@]}"
[[ -n "$HUD" ]] && export MTL_HUD_ENABLED=1
export MP_MOUSE_SCALE=${MP_MOUSE_SCALE:-2.5}
INJ="$C/Plugins/metalport_tweaks.dylib"; [[ -f "$INJ" ]] || INJ=""
OVL="$HOME/Library/Application Support/Steam/Steam.AppBundle/Steam/Contents/MacOS/gameoverlayrenderer.dylib"
[[ -z "$NO_OVERLAY" && -f "$OVL" ]] && INJ="${INJ:+$INJ:}$OVL"
MODS="${MP_MODS_DIR:-$HOME/Library/Application Support/metalport/mods/$(/usr/bin/plutil -extract CFBundleIdentifier raw "$C/Info.plist")}"
ROOT="$MODS"                                                   # BepInEx: tools/mods folder, or a mod manager's (r2modmac) game folder
ACF="$HOME/Library/Application Support/Steam/steamapps/appmanifest_$APPID.acf"
if [[ -f "$ACF" ]]; then
  G="$HOME/Library/Application Support/Steam/steamapps/common/$(sed -n 's/.*"installdir"[[:space:]]*"\(.*\)"/\1/p' "$ACF")"
  [[ -d "$G/BepInEx/plugins" ]] && ROOT="$G"                   # mods applied there by r2modmac / r2modman-style managers
fi
if [[ -n "$MP_MODS" && -z "$MP_NO_MODS" && -f "$MODS/BepInEx/core/BepInEx.Preloader.dll" && -f "$MODS/libdoorstop.dylib" && -d "$ROOT/BepInEx" ]]; then
  if [[ "$ROOT" != "$MODS" ]] && ! cmp -s "$MODS/BepInEx/core/BepInEx.Preloader.dll" "$ROOT/BepInEx/core/BepInEx.Preloader.dll"; then
    rm -rf "$ROOT/BepInEx/core"; cp -R "$MODS/BepInEx/core" "$ROOT/BepInEx/core"   # use the Apple Silicon-fixed BepInEx core
  fi
  export DOORSTOP_ENABLED=1 DOORSTOP_TARGET_ASSEMBLY="$ROOT/BepInEx/core/BepInEx.Preloader.dll" DOORSTOP_IGNORE_DISABLED_ENV=0
  INJ="$MODS/libdoorstop.dylib${INJ:+:$INJ}"
fi
[[ -n "$INJ" ]] && export DYLD_INSERT_LIBRARIES="$INJ"
LOGDIR="$HOME/Library/Logs/metalport"; mkdir -p "$LOGDIR"; export MP_LOG="${MP_LOG:-$LOGDIR/$EXE.log}"
[[ -f "$MP_LOG" ]] && mv -f "$MP_LOG" "${MP_LOG%.log}.prev.log"
export OPUS_SHIM_LOG="${MP_LOG%.log}.opus.log"
MARK="$HOME/Library/Application Support/metalport/$EXE-warmup-v1.done"
[[ "${WARMUP:-auto}" == "1" || ( "${WARMUP:-auto}" == "auto" && ! -f "$MARK" ) ]] && export MP_WARMUP=1 MP_WARMUP_MARK="$MARK"
start=$SECONDS; me=$$
( while kill -0 $me 2>/dev/null; do sleep 1; done                      # after the game exits: was it a Steam ownership/sign-in failure?
  if (( SECONDS - start < 180 )) && grep -qE 'Steam not initialized|SteamAPI_Init\(\) failed|SteamApi_Init failed|Steamworks failed' "$MP_LOG" 2>/dev/null; then
    say "Steam couldn't confirm that the signed-in account owns $TITLE (Steam app $APPID). Sign in to Steam with the account that bought it, then try again." '"OK"' >/dev/null
  fi ) &!
exec "$C/MacOS/$EXE" -logfile "$MP_LOG" "$@"
'''.replace('@EXE@', exe).replace('@APPID@', a.appid).replace('@TITLE@', title.replace('"', ''))
p = os.path.join(C, 'MacOS', 'launch'); open(p, 'w').write(script); os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
pl['CFBundleExecutable'] = 'launch'; pl['UnityPlayerExecutable'] = exe; pl['MetalportSteamAppID'] = a.appid   # read by tools/steam-play
if a.title: pl['CFBundleName'] = pl['CFBundleDisplayName'] = a.title
plistlib.dump(pl, open(info, 'wb'))
print(f'{a.app}: double-click launcher installed (game binary {exe}, Steam app {a.appid}); re-sign the app')
