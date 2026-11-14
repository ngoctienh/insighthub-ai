#!/usr/bin/env sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "${AUTO_SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed_demo_data || true
fi

exec gunicorn insighthub.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers ${WEB_CONCURRENCY:-2} \
  --timeout 120
