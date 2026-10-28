#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/backend"
alembic upgrade head

uvicorn app.main:app &
api_pid=$!
faststream run app.consumer:app &
consumer_pid=$!

trap 'kill "$api_pid" "$consumer_pid" 2>/dev/null || true
wait "$api_pid" "$consumer_pid" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

wait "$api_pid" "$consumer_pid"
