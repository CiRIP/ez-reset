import logging
import time
from types import TracebackType
from typing import Self

from win32file import (
    FILE_FLAG_NO_BUFFERING,
    FILE_FLAG_WRITE_THROUGH,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    GENERIC_READ,
    GENERIC_WRITE,
    OPEN_EXISTING,
    CreateFileW,
    DeviceIoControl,
    ReadFile,
    WriteFile,
)

from ez_reset.transport import Transport

from .winapi import IOCTL_USBPRINT_GET_1284_ID, IOCTL_USBPRINT_SOFT_RESET

logger = logging.getLogger(__name__)


MAX_TRANSFER_SIZE = 0x400000


class USBPRINTTransport(Transport):
    def __init__(self, path: str) -> None:
        self.path = path
        self.handle = None
        self.closed = True

        self._buffer = b""

    def __enter__(self) -> Self:
        logger.debug("CreateFileW(%s)", self.path)
        self.handle = CreateFileW(
            self.path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH,
            None,
        )

        logger.debug("    Opened %s on handle %d", self.path, self.handle.handle)

        logger.debug(
            "DeviceIoControl(%d, IOCTL_USBPRINT_SOFT_RESET, NULL, 1024)",
            self.handle.handle,
        )
        DeviceIoControl(self.handle, IOCTL_USBPRINT_SOFT_RESET, None, 1024)
        logger.debug("    Issued soft reset to %d", self.handle.handle)

        self.closed = False

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        logger.debug("Closing...")
        self.handle.close()
        self.closed = True

        return False

    def write(self, data: bytes) -> None:
        if self.closed:
            msg = f"Handle to USBPRINT device {self.path} is closed"
            raise OSError(msg)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("WriteFile(%s)", data[:32])
            if len(data) > 32:
                logger.debug("    Above call was truncated")

        _status, bytes_written = WriteFile(self.handle, data)

        assert bytes_written == len(data)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("    Wrote %d bytes to %d", bytes_written, self.handle)

    def read(self, size: int) -> bytes:
        if self.closed:
            msg = f"Handle to USBPRINT device {self.path} is closed"
            raise OSError(msg)

        while len(self._buffer) < size:
            _status, data = ReadFile(self.handle, MAX_TRANSFER_SIZE)
            self._buffer += data

            if len(self._buffer) < size:
                time.sleep(0.01)

        read = self._buffer[:size]
        self._buffer = self._buffer[size:]

        return read

    def drain(self) -> None:
        remaining = True
        while remaining:
            _status, data = ReadFile(self.handle, MAX_TRANSFER_SIZE)
            remaining = len(data) != 0

    def identify(self) -> str:
        return DeviceIoControl(self.handle, IOCTL_USBPRINT_GET_1284_ID, None, 1024)[2:].decode("ascii")
