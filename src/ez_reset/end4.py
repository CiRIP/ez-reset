import logging
from time import sleep
from types import TracebackType
from typing import Self

from .control import ControlBackend
from .exceptions import BackendError
from .transport import Transport
from .utils import parse_identifier

logger = logging.getLogger(__name__)


ExitPacketMode2 = b"\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL\t\t\t\t\t\n"


class END4ControlBackend(ControlBackend):
    """Handles the Control channel over END4.

    An Epson-proprietary bidirectional protocol, "END4" makes it possible to send CTRL commands over a printer data line
    without requiring full IEEE 1284.4 (Dot4 or D4) framing.

    The underlying transport must be capable of bidirectional communication, and must support returning the IEEE 1284.4
    ID string.
    """

    def __init__(self, bidi_transport: Transport) -> None:
        self.transport = bidi_transport

        if self.transport.closed:
            msg = "BiDi device is closed"
            raise BackendError(msg)

    def __enter__(self) -> Self:
        identifier = parse_identifier(self.identify())
        self.transport.write(ExitPacketMode2)

        dds = int(identifier["DDS"], base=16)
        while dds > 0:
            self.transport.write(b"\x11" * 0x8000)
            dds -= 0x8000

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        return False

    def send(self, command: bytes) -> bytes:
        self.transport.drain()

        self.transport.write(
            b"END4"
            b"\x02\x01\x00\x00\x00"
            + (len(command) + 14).to_bytes(
                1,
                "big",
            )  # are other 0x00 bytes be the MSBs of the length?
            + b"\x00\x00\x02\x00"
            + command,
        )

        response = b""
        while not response.startswith(b"END4"):
            response = self.transport.read(1024)
            sleep(0.1)

        expected_len = int.from_bytes(response[9:10], "big")

        if len(response) != expected_len:
            msg = "Received incomplete packet."
            raise BackendError(msg)

        return response[10:]

    def identify(self) -> str:
        return self.transport.identify()
