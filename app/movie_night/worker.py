"""One supervised background thread per web process; SQLite serializes delivery."""
import logging
import threading
from contextlib import asynccontextmanager

from app.movie_night.planning import deliver_one

logger = logging.getLogger(__name__)


def run(stop):
    while not stop.is_set():
        try:
            if deliver_one():
                continue
        except Exception:  # noqa: BLE001 - keep the worker alive; never expose provider secrets
            # Do not log exception values: provider URLs can contain credentials.
            logger.warning("Filmavondworker kon de wachtrij niet verwerken; probeert opnieuw.")
        stop.wait(5)


@asynccontextmanager
async def lifespan(app):
    stop = threading.Event()
    worker = threading.Thread(target=run, args=(stop,), daemon=True, name="filmavond-worker")
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join(timeout=12)
