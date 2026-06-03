import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB_SRC = ROOT.parents[3] / "lib" / "ssh-library" / "src"
sys.path.append(str(ROOT))
if LIB_SRC.exists():
    sys.path.append(str(LIB_SRC))


def test_get_db_default_uses_local_postgres(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)

    from models.PostgreSQLManager import PostgreSQLManager
    from models.db_factory import get_db

    assert isinstance(get_db(), PostgreSQLManager)


def test_get_db_ssh_library_backend(monkeypatch):
    if not LIB_SRC.exists():
        pytest.skip("ssh-library checkout is not available")

    monkeypatch.setenv("DB_BACKEND", "ssh_library")

    from models.db_factory import get_db
    from ssh_library import SecReportsManager

    assert isinstance(get_db(), SecReportsManager)
