"""Founder review CLI for opt-in minimized story submissions."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.data import repo
from app.data.db import create_database_engine, create_session_factory


async def run(
    argv: Sequence[str] | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    engine = None
    if session_factory is None:
        settings = get_settings()
        engine = create_database_engine(settings.database_url)
        session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            if args.command == "list":
                status = None if args.status == "all" else args.status
                stories = await repo.list_story_submissions(
                    session, status=status, limit=args.limit
                )
                for story in stories:
                    print(_format_story(story))
                return 0

            status = {"approve": "approved", "reject": "rejected"}[args.command]
            story = await repo.update_story_status(
                session, story_id=UUID(args.story_id), status=status
            )
            if story is None:
                print(f"story not found: {args.story_id}", file=sys.stderr)
                return 1
            await session.commit()
            print(f"{story.status}: {story.id}")
            return 0
    finally:
        if engine is not None:
            await engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list stories for review")
    list_parser.add_argument(
        "--status",
        choices=["submitted", "approved", "rejected", "published", "all"],
        default="submitted",
    )
    list_parser.add_argument("--limit", type=int, default=20)

    for command in ("approve", "reject"):
        command_parser = subparsers.add_parser(command, help=f"{command} a story")
        command_parser.add_argument("story_id")

    return parser


def _format_story(story) -> str:
    return (
        f"{story.id} | {story.status} | {story.face} | {story.language} | "
        f"{story.created_ts.isoformat()}\n{story.minimized_text}\n"
    )


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
