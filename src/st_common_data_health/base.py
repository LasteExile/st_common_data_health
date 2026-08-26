import time
import datetime
from typing import Literal, Callable, TypedDict, Awaitable
from abc import ABC, abstractmethod
from enum import Enum

from st_common_data_health.exceptions import UnhealthComponentError, DegradedComponentError 

__all__ = (
    "HEALTH_STATUS",
    "ComponentHealthStatus",
    "HealthHandler",
    "AbstractComponentHealthHandler",
)


class HEALTH_STATUS(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "Unhealthy"
    DEGRADED = "Degraded"


class ComponentHealthStatus(TypedDict):
    status: str
    exception: str | None
    duration: str


class TotalHealthStatus(TypedDict):
    status: str
    duration: str
    entries: dict[str, ComponentHealthStatus]


HealthTypes = ("live", "ready", "startup")
HealthTypesType = Literal["live", "ready", "startup"]
HealthStatusType = tuple[HEALTH_STATUS, dict[str, ComponentHealthStatus]]


class AbstractComponentHealthHandler(ABC):
    """
        Abstract class to check component's status: every method must returns None if everything is
        OK or raise UnhealthComponentError or DegradedComponentError with detailed error message
    """
    name: str

    def __init__(
        self,
        *args,
        name: str | None = None,
        **kwargs,
    ) -> None:
        if name:
            self.name = name

    @abstractmethod
    async def check_startup(self) -> None:
        pass

    @abstractmethod
    async def check_live(self) -> None:
        pass

    @abstractmethod
    async def check_ready(self) -> None:
        pass


class HealthHandler:
    """
        Check components health statuses and determinate the global system
        status by worst of components' statuses

        Accepts list of childs of AbstractComponentHealthHandler
        Every probe returns worst status and detailed components status
    """
        
    _components: dict[HealthTypesType, list[AbstractComponentHealthHandler]]

    def __init__(
        self,
        live_components: list[AbstractComponentHealthHandler],
        ready_components: list[AbstractComponentHealthHandler],
        startup_components: list[AbstractComponentHealthHandler],
    ) -> None:
        self._components = {
            "live": live_components,
            "ready": ready_components, 
            "startup": startup_components,
        }

    async def _get_status(
        self,
        *,
        health_type: Literal["startup", "live", "ready"],
    ) -> TotalHealthStatus:
        method_name = "check_" + health_type

        worst_status = HEALTH_STATUS.HEALTHY
        components_statuses: dict[str, ComponentHealthStatus] = {}

        total_check_start_time = time.time()
        for component in self._components[health_type]:
            method = getattr(component, method_name)
            exception = None
            status = HEALTH_STATUS.HEALTHY

            check_start_time = time.time()
            try:
                await method()
            except UnhealthComponentError as e:
                exception = str(e)
                status = HEALTH_STATUS.UNHEALTHY
                worst_status = HEALTH_STATUS.UNHEALTHY
            except DegradedComponentError as e:
                exception = str(e)
                status = HEALTH_STATUS.DEGRADED
                if worst_status == HEALTH_STATUS.HEALTHY:
                    worst_status = HEALTH_STATUS.DEGRADED

            check_end_time = time.time()

            check_duration = datetime.timedelta(
                seconds=(check_end_time - check_start_time))  # type: ignore

            components_statuses[component.name] = ComponentHealthStatus(
                status=status.value,
                duration=str(check_duration),
                exception=exception,
            )

        total_check_end_time = time.time()
        total_check_duration = datetime.timedelta(
            seconds=(total_check_end_time - total_check_start_time))  # type: ignore

        return {
            "status": worst_status.value,
            "duration": str(total_check_duration),
            "entries": components_statuses,
        } 

    async def get_startup(self) -> TotalHealthStatus:
        return await self._get_status(health_type="startup")

    async def get_live(self) -> TotalHealthStatus:
        return await self._get_status(health_type="live")

    async def get_ready(self) -> TotalHealthStatus:
        return await self._get_status(health_type="ready")

    def get_method_by_type(self, type_: HealthTypesType) -> Callable[[], Awaitable[TotalHealthStatus]]:

        TYPES = {
            "startup": self.get_startup,
            "live": self.get_live,
            "ready": self.get_ready,
        }
        try:
            return TYPES[type_]
        except KeyError:
            raise ValueError(f"Invalid type_ was given, choose one of these: {TYPES.keys()}")
        

