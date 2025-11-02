"""Enums and structs related to printer status conditions and states.

This list is not exhaustive. The values here have been extracted from the open-source epson-inkjet-escpr driver package,
released under GPLv2.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Iterable

from .utils import parse_status_struct


class PrinterState(Enum):
    ERROR = 0x00
    SELF_PRINTING = 0x01
    BUSY = 0x02
    WAITING = 0x03
    IDLE = 0x04
    PAUSE = 0x05
    INKDRYING = 0x06
    CLEANING = 0x07
    FACTORY_SHIPMENT = 0x08
    MOTOR_DRIVE_OFF = 0x09
    SHUTDOWN = 0x0A
    WAITPAPERINIT = 0x0B
    INIT_PAPER = 0x0C

    @classmethod
    def _missing_(cls, _key: str) -> Self:
        return cls.ERROR


class PrinterError(Enum):
    NONE = -1
    FATAL = 0x00
    INTERFACE = 0x01
    PAPERJAM = 0x04
    INKOUT = 0x05
    PAPEROUT = 0x06
    PAPERSIZE = 0x0A
    PAPERPATH = 0x0C
    SERVICEREQ = 0x10
    DOUBLEFEED = 0x12
    INKCOVEROPEN = 0x1A
    NOMAINTENANCEBOX = 0x22
    COVEROPEN = 0x25
    NOTRAY = 0x29
    CARDLOADING = 0x2A
    CDDVDCONFIG = 0x2B
    CARTRIDGEOVERFLOW = 0x2C
    BATTERYVOLTAGE = 0x2F
    BATTERYTEMPERATURE = 0x30
    BATTERYEMPTY = 0x31
    SHUTOFF = 0x32
    NOT_INITIALFILL = 0x33
    PRINTPACKEND = 0x34
    MAINTENANCEBOXCOVEROPEN = 0x36
    SCANNEROPEN = 0x37
    CDRGUIDEOPEN = 0x38
    CDREXIST = 0x44
    CDREXIST_MAINTE = 0x45
    TRAYCLOSE = 0x46

    @classmethod
    def _missing_(cls, _key: str) -> Self:
        return cls.FATAL


class PaperPath(Enum):
    UNKNOWN = -1
    ROLL = 0x00
    FANFOLD = 0x01
    ROLL_BACK = 0x02

    @classmethod
    def _missing_(cls, _key: str) -> Self:
        return cls.UNKNOWN


class ConsumableStatus(Enum):
    OKAY = 0
    EMPTY = 1
    MISSING = 2
    FAIL = 3
    UNKNOWN = 4


@dataclass(frozen=True)
class ConsumableLevel:
    level: int
    status: ConsumableStatus

    @classmethod
    def from_int(cls, level: int) -> ConsumableLevel:
        """Parse level and status information from a raw level value."""
        if level == 110:
            return cls(-1, ConsumableStatus.MISSING)

        if level == 105:
            return cls(-1, ConsumableStatus.UNKNOWN)

        if level < 0 or level > 100:
            return cls(-1, ConsumableStatus.FAIL)

        if level == 0:
            return cls(level, ConsumableStatus.EMPTY)

        return cls(level, ConsumableStatus.OKAY)


class InkColor(Enum):
    BLACK = 0
    CYAN = 1
    MAGENTA = 2
    YELLOW = 3
    LIGHT_CYAN = 4
    LIGHT_MAGENTA = 5
    DARK_YELLOW = 6
    GRAY = 7
    LIGHT_BLACK = 8
    RED = 9
    BLUE = 10
    GLOSS_OPTIMIZER = 11
    LIGHT_GRAY = 12
    ORANGE = 13

    UNKNOWN = -1

    @classmethod
    def _missing_(cls, _key: str) -> Self:
        return cls.UNKNOWN


@dataclass(frozen=True)
class InkLevel(ConsumableLevel):
    color: InkColor

    @classmethod
    def from_bytes(cls, entry: bytes) -> InkLevel:
        """Parse an ink entry from an ink level field."""
        color = InkColor(entry[1])

        consumable_level = ConsumableLevel.from_int(entry[2])

        return cls(consumable_level.level, consumable_level.status, color)


@dataclass(frozen=True)
class Status:
    state: PrinterState
    error: PrinterError
    source: PaperPath
    levels: Iterable[InkLevel]
    maintenance_box: ConsumableLevel
    serial: str
    other: dict[int, bytes]

    @classmethod
    def from_bytes(cls, data: bytes) -> Status:
        status = PrinterState.IDLE
        error = PrinterError.NONE
        source: PaperPath = PaperPath.UNKNOWN
        levels: Iterable[InkLevel] = []
        maintenance_box = ConsumableLevel(-1, ConsumableStatus.UNKNOWN)
        serial = ""
        other: dict[int, bytes] = {}

        for header, _parameter_length, parameter_data in parse_status_struct(data):
            # Status entry
            if header == 0x01:
                status = PrinterState(parameter_data[0])

            # Error entry
            elif header == 0x02:
                error = PrinterError(parameter_data[0])

            # Media source entry
            elif header == 0x06:
                source = PaperPath(3 - parameter_data[0])

            # Maintenance box level entry
            elif header == 0x0D:
                maintenance_box = ConsumableLevel.from_int(parameter_data[0])

            # Ink entry
            elif header == 0x0F:
                entry_size = parameter_data[0]

                levels = [
                    InkLevel.from_bytes(parameter_data[i : i + entry_size])
                    for i in range(1, len(parameter_data), entry_size)
                ]

            elif header == 0x40:
                serial = str(parameter_data)

            else:
                other[header] = parameter_data

        return Status(status, error, source, levels, maintenance_box, serial, other)

    def __rich_repr__(self) -> Iterable[Any | tuple[Any] | tuple[str, Any] | tuple[str, Any, Any]]:
        yield "state", self.state
        yield "error", self.error, PrinterError.NONE
        yield "source", self.source
        yield "levels", self.levels
        yield (
            "maintenance_box",
            self.maintenance_box,
            ConsumableLevel(level=-1, status=ConsumableStatus.UNKNOWN),
        )
        yield "serial", self.serial
