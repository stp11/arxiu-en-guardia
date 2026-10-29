import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqladmin import Admin

from admin import AdminAuth
from api.endpoints import router as api_router
from database import engine
from models import CategoryAdmin, EpisodeAdmin, WikipediaArticleAdmin

ADMIN_PATH = os.environ.get("ADMIN_PATH", "/admin")
ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY")
ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
# For origins that can't be listed ahead of time, like per-deploy previews.
# Compose passes an empty string when it's unset.
ORIGIN_REGEX = os.environ.get("ALLOWED_ORIGIN_REGEX") or None


def get_cloudflare_ip(request: Request):
    """Cloudflare's standard header for the real client IP"""
    return request.headers.get("cf-connecting-ip") or request.client.host


limiter = Limiter(key_func=get_cloudflare_ip, default_limits=["300/minute"])
app = FastAPI(
    docs_url="/api/docs",
    redoc_url=None,
    generate_unique_id_function=lambda route: route.name,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Strict, so a link on another site can't run admin actions, which are
# plain GETs, with the admin's session.
authentication_backend = AdminAuth(
    secret_key=ADMIN_SECRET_KEY, same_site="strict"
)
admin = Admin(
    app=app,
    engine=engine,
    authentication_backend=authentication_backend,
    base_url=ADMIN_PATH,
    templates_dir=str(Path(__file__).parent / "templates"),
)

admin.add_view(EpisodeAdmin)
admin.add_view(CategoryAdmin)
admin.add_view(WikipediaArticleAdmin)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_origin_regex=ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
add_pagination(app)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
