"""The database lives in the container's ephemeral filesystem and is snapshotted to object
storage after every write. These tests pin down the part that can lose or corrupt data: the
generation precondition that stops a stale instance from overwriting a newer snapshot.
"""

import pytest

from app.snapshot import DatabaseSnapshot, StaleSnapshotError
from tests.fakes import FakeObjectStore


@pytest.fixture
def db_file(tmp_path):
    path = tmp_path / "inventory.sqlite"
    path.write_bytes(b"version-1")
    return path


def test_restore_is_a_no_op_when_nothing_has_been_snapshotted_yet(tmp_path):
    """First ever boot: there is no object in the bucket and the app must still start."""
    store = FakeObjectStore()
    path = tmp_path / "inventory.sqlite"
    snapshot = DatabaseSnapshot(store, "db/inventory.sqlite", path)

    snapshot.restore()

    assert not path.exists()
    assert snapshot.generation is None


def test_save_then_restore_round_trips_the_file(tmp_path):
    store = FakeObjectStore()
    path = tmp_path / "inventory.sqlite"
    path.write_bytes(b"the database")
    DatabaseSnapshot(store, "db/inventory.sqlite", path).save()

    path.unlink()
    restored = DatabaseSnapshot(store, "db/inventory.sqlite", path)
    restored.restore()

    assert path.read_bytes() == b"the database"
    assert restored.generation is not None


def test_repeated_saves_from_one_instance_are_accepted(db_file):
    """The normal case: one writer, saving over and over as the owner adds items."""
    snapshot = DatabaseSnapshot(FakeObjectStore(), "db/inventory.sqlite", db_file)

    snapshot.save()
    first = snapshot.generation
    db_file.write_bytes(b"version-2")
    snapshot.save()

    assert snapshot.generation != first


def test_a_stale_instance_cannot_overwrite_a_newer_snapshot(tmp_path):
    """Cloud Run overlaps the old and new instance on every deploy. Without this guard the
    older one would silently clobber writes made by the newer one.
    """
    store = FakeObjectStore()
    old_path = tmp_path / "old.sqlite"
    new_path = tmp_path / "new.sqlite"
    old_path.write_bytes(b"from the old instance")

    old_instance = DatabaseSnapshot(store, "db/inventory.sqlite", old_path)
    old_instance.save()

    new_instance = DatabaseSnapshot(store, "db/inventory.sqlite", new_path)
    new_instance.restore()
    new_path.write_bytes(b"from the new instance")
    new_instance.save()

    old_path.write_bytes(b"the old instance writes again")
    with pytest.raises(StaleSnapshotError):
        old_instance.save()

    assert store.read("db/inventory.sqlite") == b"from the new instance"


def test_save_is_a_no_op_when_snapshotting_is_disabled(tmp_path):
    """The local dev loop runs with no bucket configured and must not touch the network."""
    path = tmp_path / "inventory.sqlite"
    path.write_bytes(b"local only")
    snapshot = DatabaseSnapshot(None, "db/inventory.sqlite", path)

    snapshot.restore()
    snapshot.save()

    assert path.read_bytes() == b"local only"


def test_creating_the_object_races_are_rejected(tmp_path):
    """Two instances booting into an empty bucket both think they are creating the object.
    Only one may win.
    """
    store = FakeObjectStore()
    a_path = tmp_path / "a.sqlite"
    b_path = tmp_path / "b.sqlite"
    a_path.write_bytes(b"instance a")
    b_path.write_bytes(b"instance b")

    a = DatabaseSnapshot(store, "db/inventory.sqlite", a_path)
    b = DatabaseSnapshot(store, "db/inventory.sqlite", b_path)
    a.restore()
    b.restore()

    a.save()
    with pytest.raises(StaleSnapshotError):
        b.save()
