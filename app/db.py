from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


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

    def sessions(self) -> Generator[Session, None, None]:
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()
