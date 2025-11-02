import xml.etree.ElementTree as ET
from dataclasses import dataclass
from importlib.resources import files
from itertools import batched
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

xml_content = files(__package__).joinpath("devices.xml").read_bytes()
devices = ET.fromstring(xml_content)


@dataclass
class Counter:
    addresses: list[int]
    max: int


@dataclass
class Device:
    model: bytes
    key: bytes

    counters: list[Counter]

    reset: dict[int, int]


def by_model(model: str) -> Device:
    printer_el: Element = devices.find(f".//printer[@model='{model}']")

    device = Device(
        model=b"",
        key=b"",
        counters=[],
        reset={},
    )

    for spec in printer_el.attrib.get("specs", "").split(","):
        spec_el: Element = devices.find(f".//devices/{spec}")

        service_el = spec_el.find(".//service")
        if service_el is not None:
            factory_el = service_el.find(".//factory")
            device.model = bytes(int(byte, 0) for byte in factory_el.text.split())

            keyword_el = service_el.find(".//keyword")
            if keyword_el is not None:
                device.key = bytes(int(byte, 0) for byte in keyword_el.text.split())

        waste_el = spec_el.find(".//waste")
        if waste_el is not None:
            query_el = waste_el.find(".//query")
            if query_el is not None:
                for counter_el in query_el.findall(".//counter"):
                    counter = Counter(addresses=[], max=0)

                    entry_el = counter_el.find(".//entry")
                    raw_addresses = entry_el.text if entry_el is not None else counter_el.text

                    counter.addresses = [int(raw, 0) for raw in raw_addresses.split()]

                    max_el = counter_el.find(".//max")
                    counter.max = int(max_el.text if max_el is not None else 0)

                    device.counters.append(counter)

            reset_el = waste_el.find(".//reset")
            if reset_el is not None:
                device.reset = {int(addr, 0): int(val, 0) for (addr, val) in batched(reset_el.text.split(), 2)}

    return device
