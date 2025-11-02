# ruff: noqa: N802

import binascii
import logging
import struct
import time
from dataclasses import dataclass
from enum import IntEnum
from types import TracebackType
from typing import Self

from ez_reset.control import ControlBackend
from ez_reset.transport import Transport

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class D4Packet:
    psid: int
    ssid: int
    credit: int
    control: int
    payload: bytes


class D4Command(IntEnum):
    Init = 0
    OpenChannel = 1
    CloseChannel = 2
    Credit = 3
    CreditRequest = 4
    Exit = 8
    GetSocketID = 9


errors = {
    0x80: "Malformed packet",
    0x81: "No credit",
    0x82: "Reply without command",
    0x83: "Packet too big",
    0x84: "Channel not open",
    0x85: "Unknown Result",
    0x86: "Credit overflow",
    0x87: "Bad command/reply",
}


class D4Error(Exception): ...


class D4Channel:
    def __init__(self, d4: "D4", ssid: int) -> None:
        self.d4 = d4
        self.ssid: int = ssid

        self.psid: int | None = None
        self.mtu: int | None = None
        self.tx_credits: int = 0

        self.rx_credits: int = 0
        self.rx_credits_max: int = 0x0001
        self.rx_queue: list[D4Packet] = []

    def __enter__(self) -> Self:
        self.d4.OpenChannel(self)
        self.d4.Credit(self, self.rx_credits_max)
        self.rx_credits += self.rx_credits_max

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        self.d4.CloseChannel(self)

        return False

    def _ensure_credit(self) -> None:
        if self.tx_credits < 1:
            while self.d4.CreditRequest(self) < 1:
                time.sleep(0.1)

    def write(self, data: bytes, progress=None) -> None:
        while len(data):
            control = 0

            payload = data[: self.mtu - 6] if len(data) > self.mtu - 6 else data
            control |= 2

            data = data[len(payload) :]

            credit = min(self.rx_credits_max - self.rx_credits, 0xFF)
            packet = D4Packet(self.psid, self.ssid, credit, control, payload)
            self.rx_credits += credit

            self._ensure_credit()
            self.d4.write_packet(self, packet)

            if progress:
                progress(len(payload))

    def read(self) -> D4Packet:
        credit = self.rx_credits_max - self.rx_credits
        # keep Credit transactions over the wire to a minimum
        if credit > 0xFF:
            self.d4.Credit(self, credit)
            self.rx_credits += credit

        return self.d4.read_packet(self)


class D4:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport

        self.open_channels: dict[int, D4Channel] = {0x00: D4Channel(self, 0x00)}
        self.open_channels[0x00].tx_credits = 1

        # drain eg. periodic status messages that may be queued
        self.transport.drain()

        # escape other modes, enter 1284.4 mode
        self.transport.write(b"\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL\n@EJL\n")
        self.transport.read(8)

        self.Init()

    def _get_free_psid(self) -> int:
        for i in range(0x100):
            if i not in self.open_channels:
                return i

        msg = "No free PSIDs to allocate to channel open."
        raise D4Error(msg)

    def write_packet(self, channel: D4Channel, packet: D4Packet) -> None:
        length = 6 + len(packet.payload)
        header = struct.pack(
            ">BBHBB",
            packet.psid,
            packet.ssid,
            length,
            packet.credit,
            packet.control,
        )

        data = header + packet.payload
        logger.debug("> %s", " ".join(f"{x:02x}" for x in data[:0x100]))
        self.transport.write(data)

        channel.tx_credits -= 1

    def read_packet(self, channel: D4Channel) -> D4Packet:
        while not len(channel.rx_queue):
            self.read_next_packet()

        return channel.rx_queue.pop(0)

    def read_next_packet(self) -> None:
        header_data = self.transport.read(6)
        psid, ssid, length, credit, control = struct.unpack(">BBHBB", header_data)
        logger.debug("< %s", " ".join(f"{x:02x}" for x in header_data))

        payload = self.transport.read(length - 6)
        logger.debug("< %s", " ".join(f"{x:02x}" for x in header_data + payload))

        if psid not in self.open_channels:
            logger.warning("Received packet for closed socket ID %d", psid)
            return

        channel = self.open_channels[psid]

        channel.tx_credits += credit
        channel.rx_credits -= 1

        channel.rx_queue.append(D4Packet(psid, ssid, credit, control, payload))

    def command(self, command: D4Command, payload: bytes = b"") -> bytes:
        if command not in [command.Init, command.Exit]:
            assert self.open_channels[0].tx_credits

        logger.debug("%s %s", command.name, binascii.hexlify(payload))

        packet = D4Packet(0x00, 0x00, 1, 0x00, bytes([command]) + payload)

        self.write_packet(self.open_channels[0x00], packet)
        res = self.read_packet(self.open_channels[0x00])

        assert res.psid == 0

        if res.payload[0] == 0x7F:  # Error
            logger.error(errors.get(res.payload[3], f"0x{res.payload[3]:x}"))

        assert res.payload[0] == command | 0x80
        assert res.payload[1] == 0

        return res.payload[2:]

    def Init(self) -> None:
        resp = self.command(D4Command.Init, b"\x10")
        assert resp == b"\x10"

    def Exit(self) -> None:
        self.command(D4Command.Exit)

    def GetSocketID(self, name: str) -> int:
        resp = self.command(D4Command.GetSocketID, name.encode("ascii"))
        return int(resp[0])

    def OpenChannel(self, channel: D4Channel) -> None:
        psid = channel.ssid

        req = struct.pack(
            ">BBHHHH",
            psid,
            channel.ssid,
            0xFFFF,
            0xFFFF,
            0x0000,
            0x0000,
        )

        res = self.command(D4Command.OpenChannel, req)
        psid, ssid, mtu, _max_credit, credit = struct.unpack(">BBHHH", res)

        assert ssid == channel.ssid

        channel.psid = psid
        channel.mtu = mtu
        channel.tx_credits = credit

        self.open_channels[psid] = channel

    def CloseChannel(self, channel: D4Channel) -> None:
        req = struct.pack(">BB", channel.psid, channel.ssid)
        self.command(D4Command.CloseChannel, req)

        del self.open_channels[channel.psid]

    def Credit(self, channel: D4Channel, amount: int) -> None:
        req = struct.pack(">BBH", channel.psid, channel.ssid, amount)
        self.command(D4Command.Credit, req)

    def CreditRequest(self, channel: D4Channel, amount: int = 0xFFFF) -> int:
        req = struct.pack(">BBH", channel.psid, channel.ssid, amount)
        resp = self.command(D4Command.CreditRequest, req)
        _, _, amount = struct.unpack(">BBH", resp)
        self.open_channels[channel.psid].tx_credits += amount
        return amount

    def channel(self, name: str) -> D4Channel:
        ssid = self.GetSocketID(name)
        return D4Channel(self, ssid)


class D4ControlBackend(ControlBackend):
    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self.d4: D4 | None = None
        self.channel: D4Channel | None = None

    def __enter__(self) -> Self:
        self.d4 = D4(self.transport)
        self.channel = self.d4.channel("EPSON-CTRL").__enter__()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        self.channel.__exit__(exc_type, exc_val, exc_tb)

        return False

    def send(self, command: bytes) -> bytes:
        if not self.channel:
            msg = "Channel must be opened"
            raise RuntimeError(msg)

        self.channel.write(command)
        res = self.channel.read()

        return res.payload

    def identify(self) -> str:
        return self.transport.identify()
