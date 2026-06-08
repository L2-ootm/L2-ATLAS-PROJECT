"""Tests for atlas_wiki.provenance_service (06-04).

Covers write_provenance and get_provenance primitives that every wiki update
calls to record memory layer writes per D-019.
"""

import sqlite3
import threading

import pydantic
import pytest

from atlas_wiki.provenance_service import get_provenance, write_provenance
from atlas_core.schemas.core import MemoryProvenance


def test_write_provenance_creates_row(db: sqlite3.Connection, lock: threading.Lock) -> None:
    """write_provenance returns MemoryProvenance and inserts exactly one DB row."""
    item_id = "wiki-page-001"

    result = write_provenance(db, lock, layer="WIKI", item_id=item_id)

    assert isinstance(result, MemoryProvenance)
    assert result.item_id == item_id

    cursor = db.execute("SELECT COUNT(*) FROM memory_provenance WHERE item_id=?", (item_id,))
    count = cursor.fetchone()[0]
    assert count == 1


def test_write_provenance_fields(
    db: sqlite3.Connection, lock: threading.Lock, run_id: str
) -> None:
    """Row in DB has correct layer, item_id, and run_id after write_provenance."""
    item_id = "wiki-page-fields-test"

    write_provenance(db, lock, layer="WIKI", item_id=item_id, run_id=run_id)

    cursor = db.execute(
        "SELECT layer, item_id, run_id FROM memory_provenance WHERE item_id=?",
        (item_id,),
    )
    row = cursor.fetchone()
    assert row is not None
    layer_val, item_id_val, run_id_val = row
    assert layer_val == "WIKI"
    assert item_id_val == item_id
    assert run_id_val == run_id


def test_get_provenance_returns_records(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    """get_provenance returns list[MemoryProvenance] with correct data after write."""
    item_id = "wiki-page-read-back"

    write_provenance(db, lock, layer="WIKI", item_id=item_id, sensitivity="internal")

    records = get_provenance(db, item_id)

    assert isinstance(records, list)
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, MemoryProvenance)
    assert record.item_id == item_id
    assert record.layer == "WIKI"
    assert record.sensitivity == "internal"


def test_write_provenance_invalid_layer(
    db: sqlite3.Connection, lock: threading.Lock
) -> None:
    """write_provenance with invalid layer raises pydantic.ValidationError, not a DB error."""
    with pytest.raises(pydantic.ValidationError):
        write_provenance(db, lock, layer="INVALID", item_id="some-page")

    # Verify no partial row was inserted
    cursor = db.execute("SELECT COUNT(*) FROM memory_provenance")
    assert cursor.fetchone()[0] == 0
