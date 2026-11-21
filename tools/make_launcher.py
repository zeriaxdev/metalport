#!/usr/bin/env python3
"""Make a ported .app start by double-click: adds Contents/MacOS/launch (a shell script, set as CFBundleExecutable) that does what
tools/launch.sh does (Metal HUD, tweaks + Steam overlay injection, Steam app id, player log, first-run shader warm-up) and checks Steam:
  * Steam not running -> dialog, start Steam, wait for sign-in;
  * the game quits because Steam could not confirm ownership -> dialog saying so.
Metal HUD is off; Steam Launch Options `-hud` (or HUD=1 in the environment) turns it on.  Environment set by the caller wins
(tests can pass REPO_NO_ACTIVATE etc.; NO_OVERLAY=1 still works).
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
args=(); for a in "$@"; do [[ "$a" == -hud || "$a" == HUD=1 ]] && HUD=1 || args+=("$a"); done; set -- "${args[@]}"   # Steam Launch Options: -hud
[[ -n "$HUD" ]] && export MTL_HUD_ENABLED=1
export REPO_MOUSE_SCALE=${REPO_MOUSE_SCALE:-2.5}
INJ="$C/Plugins/repo_tweaks.dylib"; [[ -f "$INJ" ]] || INJ=""
OVL="$HOME/Library/Application Support/Steam/Steam.AppBundle/Steam/Contents/MacOS/gameoverlayrenderer.dylib"
[[ -z "$NO_OVERLAY" && -f "$OVL" ]] && INJ="${INJ:+$INJ:}$OVL"
[[ -n "$INJ" ]] && export DYLD_INSERT_LIBRARIES="$INJ"
LOGDIR="$HOME/Library/Logs/MacPorts-Unity"; mkdir -p "$LOGDIR"; export REPO_LOG="${REPO_LOG:-$LOGDIR/$EXE.log}"
[[ -f "$REPO_LOG" ]] && mv -f "$REPO_LOG" "${REPO_LOG%.log}.prev.log"
export OPUS_SHIM_LOG="${REPO_LOG%.log}.opus.log"
MARK="$HOME/Library/Application Support/MacPorts-Unity/$EXE-warmup-v1.done"
[[ "${WARMUP:-auto}" == "1" || ( "${WARMUP:-auto}" == "auto" && ! -f "$MARK" ) ]] && export REPO_WARMUP=1 REPO_WARMUP_MARK="$MARK"
start=$SECONDS; me=$$
( while kill -0 $me 2>/dev/null; do sleep 1; done                      # after the game exits: was it a Steam ownership/sign-in failure?
  if (( SECONDS - start < 180 )) && grep -qE 'Steam not initialized|SteamAPI_Init\(\) failed|SteamApi_Init failed|Steamworks failed' "$REPO_LOG" 2>/dev/null; then
    say "Steam couldn't confirm that the signed-in account owns $TITLE (Steam app $APPID). Sign in to Steam with the account that bought it, then try again." '"OK"' >/dev/null
  fi ) &!
exec "$C/MacOS/$EXE" -logfile "$REPO_LOG" "$@"
'''.replace('@EXE@', exe).replace('@APPID@', a.appid).replace('@TITLE@', title.replace('"', ''))
p = os.path.join(C, 'MacOS', 'launch'); open(p, 'w').write(script); os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
pl['CFBundleExecutable'] = 'launch'; pl['UnityPlayerExecutable'] = exe
if a.title: pl['CFBundleName'] = pl['CFBundleDisplayName'] = a.title
plistlib.dump(pl, open(info, 'wb'))
print(f'{a.app}: double-click launcher installed (game binary {exe}, Steam app {a.appid}); re-sign the app')
