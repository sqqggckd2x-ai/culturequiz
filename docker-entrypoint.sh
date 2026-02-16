#!/usr/bin/env bash
set -e

# Wait for DB/Redis could be added here if needed
echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

echo "Starting Daphne..."
exec daphne -b 0.0.0.0 -p 8000 quiz_platform.asgi:application
