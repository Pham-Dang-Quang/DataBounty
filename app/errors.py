from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def register_error_handlers(app: FastAPI) -> None:
    def error_response(request: Request, status_code: int, message: str):
        wants_json = (
            request.url.path.startswith("/api/")
            or request.headers.get("content-type") == "application/json"
            or "text/html" not in request.headers.get("accept", "")
        )
        if wants_json:
            return JSONResponse({"error": {"code": status_code, "message": message}}, status_code)
        request.session["error_popup"] = message
        return RedirectResponse(_error_return_path(request), status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return error_response(request, exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(request: Request, exc: RequestValidationError):
        messages = [str(error.get("msg", "Invalid value")) for error in exc.errors()]
        message = "Invalid request: " + "; ".join(dict.fromkeys(messages))
        return error_response(request, 422, message)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, _exc: Exception):
        return error_response(request, 500, "An unexpected error occurred. Please try again.")


def _error_return_path(request: Request) -> str:
    referer = request.headers.get("referer", "")
    if referer:
        parsed = urlparse(referer)
        if parsed.netloc in {"", request.url.netloc} and parsed.path.startswith("/"):
            query = f"?{parsed.query}" if parsed.query else ""
            return f"{parsed.path}{query}"
    return "/"
