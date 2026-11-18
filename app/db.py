from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from web3 import Web3


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str) -> None:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_tables(self) -> None:
        Base.metadata.create_all(self.engine)
        self._apply_additive_columns()

    def _apply_additive_columns(self) -> None:
        """Apply small SQLite additions without introducing a migration framework."""
        if self.engine.dialect.name != "sqlite":
            return
        statements = []
        contribution_columns = {
            column["name"] for column in inspect(self.engine).get_columns("contributions")
        }
        if "evaluation_progress" not in contribution_columns:
            statements.append(
                "ALTER TABLE contributions ADD COLUMN evaluation_progress "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "evaluation_stage" not in contribution_columns:
            statements.append(
                "ALTER TABLE contributions ADD COLUMN evaluation_stage VARCHAR(120) "
                "NOT NULL DEFAULT 'Queued for evaluation'"
            )
        if "companion_text" not in contribution_columns:
            statements.append("ALTER TABLE contributions ADD COLUMN companion_text TEXT")
        if "reviewer_id" not in contribution_columns:
            statements.append("ALTER TABLE contributions ADD COLUMN reviewer_id INTEGER")
        if "payout_key" not in contribution_columns:
            statements.append("ALTER TABLE contributions ADD COLUMN payout_key VARCHAR(66)")
        contribution_additions = {
            "source_stored_filename": "VARCHAR(80)",
            "source_original_filename": "VARCHAR(255)",
            "source_sha256": "VARCHAR(64)",
            "source_media_type": "VARCHAR(100)",
            "source_size_bytes": "INTEGER",
            "validation_summary": "TEXT",
        }
        for name, column_type in contribution_additions.items():
            if name not in contribution_columns:
                statements.append(f"ALTER TABLE contributions ADD COLUMN {name} {column_type}")
        call_columns = {column["name"] for column in inspect(self.engine).get_columns("data_calls")}
        call_additions = {
            "ai_evaluation_prompt": "TEXT",
            "csv_columns": "TEXT",
            "csv_delimiter": "VARCHAR(20)",
            "csv_min_records": "INTEGER",
            "csv_max_records": "INTEGER",
            "csv_allow_extra_columns": "BOOLEAN NOT NULL DEFAULT 0",
            "csv_allow_missing_values": "BOOLEAN NOT NULL DEFAULT 0",
            "csv_unique_column": "VARCHAR(120)",
            "segmentation_mode": "VARCHAR(30)",
        }
        for name, column_type in call_additions.items():
            if name not in call_columns:
                statements.append(f"ALTER TABLE data_calls ADD COLUMN {name} {column_type}")
        user_columns = {column["name"] for column in inspect(self.engine).get_columns("users")}
        user_additions = {
            "email": "VARCHAR(320)",
            "password_hash": "VARCHAR(300)",
            "display_name": "VARCHAR(80)",
            "bio": "TEXT",
            "profile_image": "VARCHAR(80)",
        }
        for name, column_type in user_additions.items():
            if name not in user_columns:
                statements.append(f"ALTER TABLE users ADD COLUMN {name} {column_type}")
        if statements:
            with self.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
        with self.engine.begin() as connection:
            connection.execute(
                text("UPDATE data_calls SET data_type = 'image_text' WHERE data_type = 'image'")
            )
            connection.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_contributions_source_stored_filename "
                    "ON contributions (source_stored_filename) "
                    "WHERE source_stored_filename IS NOT NULL"
                )
            )
            legacy_contributions = connection.execute(
                text("SELECT id FROM contributions WHERE payout_key IS NULL")
            ).fetchall()
            for (contribution_id,) in legacy_contributions:
                legacy_hash = Web3.keccak(text=str(contribution_id)).hex()
                legacy_key = f"0x{legacy_hash.removeprefix('0x')}"
                connection.execute(
                    text(
                        "UPDATE contributions SET payout_key = :payout_key WHERE id = :id"
                    ),
                    {"payout_key": legacy_key, "id": contribution_id},
                )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_contributions_payout_key "
                    "ON contributions (payout_key) WHERE payout_key IS NOT NULL"
                )
            )

    def sessions(self) -> Generator[Session, None, None]:
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()
