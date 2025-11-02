from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


class ControlBackend(ABC):
    """Interface describing functions for sending commands over the Control interface.

    Usage must always be through an async context manager::

        async with ExampleControlBackend(...) as backend:
            ...

    Control commands are always two bytes, followed by a little-endian `length`, then `length` bytes of payload. The
    payload is command-dependant and does not follow any common structure.

    Common commands are:

    * `st`: status information
    * `vi`: version information
    * `||`: service command
    """

    @abstractmethod
    def __enter__(self) -> Self: ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool: ...

    @abstractmethod
    def send(self, command: bytes) -> bytes:
        """Send the binary payload."""
        ...

    @abstractmethod
    def identify(self) -> str:
        """Retrieve the IEEE 1284 Device ID."""
        ...
