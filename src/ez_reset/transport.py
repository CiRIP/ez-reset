import typing
from types import TracebackType


class Transport(typing.Protocol):
    closed: bool

    def __enter__(self) -> typing.Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool: ...

    def read(self, size: int) -> bytes: ...

    def write(self, data: bytes) -> None: ...

    def drain(self) -> None: ...

    def identify(self) -> str: ...
