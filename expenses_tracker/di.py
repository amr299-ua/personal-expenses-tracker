"""Lightweight dependency injection container.

Provides a simple registry for wiring application services without
tight coupling to concrete implementations.
"""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003
from typing import Any


class Container:
    """Minimal DI container supporting singleton and factory registrations."""

    def __init__(self) -> None:
        self._registry: dict[str, tuple[Callable[[], Any], bool]] = {}
        self._singletons: dict[str, Any] = {}

    def register(self, name: str, factory: Callable[[], Any], *, singleton: bool = True) -> None:
        """Register a service by name.

        Args:
            name: Unique identifier for the service.
            factory: Callable that returns the service instance.
            singleton: If True, the factory is called once and cached.
        """
        self._registry[name] = (factory, singleton)
        self._singletons.pop(name, None)

    def resolve(self, name: str) -> Any:
        """Resolve a registered service by name.

        Raises:
            KeyError: If the service is not registered.
        """
        if name not in self._registry:
            raise KeyError(f"Service '{name}' is not registered in the container.")

        factory, singleton = self._registry[name]
        if singleton:
            if name in self._singletons:
                return self._singletons[name]
            instance = factory()
            self._singletons[name] = instance
            return instance
        return factory()

    def has(self, name: str) -> bool:
        """Return whether a service is registered."""
        return name in self._registry


# Global application container
container = Container()
