# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

美容室向けのAI画像変換Webアプリケーション。モデル・スタイリスト画像をVertex AI経由のGemini 2.5 Flash Imageモデルで高品質に変換します。

## Tech Stack

**DO NOT change these versions without approval:**
- Python 3.11+
- Django 5.0.x
- Celery 5.x with Redis 7
- Django Channels 4.x / Daphne (WebSocket support)
- PostgreSQL 14 (production) / SQLite (development fallback)
- Vertex AI: Gemini 2.5 Flash Image (`google-genai`, `google-cloud-aiplatform`)
- Docker / docker-compose

## Development Commands

### Local Development
```bash
# Start development server (includes WebSocket/ASGI support)
python manage.py runserver

# Database setup
python manage.py migrate
python manage.py createsuperuser

# Load prompt presets fixture
python manage.py loaddata images/fixtures/prompt_presets.json

# Celery worker (async task processing)
celery -A config worker -l info

# Celery beat (scheduled tasks - monthly usage reset)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Docker
```bash
# Start all services (web, db, redis, celery, celery-beat)
docker-compose up --build

# Services run on:
# - web: daphne on port 8000 (ASGI for HTTP + WebSocket)
# - db: PostgreSQL 14
# - redis: Redis 7 (Celery broker + Channels layer)
# - celery: worker process
# - celery-beat: scheduler process
```

### Testing
```bash
# Run all tests
python manage.py test

# Test Gemini API connection
python test_gemini_connection.py

