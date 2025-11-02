from collections.abc import Generator


def parse_status_struct(data: bytes) -> Generator[tuple[int, int, bytes], None, None]:
    """Return a generator that iterates over a binary status struct's entries."""
    length = int.from_bytes(data[0:2], "little")

    if len(data) != length + 2:
        msg = "Status payload length invalid"
        raise ValueError(msg)

    # The status object contains various fields of interest, which are comprised of:
    # header  - 1 byte
    # size    - 1 byte
    # payload - n bytes
    index = 2
    while index < length:
        header = data[index]
        index += 1

        parameter_length = data[index]
        index += 1

        parameter_data = data[index : index + parameter_length]
        index += parameter_length

        yield header, parameter_length, parameter_data


def parse_identifier(identifier: str) -> dict[str, str]:
    """Parse an IEEE 1284.4 ID string."""
    fields = identifier.split(";")

    return dict(e.split(":") for e in fields if e)
