# ruff: noqa: E501
"""Add lively, call-specific discussions without recreating contribution files."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seed_demo_content import discussion_prompts  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.models import Comment, DataCall, User  # noqa: E402


def seed_discussions() -> None:
    db = Database(get_settings().database_url)
    db.create_tables()
    with db.session_factory() as session:
        users = [
            user
            for user in session.scalars(select(User)).all()
            if user.email and user.email.endswith("@databounty.local")
        ]
        for call_index, call in enumerate(session.scalars(select(DataCall)).all()):
            existing = session.scalars(select(Comment).where(Comment.call_id == call.id)).all()
            if len(existing) >= 18:
                continue
            for prompt_index, prompt in enumerate(discussion_prompts(call.title)):
                root = Comment(
                    call_id=call.id,
                    author_id=users[(call_index + prompt_index) % len(users)].id,
                    body=prompt,
                )
                session.add(root)
                session.flush()
                if prompt_index % 2 == 0:
                    session.add(
                        Comment(
                            call_id=call.id,
                            author_id=users[(call_index + prompt_index + 3) % len(users)].id,
                            parent_id=root.id,
                            body=(
                                "I see the trade-off. I would document that decision in the review notes "
                                "and apply the same threshold to every contributor."
                            ),
                        )
                    )
        session.commit()
        print("Seeded discussions for all calls.")


if __name__ == "__main__":
    seed_discussions()
