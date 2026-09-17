"""Orders API with a hand-rolled throttling middleware."""

import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from project.components.orders.endpoints import router as orders_router

app = FastAPI(title="orders-api")
app.include_router(orders_router)

_HITS: dict[str, list[float]] = {}
_LIMIT = 5
_WINDOW = 60.0


@app.middleware("http")
async def throttle(request: Request, call_next):
    key = request.client.host if request.client else "anonymous"
    now = time.monotonic()
    hits = [moment for moment in _HITS.get(key, []) if now - moment < _WINDOW]
    if len(hits) >= _LIMIT:
        return JSONResponse({"detail": "too many requests"}, status_code=429)
    hits.append(now)
    _HITS[key] = hits
    return await call_next(request)
