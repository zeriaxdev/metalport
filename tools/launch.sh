#!/bin/zsh
# Generic launcher.  usage: launch.sh <dir containing App.app> <AppName> [steam app id] [game args...]
# Sets the Metal HUD (HUD=1), the tweaks library (mouse scale, App Nap off, first-run shader warm-up), and the Steam overlay/app id when given.
DIR="$1"; NAME="$2"; APPID="$3"; shift 3 2>/dev/null; cd "$DIR" || exit 1
TWEAKS="$PWD/$NAME.app/Contents/Plugins/repo_tweaks.dylib"
[[ -n "$HUD" ]] && export MTL_HUD_ENABLED=1     # HUD=1 shows the Metal HUD (off by default)
export REPO_MOUSE_SCALE=${REPO_MOUSE_SCALE:-2.5}
OVERLAY=""; if [[ -n "$APPID" ]]; then
  export SteamAppId=$APPID SteamGameId=$APPID; STEAM_MACOS="$HOME/Library/Application Support/Steam/Steam.AppBundle/Steam/Contents/MacOS"
  [[ -z "$NO_OVERLAY" && -f "$STEAM_MACOS/gameoverlayrenderer.dylib" ]] && OVERLAY=":$STEAM_MACOS/gameoverlayrenderer.dylib"; fi
export DYLD_INSERT_LIBRARIES="$TWEAKS$OVERLAY"
# always keep the last run's log (and the Opus call log) so problems can be diagnosed after the fact
LOGDIR="$HOME/Library/Logs/MacPorts-Unity"; mkdir -p "$LOGDIR"; REPO_LOG="${REPO_LOG:-$LOGDIR/$NAME.log}"
[[ -f "$REPO_LOG" ]] && mv -f "$REPO_LOG" "${REPO_LOG%.log}.prev.log"
export REPO_LOG OPUS_SHIM_LOG="${REPO_LOG%.log}.opus.log"
MARK="$HOME/Library/Application Support/MacPorts-Unity/$NAME-warmup-v1.done"
if [[ "${WARMUP:-auto}" == "1" || ( "${WARMUP:-auto}" == "auto" && ! -f "$MARK" ) ]]; then export REPO_WARMUP=1 REPO_WARMUP_MARK="$MARK"; fi
exec "./$NAME.app/Contents/MacOS/$NAME" -logfile "$REPO_LOG" "$@"
