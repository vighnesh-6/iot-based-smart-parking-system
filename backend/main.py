"""Run with: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import sqlite3

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.config import DEVICES, Settings
from backend.db import Database, statistics
from backend.mqtt_ingest import Ingestor
from backend.schemas import HistoryPage, SlotStatus, State, Statistics


def create_app(settings=None, *, topics=None):
    @asynccontextmanager
    async def lifespan(app):
        configured = settings or Settings.from_env()
        database = Database(configured.database_path, configured.database_timeout)
        await run_in_threadpool(database.initialize)
        ingestor = Ingestor(configured, database, topics=topics)
        app.state.database, app.state.ingestor, app.state.settings = database, ingestor, configured
        ingestor.start()
        try:
            yield
        finally:
            await run_in_threadpool(ingestor.stop)

    app = FastAPI(title="Smart Parking API", version="2.0.0", lifespan=lifespan)

    @app.exception_handler(sqlite3.Error)
    async def database_error(_request, _error):
        return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})

    @app.get("/slots", response_model=list[SlotStatus])
    def slots():
        return app.state.database.current(app.state.settings.stale_seconds)

    @app.get("/slots/{slot_id}", response_model=SlotStatus)
    def slot(slot_id: str):
        for item in slots():
            if item["slot_id"] == slot_id:
                return item
        raise HTTPException(404, "Unknown parking slot")

    @app.get("/history", response_model=HistoryPage)
    def history(slot_id: str | None = None, device_id: str | None = None,
                state: State | None = None, since: datetime | None = None,
                until: datetime | None = None, limit: int = Query(100, ge=1, le=1000),
                offset: int = Query(0, ge=0)):
        if slot_id is not None and slot_id not in {s for slots_ in DEVICES.values() for s in slots_}:
            raise HTTPException(422, "Invalid slot filter")
        if device_id is not None and device_id not in DEVICES:
            raise HTTPException(422, "Invalid device filter")
        for value in (since, until):
            if value is not None and value.utcoffset() is None:
                raise HTTPException(422, "Time filters require a timezone")
        if since and until and since > until:
            raise HTTPException(422, "since must not be after until")
        def utc(value):
            return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z") if value else None
        return app.state.database.history(slot_id=slot_id, device_id=device_id, state=state,
            since=utc(since), until=utc(until), limit=limit, offset=offset)

    @app.get("/stats", response_model=Statistics)
    def stats():
        return statistics(slots())

    @app.get("/health")
    def health():
        try:
            database_ok = app.state.database.healthy()
        except (sqlite3.Error, OSError):
            database_ok = False
        mqtt = app.state.ingestor.snapshot()
        ready = database_ok and mqtt["worker_alive"] and not mqtt["database_error_active"] and not mqtt["worker_error_active"] and (
            not mqtt["enabled"] or (mqtt["connected"] and mqtt["subscribed"] and mqtt["network_alive"]))
        return JSONResponse(status_code=200 if ready else 503, content={
            "status": "ok" if ready else "degraded", "database_ok": database_ok, "mqtt": mqtt})

    return app


app = create_app()
