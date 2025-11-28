## Deployment adjustments (March 2025)
- docker-compose.yml: web uses daphne ASGI; networks use long syntax with app-network alias style-ai-web; ALLOWED_HOSTS includes prod domain and internal hosts; no host ports in base.
- docker-compose.override.yml (gitignored) for local: ports 18002/15432/16379 and DEBUG=True overrides for web/db/redis.
- External docker network required: `docker network create app-network` (documented in docs/SETUP.md).
- WhiteNoise added; STATICFILES_STORAGE set only when DEBUG is False to avoid manifest errors in dev.
- Docs updated (docs/SETUP.md) with network creation and override sample.
