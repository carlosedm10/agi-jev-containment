#!/bin/sh
# Squid basic_auth helper: validates "user token" credentials against a flat
# tokens file ("user:token" per line, path as argv[1]). Revoking a run's egress
# is deleting its line — no restart needed once the credential TTL lapses.
TOKENS=${1:-/proxy/tokens}
while read -r user pass; do
  if grep -qxF "$user:$pass" "$TOKENS" 2>/dev/null; then
    echo OK
  else
    echo ERR
  fi
done
