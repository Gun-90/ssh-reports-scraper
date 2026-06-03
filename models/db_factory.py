import os


def get_db():
    """Return a DB manager based on DB_BACKEND.

    DB_BACKEND=sqlite       — use SQLite (legacy/test only)
    DB_BACKEND=ssh_library  — opt-in SecReportsManager smoke path
    All other cases         — use local PostgreSQLManager (production default)
    """
    backend = os.getenv("DB_BACKEND", "postgres").lower()
    if backend == "sqlite":
        from models.SQLiteManager import SQLiteManager
        return SQLiteManager()
    if backend == "ssh_library":
        try:
            from ssh_library import SecReportsManager
        except ImportError as e:
            raise RuntimeError(
                "DB_BACKEND=ssh_library requires ssh-library to be installed "
                "or available on PYTHONPATH. Keep DB_BACKEND=postgres for production "
                "until the deploy image includes ssh-library."
            ) from e
        return SecReportsManager(
            db_name=os.getenv("POSTGRES_REPORT_DB", "ssh_reports_hub"),
            user=os.getenv("POSTGRES_USER", "ssh_reports_hub"),
            keyword_db_name=os.getenv("POSTGRES_KEYWORD_DB"),
        )

    from models.PostgreSQLManager import PostgreSQLManager
    return PostgreSQLManager()
