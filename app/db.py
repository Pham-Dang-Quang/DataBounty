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
        self._add_evaluation_progress_columns()

    def _add_evaluation_progress_columns(self) -> None:
        """Apply the two additive SQLite columns without introducing a migration framework."""
        if self.engine.dialect.name != "sqlite":
            return
        columns = {column["name"] for column in inspect(self.engine).get_columns("contributions")}
        statements = []
        if "evaluation_progress" not in columns:
            statements.append(
                "ALTER TABLE contributions ADD COLUMN evaluation_progress "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "evaluation_stage" not in columns:
            statements.append(
                "ALTER TABLE contributions ADD COLUMN evaluation_stage VARCHAR(120) "
                "NOT NULL DEFAULT 'Queued for evaluation'"
            )
        if statements:
            with self.engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))

    def sessions(self) -> Generator[Session, None, None]:
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()
