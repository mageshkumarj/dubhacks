import logging
import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from .body_limit import BodyLimitMiddleware
from .config import API_VERSION, db_path
from .db import connect
from .envelope import STUB_HEADERS, fail, ok
from .errors import DomainError
from .routers import commerce_cart, commerce_catalog, customer, personas

log = logging.getLogger("sandbox.api")

DESCRIPTION = (
    "**STUB DATA ONLY.** Mock T-Mobile commerce and customer-context platform for the hackathon. "
    "Every SKU, price, customer and promotion is synthetic and is not an official offer."
)

app = FastAPI(
    title="T-Mobile Hackathon Sandbox API", version=API_VERSION, description=DESCRIPTION,
    redirect_slashes=False,  # an empty path value must answer with the standard error envelope, not a redirect
)
app.include_router(customer.router)
app.include_router(commerce_catalog.router)
app.include_router(commerce_cart.router)
app.include_router(personas.router)


MAX_BODY_BYTES = 65_536


app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_BODY_BYTES)


@app.middleware("http")
async def mark_stub_data(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Data-Source"] = "stub"
    return response


# Registered last so it is the outermost middleware: browser apps get CORS headers even on 4xx/413 responses.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Data-Source"],
)


READY_KEYS = ("data_source", "schema_version", "as_of", "content_sha256")


@app.exception_handler(sqlite3.Error)
async def dataset_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
    log.error("dataset error on %s: %s", request.url.path, type(exc).__name__)
    message = "Dataset not available. Run: python -m datagen"
    return JSONResponse(status_code=503, content=fail(message, "DATASET_UNAVAILABLE"), headers=STUB_HEADERS)


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=fail(exc.message, exc.code), headers=STUB_HEADERS)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=fail(str(exc.detail), f"HTTP_{exc.status_code}"))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", ()))
    message = f"{where}: {first.get('msg', 'invalid input')}"
    return JSONResponse(status_code=422, content=fail(message, "VALIDATION_ERROR"))


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500, content=fail("Internal server error", "INTERNAL_ERROR"), headers=STUB_HEADERS
    )


@app.get("/health", tags=["platform"])
def health() -> dict:
    return ok({"status": "up", "version": API_VERSION})


def _read_metadata() -> dict[str, str]:
    conn = connect(db_path())
    try:
        return dict(conn.execute("SELECT key, value FROM metadata").fetchall())
    finally:
        conn.close()


@app.get("/ready", tags=["platform"], response_model=None)
def ready() -> dict | JSONResponse:
    try:
        meta = _read_metadata()
    except sqlite3.Error:
        meta = {}
    if "data_source" not in meta:
        return JSONResponse(
            status_code=503,
            content=fail("Dataset not available. Run: python -m datagen", "DATASET_UNAVAILABLE"),
        )
    return ok({"status": "ready", "dataset": {k: meta[k] for k in READY_KEYS if k in meta}})
