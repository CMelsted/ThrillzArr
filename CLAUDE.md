# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ThrillzArr is a fork of [Bragibooks](https://github.com/djdembeck/bragibooks), a Django web app that's a frontend for `m4b-merge`: it lets a user pick audiobook folders/files, match them to an Audible ASIN via a metadata search API (default `https://api.audnex.us`), then merges/converts/tags them into a single `.m4b` in the background.

## Running locally

The `m4b_merge` Python package is **vendored** in this repo (top-level `m4b_merge/`, forked from upstream's last Python release `v0.5.3-python-final` before their Rust rewrite). Its Python deps are in `requirements.txt`, but the merge pipeline still shells out to external binaries (`m4b-tool`, `mp4chaps`, `ffmpeg`/`ffprobe`, `fdkaac`) which the Dockerfile installs — outside Docker those must be on PATH or merges fail at runtime (the app itself starts fine without them; `m4b_merge/config.py` only warns at import and `require_binaries()` raises at merge time).

Local vendored modifications (documented in `m4b_merge/__init__.py`): subprocesses run via `Popen(start_new_session=True)` exposing the process group id through `M4bMerge.on_subprocess_start` (used for job abandonment via `os.killpg`), and `run_merge()` is split into separately-callable stages (`prepare_data` → `prepare_command_args` → `merge` → `fix_chapters` → `move_completed_input`) so `utils/merge.py` can update progress and check cancellation between stages.

Build and run via Docker:

```bash
docker build . -f docker/Dockerfile -t thrillzarr:dev
docker run --rm -it -v /path/to/input:/input -v /path/to/output:/output -v /path/to/config:/config -p 8000:8000 thrillzarr:dev
```

`docker/entrypoint.sh` is the container's actual startup sequence: it fixes permissions for `UID`/`GID`, runs `manage.py migrate`, `manage.py collectstatic`, starts a Celery worker (`celery -A bragibooks_proj worker --concurrency ${CELERY_WORKERS:-1}`), then Gunicorn (`gunicorn bragibooks_proj.wsgi`). The Dockerfile builds from `python:3.12-alpine`, installing PHP/`m4b-tool`/ffmpeg/mp4v2/fdkaac directly (no dependency on the old `ghcr.io/djdembeck/m4b-merge` base image, whose upstream was rewritten in Rust and no longer ships the Python package).

`manage.py` has first-run bootstrap logic: if the config dir has no `secret_key.txt`, it generates one and runs `makemigrations`/`migrate` via `sys.executable`.

Once inside a working environment, standard Django commands apply:

```bash
python manage.py runserver 0.0.0.0:8000
python manage.py makemigrations importer
python manage.py migrate
python manage.py test importer
```

Note: `importer/tests.py` is currently an empty stub — there is no real test suite yet.

## Configuration

- `CONFIG_DIR` is `/config` if that directory exists (Docker), else `<repo>/config`. It holds `secret_key.txt` and the sqlite DB (`db.sqlite3`).
- App-level settings (API URL, input/output/completed directories, CPU count, output path scheme) are **not** environment variables — they're stored in the DB via the single `Setting` model row, edited through the `/setting` web page (`SettingView`/`SettingForm`). `utils/merge.set_configs()` reads that row into `m4b_merge.config` before every merge job.
- Environment variables that do matter: `DEBUG`, `LOG_LEVEL`, `CSRF_TRUSTED_ORIGINS`, `UID`/`GID`, `CELERY_WORKERS`, `BROKER_URL` (Celery broker; defaults to a `sqla+sqlite` broker pointed at the same sqlite DB).

## Architecture

Single Django app (`importer`) plus a thin project shell (`bragibooks_proj`):

- **`importer/models.py`** — `Book`, `Author`, `Narrator`, `Setting`, `ConversionPreset`, `Status`. `Book.status` is a `OneToOneField` to `Status` (`Pending Review`/`Processing`/`Done`/`Error`/`Abandoned`); `Author`/`Narrator` are `ManyToManyField`s to `Book`. `BookManager` holds `book_asin_validator`, not queryset logic. `ConversionPreset.save()` enforces exactly one `is_default=True` row.
- **`importer/views.py`** — the whole user flow lives here as class-based views, wired in `importer/urls.py`. The flow is **Import** (browse + match, one page) → **Review** (approve) → background processing:
  - `ImportView` (`/`) — a single page with two areas: a browsable tree of `input_dir()` (the deploy-time `/input` mount) where every row has an "Import" button, and a "match" area below listing whatever's currently in `request.session['input_dir']` with an ASIN select/Custom Search/Accept per entry plus an Accept All. Every interaction (`action=add|remove|accept`, default `accept`) POSTs back to this same view via `fetch()` and is applied to the DOM in place — the page never reloads on a single action, so matches already chosen for other entries survive. Accepting calls `utils.merge.create_book` (book lands in `Pending Review`, nothing enqueued yet); when the session list empties, redirects to `/review` if anything's pending. Tree rows for items currently in the session are rendered with `is-imported-hidden` (see `importer/static/css/` inline block in `importer.html`) rather than removed from the DOM, so removing an entry from the match area can reveal the same row again without re-rendering the tree. Non-AJAX POSTs (JS disabled) get a redirect+flash-message fallback instead of JSON.
  - `ReviewView` (`/review`) — approval stage: shows each pending book's fetched metadata as an editable `BookMetadataForm` plus a `ConversionPreset` dropdown; Approve/Approve All enqueues `m4b_merge_task` (storing the Celery task id on `Status.task_id`), Discard deletes the pending row.
  - `AsinSearch` (`/asin-search`) — JSON API backing the Import page's search UI; delegates to `utils/search_tools.py`.
  - `BookListView` (`/books`) — tabs of books by `Status` (done/processing/error/abandoned). The Processing tab polls `BookStatusView` (`/book/<id>/status`, JSON) every 3s from `book_tabs.js` to live-update progress bars. Done/Error/Abandoned tabs get a per-book "Clear Entry" button plus a tab-wide "Clear all", both silent (no confirmation, no flash message) — see `ClearJobsView`.
  - `AbandonJobView` (`/book/<id>/abandon`) — cancels an in-flight job: sets `Status.cancel_requested`, kills the recorded subprocess group (`os.killpg(Status.pgid, SIGTERM)`), best-effort Celery revoke. The task also re-checks the cancel flag between stages (don't rely on Celery revoke alone — the `sqla+sqlite` broker's control channel is unreliable).
  - `ClearJobsView` (`/books/clear`) — deletes a single Done/Error/Abandoned book (`book_id`) or every book of one status (`clear_all=<status>`); deleting the `Status` cascades to the `Book`. Never touches files on disk.
  - `EditBookView` (`/book/<id>/edit`) — post-completion metadata editing, reuses `BookMetadataForm`.
  - `PresetsView` (`/presets`) — CRUD for `ConversionPreset` (name, output path scheme). The default is set from a checkbox column in the preset list (`action=set_default`), not the edit form; deleting the last remaining preset is refused server-side.
  - `SettingView` (`/setting`) — single-row `Setting` CRUD (create-if-none-else-update, never more than one row): `api_url`, `num_cpus`, `delete_source_after_success` (default off). Input/output paths are NOT settings — they come from the deploy-time bind mounts (`/input`, `/output`, with `~/input`/`~/output` fallbacks outside Docker; see `utils/paths.py`). The settings page also hosts the client-side light/dark toggle.
- **`importer/tasks.py`** — one Celery task, `m4b_merge_task`, delegating to `utils.merge.run_m4b_merge`. This is where actual merge/convert/tag work happens asynchronously, writing progress back onto the `Book`'s `Status` row.
- **`utils/merge.py`** — bridges Django models to the vendored `m4b_merge` package. `run_m4b_merge()` drives the merge stage-by-stage, updating `Status.progress_percent`/`stage` and checking `cancel_requested` between stages; status writes use targeted `Status.objects.filter(...).update(...)` (never `status.save()`) so the abandon view's concurrent `cancel_requested` write is never clobbered by a stale in-memory object. `_apply_book_overrides()` pushes review-stage manual edits from the `Book` row back into the metadata dict so they end up in the tagged file. `_post_process()` handles preset-driven behavior: optional move into the Audiobookshelf library path and optional source deletion (falling back to the junk-dir move). `create_book`/`make_book_model`/`make_author_model`/`make_narrator_model` build DB rows from Audible API metadata, deduping authors/narrators by ASIN or first+last name.
- **`utils/search_tools.py`** — `SearchTool` builds/normalizes search queries and calls the metadata API (via `RegionTool` in `utils/region_tools.py` for region-specific URLs); `ScoreTool` ranks results by Levenshtein-distance similarity on title/author plus a language-match bonus, used to auto-suggest the best ASIN match.
- **`bragibooks_proj/`** — Django settings/urls/wsgi/celery app config. `celery.py` autodiscovers tasks only in `importer`. `importer/context_processors.py` injects the app version (`importer/version.py`) into every template context.
- Frontend is server-rendered Django templates (`importer/templates/*.html`) with small vanilla-JS files per page (`importer.js`, `book_tabs.js`) — no JS build step or frontend framework. These `.js` files are `{% include %}`d into a `{% block script %}`, so they're actually rendered as Django templates (can use `{% url %}`/`{% static %}` directly), not served as static assets.

## Conventions

- Commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) — enforced by CI (`.github/workflows/check-conventional-commits.yml`) and used to drive `release-please` versioning (`importer/version.py` / `CHANGELOG.md`).
- CI on PRs also just builds the Docker image (`.github/workflows/build-docker-image.yml`) — there is no lint/test gate currently wired up.
