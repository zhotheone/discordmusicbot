from typing import Any, Dict, Type, TypeVar, Union

T = TypeVar("T")


class DIContainer:
    """Simple dependency injection container."""

    def __init__(self):
        self._services: Dict[Union[str, Type], Any] = {}
        self._singletons: Dict[Union[str, Type], Any] = {}

    def register(
        self, service_type: Union[str, Type[T]], instance: T, singleton: bool = True
    ) -> None:
        """Register a service instance."""
        if singleton:
            self._singletons[service_type] = instance
        else:
            self._services[service_type] = instance

    def get(self, service_type: Union[str, Type[T]]) -> T:
        """Get a service instance."""
        if service_type in self._singletons:
            return self._singletons[service_type]

        if service_type in self._services:
            return self._services[service_type]

        raise ValueError(f"Service {service_type} not registered")

    def has(self, service_type: Union[str, Type[T]]) -> bool:
        """Check if a service is registered."""
        return service_type in self._singletons or service_type in self._services
