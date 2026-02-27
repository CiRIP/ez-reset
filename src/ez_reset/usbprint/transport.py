import logging
import time
from types import TracebackType
from typing import Self

import usb.core
import usb.util

from ez_reset.transport import Transport

logger = logging.getLogger(__name__)

MAX_TRANSFER_SIZE = 0x400000
READ_TIMEOUT_MS = 150
WRITE_TIMEOUT_MS = 5000

PRINTER_CLASS = 0x07
GET_DEVICE_ID = 0x00
SOFT_RESET = 0x02


def _is_printer_device(device: usb.core.Device) -> bool:
    for config in device:
        for interface in config:
            if interface.bInterfaceClass == PRINTER_CLASS:
                return True

    return False


def _find_printer_interface(device: usb.core.Device) -> tuple[int, int]:
    for config in device:
        for interface in config:
            if interface.bInterfaceClass == PRINTER_CLASS:
                return config.bConfigurationValue, interface.bInterfaceNumber

    msg = f"USB device {device.idVendor:04x}:{device.idProduct:04x} has no printer interface"
    raise RuntimeError(msg)


def _format_path(device: usb.core.Device) -> str:
    return f"{device.idVendor:04x}:{device.idProduct:04x}:{device.bus:03d}:{device.address:03d}"


def enumerate_printers() -> list[str]:
    printers: list[str] = []
    devices = usb.core.find(find_all=True, custom_match=_is_printer_device)

    for device in devices:
        path = _format_path(device)
        product = usb.util.get_string(device, device.iProduct) or "Unknown printer"
        printers.append(f"{path} {product}")

    return printers


class USBPRINTTransport(Transport):
    def __init__(self, path: str) -> None:
        self.path = path
        self.closed = True

        self._buffer = b""
        self._device: usb.core.Device | None = None
        self._interface: int | None = None
        self._ep_in: usb.core.Endpoint | None = None
        self._ep_out: usb.core.Endpoint | None = None
        self._detached_kernel = False

    def __enter__(self) -> Self:
        try:
            vid, pid, bus, address = (int(v, 16) for v in self.path.split(" ", 1)[0].split(":"))
        except (ValueError, IndexError) as exc:
            msg = f"Invalid USB printer path: {self.path}"
            raise ValueError(msg) from exc

        device = usb.core.find(idVendor=vid, idProduct=pid, bus=bus, address=address)
        if not device:
            msg = f"USB printer not found: {self.path}"
            raise OSError(msg)

        cfg_value, interface = _find_printer_interface(device)
        device.set_configuration(cfg_value)

        if device.is_kernel_driver_active(interface):
            device.detach_kernel_driver(interface)
            self._detached_kernel = True

        usb.util.claim_interface(device, interface)
        configuration = device.get_active_configuration()
        intf = configuration[(interface, 0)]

        ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda endpoint: usb.util.endpoint_direction(endpoint.bEndpointAddress)
            == usb.util.ENDPOINT_OUT
            and usb.util.endpoint_type(endpoint.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK,
        )
        ep_in = usb.util.find_descriptor(
            intf,
            custom_match=lambda endpoint: usb.util.endpoint_direction(endpoint.bEndpointAddress)
            == usb.util.ENDPOINT_IN
            and usb.util.endpoint_type(endpoint.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK,
        )

        if not ep_out or not ep_in:
            msg = f"USB printer interface is missing bulk endpoints: {self.path}"
            raise OSError(msg)

        # Clear stale state before opening a D4 session.
        device.ctrl_transfer(0x21, SOFT_RESET, 0, interface)

        self._device = device
        self._interface = interface
        self._ep_in = ep_in
        self._ep_out = ep_out
        self.closed = False

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        if self._device and self._interface is not None:
            usb.util.release_interface(self._device, self._interface)
            if self._detached_kernel:
                self._device.attach_kernel_driver(self._interface)

            usb.util.dispose_resources(self._device)

        self._device = None
        self._interface = None
        self._ep_in = None
        self._ep_out = None
        self._detached_kernel = False
        self.closed = True

        return False

    def write(self, data: bytes) -> None:
        if self.closed or not self._ep_out:
            msg = f"Handle to USBPRINT device {self.path} is closed"
            raise OSError(msg)

        bytes_written = self._ep_out.write(data, timeout=WRITE_TIMEOUT_MS)
        if bytes_written != len(data):
            msg = f"Short USB write: expected {len(data)}, got {bytes_written}"
            raise OSError(msg)

    def read(self, size: int) -> bytes:
        if self.closed or not self._ep_in:
            msg = f"Handle to USBPRINT device {self.path} is closed"
            raise OSError(msg)

        while len(self._buffer) < size:
            try:
                data = bytes(self._ep_in.read(MAX_TRANSFER_SIZE, timeout=READ_TIMEOUT_MS))
                self._buffer += data
            except usb.core.USBTimeoutError:
                time.sleep(0.01)

        read = self._buffer[:size]
        self._buffer = self._buffer[size:]
        return read

    def drain(self) -> None:
        if self.closed or not self._ep_in:
            return

        while True:
            try:
                data = self._ep_in.read(MAX_TRANSFER_SIZE, timeout=READ_TIMEOUT_MS)
                if len(data) == 0:
                    return
            except usb.core.USBTimeoutError:
                return

    def identify(self) -> str:
        if self.closed or not self._device or self._interface is None:
            msg = f"Handle to USBPRINT device {self.path} is closed"
            raise OSError(msg)

        raw = bytes(self._device.ctrl_transfer(0xA1, GET_DEVICE_ID, 0, self._interface, 1024))
        if len(raw) < 3:
            return raw.decode("ascii", errors="ignore")

        payload_size = int.from_bytes(raw[:2], byteorder="big")
        payload = raw[2:payload_size]
        return payload.decode("ascii", errors="ignore").strip("\x00")
