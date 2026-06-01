#!/bin/sh
set -e

CONFIG="${PYTTYD_CONFIG:-/data/config.json}"

if [ ! -f "$CONFIG" ]; then
  echo "Initializing pyttyd config at $CONFIG"
  pyttyd init --config "$CONFIG"
fi

exec "$@"
