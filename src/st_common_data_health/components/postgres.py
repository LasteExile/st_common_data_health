from __future__ import annotations

import asyncio
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from st_common_data_health.base import AbstractComponentHealthHandler
from st_common_data_health.exceptions import UnhealthComponentError



class AbstractPostgresHealthHandler(AbstractComponentHealthHandler):
    name = "postgres"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        timeout: float = 3.0,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self._session_factory = session_factory
        self._timeout = timeout

    async def ping(self) -> None:
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session_factory() as session:
                    await session.execute(text("SELECT 1"))
        except (SQLAlchemyError, TimeoutError) as exc:
            raise UnhealthComponentError(str(exc)) from exc


class ReadOnlyPostgresHealthHandler(AbstractPostgresHealthHandler):
    async def check_startup(self) -> None:
        await self.ping()

    async def check_live(self) -> None:
        await self.ping()

    async def check_ready(self) -> None:
        await self.ping()


class PostgresHealthHandler(AbstractPostgresHealthHandler):
    async def check_write_read(self) -> None:
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session_factory() as session:
                    try:
                        await session.execute(
                            text("""
                                CREATE TEMP TABLE healthcheck_tmp (
                                    id BIGSERIAL,
                                    val TEXT NOT NULL
                                ) ON COMMIT DROP
                            """)
                        )

                        expected = f"health-{time.time_ns()}"

                        await session.execute(
                            text("""
                                INSERT INTO healthcheck_tmp (val)
                                VALUES (:value)
                            """),
                            {"value": expected},
                        )

                        actual = await session.scalar(
                            text("""
                                SELECT val
                                FROM healthcheck_tmp
                                ORDER BY id DESC
                                LIMIT 1
                            """)
                        )

                        if actual != expected:
                            raise UnhealthComponentError(
                                "PostgreSQL healthcheck value mismatch"
                            )
                    finally:
                        await session.rollback()

        except UnhealthComponentError:
            raise
        except (SQLAlchemyError, TimeoutError) as exc:
            raise UnhealthComponentError(str(exc)) from exc
        

    async def check_startup(self) -> None:
        await self.ping()
        await self.check_write_read()

    async def check_live(self) -> None:
        await self.ping()

    async def check_ready(self) -> None:
        await self.ping()
