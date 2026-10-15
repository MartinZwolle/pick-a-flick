"""Small SQLite transactions shared by web workers and the offline command."""
import sqlite3
from contextlib import contextmanager

from app.config import get_data_dir


@contextmanager
def transaction():
    connection = sqlite3.connect(get_data_dir() / "pickaflick.db", timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        # Serialize credential changes, session validation and configuration writes.
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
