from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


def test_full_alembic_upgrade_and_downgrade_on_fresh_sqlite(
    tmp_path: Path, monkeypatch
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migrations.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    repository_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(repository_root / "alembic.ini"))

    def database_tables() -> set[str]:
        engine = create_engine(database_url)
        try:
            with engine.connect() as connection:
                return set(inspect(connection).get_table_names())
        finally:
            engine.dispose()

    def database_revision() -> str | None:
        engine = create_engine(database_url)
        try:
            with engine.connect() as connection:
                return connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
        finally:
            engine.dispose()

    try:
        command.upgrade(alembic_config, "head")
        table_names = database_tables()
        assert {
            "estado_operativo",
            "reservas_temporales",
            "registros_idempotencia",
            "alembic_version",
        } <= table_names

        command.downgrade(alembic_config, "base")
        table_names_after_downgrade = database_tables()
        assert "Prueba" in table_names_after_downgrade
        assert database_revision() is None

        command.upgrade(alembic_config, "head")
        table_names_after_upgrade = database_tables()
        assert {
            "estado_operativo",
            "reservas_temporales",
            "registros_idempotencia",
        } <= table_names_after_upgrade
    finally:
        get_settings.cache_clear()
