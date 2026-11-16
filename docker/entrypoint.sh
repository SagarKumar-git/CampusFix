#!/bin/sh
set -eu

# If arguments were provided (e.g. alembic upgrade head, python -m app.scripts.bootstrap_admin, sh), execute them directly
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

# Otherwise, execute the unified supervisor
exec python /app/entrypoint.py
