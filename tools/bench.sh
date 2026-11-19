#!/bin/zsh
# Sample CPU / memory / GPU utilisation of a running game (same scene, same settings, same display for a fair comparison).
# usage: bench.sh <pattern matching the process command> [seconds=30] [label]
# Read FPS / GPU ms / resolution from the Metal HUD (MTL_HUD_ENABLED=1) while it runs; this adds CPU%, RSS and whole-GPU busy %.
PAT="$1"; SECS="${2:-30}"; LABEL="${3:-run}"; PID=$(pgrep -f "$PAT" | head -1); [[ -z "$PID" ]] && { echo "no process matches '$PAT'"; exit 1; }
cpu=0; gpu=0; n=0; rss=0
for i in $(seq 1 $SECS); do
  c=$(ps -o pcpu= -p $PID | tr -d ' '); r=$(ps -o rss= -p $PID | tr -d ' '); g=$(ioreg -r -d 1 -c AGXAccelerator 2>/dev/null | grep -o '"Device Utilization %"=[0-9]*' | head -1 | cut -d= -f2)
  [[ -z "$c" ]] && break; cpu=$(echo "$cpu + $c" | bc); gpu=$(echo "$gpu + ${g:-0}" | bc); rss=$r; n=$((n+1)); sleep 1
done
printf "%s: pid %s, %d samples, avg CPU %.0f%% (of one core), RSS %d MB, avg GPU busy %.0f%%\n" "$LABEL" "$PID" "$n" "$(echo "$cpu / $n" | bc -l)" "$((rss/1024))" "$(echo "$gpu / $n" | bc -l)"
