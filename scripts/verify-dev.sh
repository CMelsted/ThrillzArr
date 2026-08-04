#!/bin/sh
# Builds and boots the app from the local Dockerfile with throwaway volumes,
# then smoke-tests the pieces that can't be verified statically:
# runtime binaries, the vendored m4b_merge package, migrations (including
# the output_scheme -> default-preset data migration), and the web UI.
#
# To test the migrations against a COPY of your real database, point
# REAL_CONFIG at your live config dir first:
#   REAL_CONFIG=/appdata/bragibooks/config ./scripts/verify-dev.sh
set -e

cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.dev.yml"

mkdir -p dev-data/input dev-data/output dev-data/config

if [ -n "$REAL_CONFIG" ]; then
    echo "==> Copying real config from $REAL_CONFIG (originals untouched)"
    cp "$REAL_CONFIG"/db.sqlite3 dev-data/config/ 2>/dev/null || echo "    (no db.sqlite3 found there)"
    cp "$REAL_CONFIG"/secret_key.txt dev-data/config/ 2>/dev/null || true
fi

echo "==> Building and starting container"
$COMPOSE up -d --build

echo "==> Waiting for web server"
tries=0
until curl -sf -o /dev/null http://localhost:8000/setting; do
    tries=$((tries + 1))
    if [ "$tries" -gt 30 ]; then
        echo "FAIL: web server never came up; logs follow"
        $COMPOSE logs --tail 50
        exit 1
    fi
    sleep 2
done
echo "    OK: web server responds"

run() { docker exec thrillzarr-dev sh -c "$1"; }

echo "==> Checking runtime binaries"
run "m4b-tool --version" | head -1
run "mp4chaps --version 2>&1 | head -1" || true
run "ffprobe -version | head -1"
echo "    OK: binaries present"

echo "==> Checking vendored m4b_merge package"
run "cd /home/app/web && python -c 'import m4b_merge; print(\"m4b_merge\", m4b_merge.__version__)'"

echo "==> Checking migrations applied"
run "cd /home/app/web && python manage.py showmigrations importer" | tee /tmp/migrations.txt
if grep -q "\[ \]" /tmp/migrations.txt; then
    echo "FAIL: unapplied migrations above"
    exit 1
fi
echo "    OK: all migrations applied"

echo "==> Checking default preset exists (0007 data migration)"
run "cd /home/app/web && python manage.py shell -c '
from importer.models import ConversionPreset
p = ConversionPreset.objects.filter(is_default=True).first()
assert p, \"no default preset\"
print(\"default preset:\", p.name, \"->\", p.output_scheme)
'"

echo "==> Checking celery worker is up"
run "cd /home/app/web && celery -A bragibooks_proj inspect ping -t 10" | grep -q pong \
    && echo "    OK: worker responds" \
    || { echo "FAIL: celery worker not responding"; exit 1; }

echo ""
echo "All smoke tests passed."
echo "The app is running at http://localhost:8000 for the manual e2e walk:"
echo "  1. Settings -> save; Presets -> check the migrated default preset"
echo "  2. Put an audiobook folder in ./dev-data/input, then Import -> Match -> Review"
echo "  3. Edit metadata, approve; watch the progress bar on Books -> Processing"
echo "  4. Abandon a job mid-merge; verify 'ps aux' in the container shows no m4b-tool"
echo "  5. Clear Error/Abandoned jobs; toggle dark mode on each page"
echo ""
echo "Tear down with: $COMPOSE down"
