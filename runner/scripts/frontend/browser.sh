#!/usr/bin/env bash
# macOS/Linux counterpart of browser.ps1: starts (or stops) the headed browser used
# for manual login, with remote debugging on the given port and a throwaway profile
# under the scratchpad. Uses Microsoft Edge if present, otherwise Google Chrome.
#   bash browser.sh start <url> <scratchpad> [port]                    fresh profile, user logs in by hand
#   bash browser.sh start-profile <url> <scratchpad> <port> <profile> [edge|chrome]
#                                                                      browser on a temporary copy of the user's real
#                                                                      profile (<profile> = "Default", "Profile 1", ...); default edge
#   bash browser.sh profiles [edge|chrome]                             list the browser's profile directories and names
#   bash browser.sh stop  <scratchpad>
# Chrome refuses --remote-debugging-port on its real user-data-dir, so start-profile copies only the
# login-bearing files (cookies, local/session storage, preferences) into <scratchpad>/pw-profile and
# runs the browser there with sync and extensions off. stop deletes that copy.
set -u
action="${1:-}"

if [ "$action" = "stop" ]; then
  scratch="${2:?scratchpad required}"
  pkill -f -- "--user-data-dir=$scratch/pw-profile" 2>/dev/null
  pkill -f "frontend/recorder.js" 2>/dev/null
  sleep 2
  rm -rf "$scratch/pw-profile"
  [ -e "$scratch/pw-profile" ] && echo "profile removed: false" || echo "profile removed: true"
  exit 0
fi

# Resolve user-data root and binary for the chosen browser ($1 = edge|chrome).
resolve_browser() {
  local which="${1:-edge}"
  case "$(uname)-$which" in
    Darwin-edge)   root="$HOME/Library/Application Support/Microsoft Edge"; bin="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" ;;
    Darwin-chrome) root="$HOME/Library/Application Support/Google/Chrome";  bin="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ;;
    *-edge)        root="$HOME/.config/microsoft-edge";                      bin="$(command -v microsoft-edge 2>/dev/null)" ;;
    *-chrome)      root="$HOME/.config/google-chrome";                       bin="$(command -v google-chrome 2>/dev/null)" ;;
    *) echo "unknown browser: $which (edge|chrome)"; exit 2 ;;
  esac
}

if [ "$action" = "profiles" ]; then
  resolve_browser "${2:-edge}"
  python3 - "$root" <<'PY'
import json, sys
info = json.load(open(sys.argv[1] + "/Local State"))["profile"]["info_cache"]
for key, v in info.items():
    print(f"{key} | {v.get('name')} | {v.get('user_name') or '-'}")
PY
  exit 0
fi

if [ "$action" = "start-profile" ]; then
  url="${2:?url required}"; scratch="${3:?scratchpad required}"; port="${4:?port required}"; profile="${5:?profile dir required}"
  resolve_browser "${6:-edge}"
  src="$root/$profile"
  [ -d "$src" ] || { echo "profile dir not found: $profile (run: browser.sh profiles ${6:-edge})"; exit 1; }
  [ -x "$bin" ] || { echo "browser not found: $bin"; exit 1; }
  dest="$scratch/pw-profile"
  rm -rf "$dest"; mkdir -p "$dest/$profile"
  cp "$root/Local State" "$dest/Local State"
  for item in Network "Local Storage" "Session Storage" Preferences "Secure Preferences" Cookies; do
    [ -e "$src/$item" ] && cp -R "$src/$item" "$dest/$profile/$item"
  done
  nohup "$bin" --remote-debugging-port="$port" --user-data-dir="$dest" --profile-directory="$profile" \
    --disable-sync --disable-extensions --no-first-run --no-default-browser-check "$url" >/dev/null 2>&1 &
  echo "started $url on port $port with a temporary copy of ${6:-edge} profile '$profile'"
  exit 0
fi

[ "$action" = "start" ] || { echo "usage: browser.sh start|start-profile|profiles|stop ..."; exit 2; }
url="${2:?url required}"; scratch="${3:?scratchpad required}"; port="${4:-9222}"

browser=""
for c in "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
         "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "$(command -v microsoft-edge 2>/dev/null)" "$(command -v google-chrome 2>/dev/null)"; do
  [ -n "$c" ] && [ -x "$c" ] && { browser="$c"; break; }
done
[ -n "$browser" ] || { echo "Edge/Chrome not found"; exit 1; }

nohup "$browser" --remote-debugging-port="$port" --user-data-dir="$scratch/pw-profile" \
  --no-first-run --no-default-browser-check "$url" >/dev/null 2>&1 &
echo "started $url on port $port using $(basename "$browser")"