# Smoke test for image conversion
python test_image_conversion.py
```

## Architecture Overview

### Django Apps Structure

**config/** - Project configuration
- `settings.py`: Django settings, Celery config, Channels config, Google Cloud credentials
- `urls.py`: Root URL routing (delegates to `api.urls`)
- `asgi.py`: ASGI application with WebSocket routing (`images.routing.websocket_urlpatterns`)
- `celery.py`: Celery app initialization

**accounts/** - User management
- `UserProfile` model: Extends Django User with `monthly_limit` and `monthly_usage` tracking
- Management command: `reset_monthly_usage` (scheduled via Celery Beat)
- Methods: `can_generate()`, `increment_usage()`, `remaining()`, `usage_percentage()`

**images/** - Core image conversion domain
- Models:
  - `ImageConversion`: Conversion job (status: pending/processing/completed/failed/cancelled)
  - `GeneratedImage`: Generated images with brightness adjustment, expiration tracking
  - `PromptPreset`: Preset prompts (category, prompt text, thumbnail)
  - `UserFavoritePrompt`: User's favorite presets
- Services (in `images/services/`):
  - `gemini_image_api.py`: `GeminiImageAPIService` - Vertex AI integration, image generation
  - `brightness.py`: Pillow-based brightness adjustment
  - `upload.py`: Image upload validation and processing
  - `scraper.py`: URL-based image scraping
- `tasks.py`: Celery tasks (`process_image_conversion_task`)
- `consumers.py`: WebSocket consumer for real-time progress notifications
- `routing.py`: WebSocket URL patterns (`ws/conversion/<conversion_id>/`)
- Management commands: Image cleanup, conversion status management

**api/** - REST API layer
- Views organized by domain (in `api/views/`):
  - `auth.py`: Login/logout, CSRF token, user info
  - `upload.py`: Image upload, validation, deletion
  - `scrape.py`: URL-based image scraping
  - `convert.py`: Start conversion, check status, cancel
  - `prompts.py`: List presets, get categories
  - `favorites.py`: Add/remove/list favorite prompts
  - `gallery.py`: List conversions, image details, download, brightness adjustment, deletion
  - `usage.py`: Usage summary and history
  - `health.py`: Health/readiness/liveness checks
- All endpoints prefixed with `/api/v1/`
- Standard response format: `{"status": "success|error", "message": "...", "data": {...}}`

### Key Architectural Patterns

**Image Conversion Flow:**
1. User uploads images via `/api/v1/upload/` → stored temporarily
2. User starts conversion via `/api/v1/convert/` → creates `ImageConversion` record
3. Celery task `process_image_conversion_task` executes asynchronously
4. Task calls `GeminiImageAPIService.generate_images_from_reference()`
5. Progress notifications sent via WebSocket (`ws/conversion/<id>/`)
6. Generated images saved as `GeneratedImage` records
7. User's `monthly_usage` incremented (respects `monthly_limit`)

**WebSocket Real-time Updates:**
- Client connects to `ws/conversion/<conversion_id>/`
- `ImageConversionConsumer` (Channels consumer) handles connection
- Celery task sends updates via `channel_layer.group_send()`
- Updates include: status changes, progress percentage, completion events

**Usage Tracking:**
- `UserProfile.monthly_usage` tracks generated image count
- `UserProfile.monthly_limit` defines maximum per month
- Celery Beat runs `reset_monthly_usage` command monthly
- Model multipliers in `images/tasks.py`: different models have different usage costs

**Gemini API Integration:**
- Uses Vertex AI SDK with service account credentials
- Project/location configured via environment variables
- Image generation with reference image + text prompt
- Automatic retry logic and error handling in `GeminiImageAPIService`

## Code Conventions

**IMPORTANT: Do not make unauthorized changes**
- Request approval for UI/UX changes (layout, colors, fonts, spacing)
- Request approval for tech stack version changes
- Only implement explicitly requested features

**Coding Style:**
- Japanese docstrings and comments for business logic
- Type hints in service layer (`images/services/*.py`)
- Standard Django signatures in views (no excessive type hints)
- Logger per module: `logger = logging.getLogger(__name__)`
- Model `Meta` with explicit `db_table`, `indexes`, `ordering`
- API responses use consistent JSON structure

**Django Models:**
- Business logic in model methods (e.g., `mark_as_processing()`, `mark_as_completed()`)
- Computed properties for derived values (e.g., `is_expired`, `remaining`)
- Use `@transaction.atomic` for multi-step operations
- Cache invalidation patterns (e.g., `UserProfile.invalidate_usage_cache()`)

**Service Layer:**
- Stateless service classes with dependency injection
- Explicit error classes (e.g., `GeminiImageAPIError`)
- Comprehensive logging (INFO for operations, ERROR for failures)
- Return typed results (use `Optional`, `List`, `Dict` type hints)

## Important Files

- `images/fixtures/prompt_presets.json`: Initial prompt presets (load with `loaddata`)
- `.env.example`: Environment variable template
- `docker-entrypoint.sh`: Docker initialization script
- `gunicorn.conf.py`: Production WSGI server config
- `docs/`: Requirements, API design, database design, implementation plans

## Environment Variables

Required environment variables (see `.env.example`):
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to GCP service account JSON
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_CLOUD_LOCATION`: Vertex AI location (typically "global")
- `DATABASE_*`: PostgreSQL connection (if using PostgreSQL)
- `REDIS_URL`: Redis connection URL
- `SECRET_KEY`: Django secret key
- `DEBUG`: Debug mode (False in production)
- `ALLOWED_HOSTS`: Comma-separated allowed hosts
- `CSRF_TRUSTED_ORIGINS`: Comma-separated trusted origins

## Testing Strategy

- Unit tests in each app's `tests.py`
- Integration tests for API endpoints
- Smoke tests for Gemini API connection
- Use Django's test client for API testing
- Mock Gemini API calls in unit tests to avoid costs

## Common Pitfalls

1. **Celery tasks not executing**: Ensure Redis is running and `celery worker` is started
2. **WebSocket connection fails**: Check ASGI server (daphne) is running, not WSGI (gunicorn)
3. **Gemini API errors**: Verify service account credentials and quota limits
4. **Monthly usage not resetting**: Ensure `celery beat` is running with DatabaseScheduler
5. **File upload issues**: Check `MEDIA_ROOT` permissions and `FILE_UPLOAD_MAX_MEMORY_SIZE`

## Debugging

- Django logs: `logs/django.log`
- Celery logs: Check celery worker console output
- WebSocket issues: Check browser console and `channels` logs
- Database queries: Enable Django debug toolbar or use `django-extensions` shell_plus
- Gemini API: Use `test_gemini_connection.py` to verify connectivity
