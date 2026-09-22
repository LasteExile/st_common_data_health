from __future__ import annotations

from faststream.kafka import KafkaBroker

from st_common_data_health.base import AbstractComponentHealthHandler
from st_common_data_health.exceptions import UnhealthComponentError



class KafkaHealthHandler(AbstractComponentHealthHandler):
    name = "kafka"

    def __init__(
        self,
        client: KafkaBroker,
        *,
        timeout: int = 3,
    ) -> None:
        self._client = client
        self._timeout = timeout

    async def _ping(self) -> None:
        value = await self._client.ping(self._timeout)
        if not value:
            raise UnhealthComponentError("Kafka returned false ping")

    async def check_startup(self) -> None:
        await self._ping()

    async def check_live(self) -> None:
        await self._ping()

    async def check_ready(self) -> None:
        await self._ping()

