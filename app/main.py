from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# Retained as public compatibility imports for tests and small integrations.
from app.auth import hash_password
from app.blockchain import BlockchainService
from app.call_rules import format_token_amount, required_remaining_liability, unix_timestamp
from app.config import Settings, get_settings
from app.db import Database
from app.errors import register_error_handlers
from app.routes_accounts import register_routes as register_account_routes
from app.routes_call_create import register_routes as register_call_creation_routes
from app.routes_call_manage import register_routes as register_call_management_routes
from app.routes_community import register_routes as register_community_routes
from app.routes_contribution_actions import register_routes as register_contribution_actions
from app.routes_contribution_files import register_routes as register_contribution_files
from app.routes_funding import register_routes as register_funding_routes
from app.routes_review import register_routes as register_review_routes
from app.routes_submissions import register_routes as register_submission_routes

__all__ = ["create_app", "hash_password", "required_remaining_liability"]

ROUTE_REGISTRARS = (
    register_account_routes,
    register_call_creation_routes,
    register_call_management_routes,
    register_community_routes,
    register_funding_routes,
    register_submission_routes,
    register_review_routes,
    register_contribution_files,
    register_contribution_actions,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app_settings.ensure_directories()
    database = Database(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.create_tables()
        yield

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=app_settings.secret_key,
        https_only=app_settings.session_https_only,
        same_site="lax",
        max_age=60 * 60 * 8,
    )
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    templates = Jinja2Templates(directory="app/templates")
    templates.env.globals["format_token"] = format_token_amount
    templates.env.globals["unix_timestamp"] = unix_timestamp
    chain = BlockchainService(app_settings)

    app.state.settings = app_settings
    app.state.database = database
    app.state.chain = chain
    app.state.templates = templates

    for register_routes in ROUTE_REGISTRARS:
        register_routes(app, app_settings, database, chain)
    register_error_handlers(app)
    return app


app = create_app()
