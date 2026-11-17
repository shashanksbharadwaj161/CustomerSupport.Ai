#!/usr/bin/env bash
# Test stub for cloudflared (the real tunnel cannot connect from the CI sandbox). Prints a quick-tunnel URL to stderr
# like cloudflared does, then stays up. With FAKE_CF_DROP_AFTER=N the FIRST run exits after N seconds (tunnel drop).
n_file="${FAKE_CF_STATE:-/tmp/fake_cf_runs}"; n=$(( $(cat "$n_file" 2>/dev/null || echo 0) + 1 )); echo $n > "$n_file"
echo "2026-11-17T00:00:00Z INF Requesting new quick Tunnel on trycloudflare.com..." >&2
echo "2026-11-17T00:00:01Z INF |  https://stub-run-$n-test.trycloudflare.com                    |" >&2
if [ "$n" = "1" ] && [ -n "${FAKE_CF_DROP_AFTER:-}" ]; then sleep "$FAKE_CF_DROP_AFTER"; echo "ERR connection lost" >&2; exit 1; fi
while true; do sleep 1; done
