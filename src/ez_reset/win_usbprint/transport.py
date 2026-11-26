import logging
import time
from types import TracebackType
from typing import Self

import pywintypes
import win32event
import winerror
from win32file import (
    FILE_FLAG_NO_BUFFERING,
    FILE_FLAG_OVERLAPPED,
    FILE_FLAG_WRITE_THROUGH,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    GENERIC_READ,
    GENERIC_WRITE,
    OPEN_EXISTING,
    AllocateReadBuffer,
    CancelIo,
    CreateFileW,
    DeviceIoControl,
    GetOverlappedResult,
    ReadFile,
    WriteFile,
)

from ez_reset.transport import Transport

from .winapi import IOCTL_USBPRINT_GET_1284_ID, IOCTL_USBPRINT_SOFT_RESET

logger = logging.getLogger(__name__)


MAX_TRANSFER_SIZE = 0x400000

# The printer may stay silent, or refuse data while it is busy: every transfer has a deadline,
# so that a silent printer produces an error instead of freezing the application.
IO_TIMEOUT_MS = 10_000
DRAIN_TIMEOUT_MS = 200


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
            FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH | FILE_FLAG_OVERLAPPED,
            None,
        )

        logger.debug("    Opened %s on handle %d", self.path, self.handle.handle)

        logger.debug(
            "DeviceIoControl(%d, IOCTL_USBPRINT_SOFT_RESET, NULL, 1024)",
            self.handle.handle,
        )
        self._control(IOCTL_USBPRINT_SOFT_RESET)
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

    def _wait(self, overlapped: pywintypes.OVERLAPPED, timeout_ms: int, operation: str) -> int:
        """Wait for an overlapped transfer; cancel it and raise TimeoutError when the deadline expires."""
        if win32event.WaitForSingleObject(overlapped.hEvent, timeout_ms) == win32event.WAIT_TIMEOUT:
            CancelIo(self.handle)
            try:
                GetOverlappedResult(self.handle, overlapped, True)
            except pywintypes.error as error:
                if error.winerror != winerror.ERROR_OPERATION_ABORTED:
                    raise

            msg = f"The printer did not complete the {operation} within {timeout_ms} ms"
            raise TimeoutError(msg)

        return GetOverlappedResult(self.handle, overlapped, True)

    @staticmethod
    def _new_overlapped() -> pywintypes.OVERLAPPED:
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, True, False, None)
        return overlapped

    def _control(self, code: int) -> bytes:
        overlapped = self._new_overlapped()
        buffer = AllocateReadBuffer(1024)
        DeviceIoControl(self.handle, code, None, buffer, overlapped)
        size = self._wait(overlapped, IO_TIMEOUT_MS, "control request")
        return bytes(buffer[:size])

    def _read_once(self, timeout_ms: int) -> bytes:
        overlapped = self._new_overlapped()
        buffer = AllocateReadBuffer(MAX_TRANSFER_SIZE)
        ReadFile(self.handle, buffer, overlapped)
        size = self._wait(overlapped, timeout_ms, "read")
        return bytes(buffer[:size])

    def write(self, data: bytes) -> None:
        if self.closed:
            msg = f"Handle to USBPRINT device {self.path} is closed"
            raise OSError(msg)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("WriteFile(%s)", data[:32])
            if len(data) > 32:
                logger.debug("    Above call was truncated")

        overlapped = self._new_overlapped()
        WriteFile(self.handle, data, overlapped)
        bytes_written = self._wait(overlapped, IO_TIMEOUT_MS, "write")

        assert bytes_written == len(data)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("    Wrote %d bytes to %d", bytes_written, self.handle)

    def read(self, size: int) -> bytes:
        if self.closed:
            msg = f"Handle to USBPRINT device {self.path} is closed"
            raise OSError(msg)

        deadline = time.monotonic() + IO_TIMEOUT_MS / 1000

        while len(self._buffer) < size:
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                msg = f"The printer did not send {size} bytes within {IO_TIMEOUT_MS} ms"
                raise TimeoutError(msg)

            self._buffer += self._read_once(remaining_ms)

            if len(self._buffer) < size:
                time.sleep(0.01)

        read = self._buffer[:size]
        self._buffer = self._buffer[size:]

        return read

    def drain(self) -> None:
        """Discard whatever the printer has queued; a silent printer simply means there is nothing to discard."""
        while True:
            try:
                data = self._read_once(DRAIN_TIMEOUT_MS)
            except TimeoutError:
                return

            if not data:
                return

            logger.debug("    Drained %d bytes", len(data))

    def identify(self) -> str:
        return self._control(IOCTL_USBPRINT_GET_1284_ID)[2:].decode("ascii")
