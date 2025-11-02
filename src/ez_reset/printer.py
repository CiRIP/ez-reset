from collections.abc import Iterable

from .control import ControlBackend
from .devices import Device
from .status import Status


class Printer:
    def __init__(self, control_backend: ControlBackend, device: Device) -> None:
        self.device = device

        self._control = control_backend

    def send_command(self, command: bytes, payload: bytes) -> bytes:
        return self._control.send(
            command + len(payload).to_bytes(2, "little") + payload,
        )

    def send_factory_command(self, model: bytes, action: int, payload: bytes = b"") -> bytes:
        command = b"||"
        action_code = bytes(
            (action, action ^ 0xFF, ((action >> 1) & 0x7F) | ((action << 7) & 0x80)),
        )
        return self.send_command(command, model + action_code + payload)

    def get_status(self) -> Status:
        command = b"st"
        expected = b"@BDC ST2\r\n"
        response = self.send_command(command, b"\x01")

        if not response.startswith(expected):
            msg = f"Unknown response {response} for command {expected}"
            raise ValueError(msg)

        payload = response[len(expected) :]

        return Status.from_bytes(payload)

    def read_eeprom(self, address: int) -> int:
        action = 0x41
        expected = b"@BDC PS\r\n"
        response = self.send_factory_command(
            self.device.model,
            action,
            address.to_bytes(2, "little"),
        )

        if not response.startswith(expected):
            msg = f"Unknown response {response} for command {expected}"
            raise ValueError(msg)

        return int(response[16:18], base=16)

    def write_eeprom(self, address: int, value: int) -> bytes:
        action = 0x42
        payload = address.to_bytes(2, "little") + value.to_bytes(1, "little") + self.device.key

        return self.send_factory_command(self.device.model, action, payload)

    def read_eeprom_multiple(self, addresses: Iterable[int]) -> bytes:
        return bytes([self.read_eeprom(address) for address in addresses])

    def read_eeprom_range(self, address: int, size: int) -> bytes:
        action = 0x51
        expected = b"@BDC PS\r\n"
        response = self.send_factory_command(
            self.device.model,
            action,
            address.to_bytes(2, "little") + size.to_bytes(1, "little"),
        )

        if not response.startswith(expected):
            msg = f"Unknown response {response} for command {expected}"
            raise ValueError(msg)

        return bytes.fromhex(response[16 : 16 + size * 2].decode("ascii"))

    def identify(self) -> dict[str, str]:
        fields = (self._control.identify()).split(";")

        return dict(e.split(":") for e in fields if e)

    def get_serial(self) -> str:
        return (self.get_status()).serial

    def get_waste(self) -> list[tuple[int, int]]:
        return [
            (
                int.from_bytes(self.read_eeprom_multiple(counter.addresses), "little"),
                counter.max,
            )
            for counter in self.device.counters
        ]

    def reset_waste(self) -> None:
        for addr, value in self.device.reset.items():
            self.write_eeprom(addr, value)

    def clean(self, level: int) -> None:
        action = 0x84
        payload = level.to_bytes(1, "little")

        self.send_factory_command(self.device.model, action, payload)

    def power_off(self) -> None:
        action = 0x20

        self.send_factory_command(self.device.model, action)

    def restart(self) -> None:
        action = 0x21

        self.send_factory_command(self.device.model, action)
