import struct


MAX_DATABASE_SIZE = 16 * 1024 * 1024 - 1


def _crc_table():
    entries = []
    for value in range(256):
        state = value << 24
        for step in range(8):
            state = ((state << 1) ^ (0x04C11DB7 if state & 0x80000000 else 0)) & 0xFFFFFFFF
        entries.append(state)
    return tuple(entries)


CRC_TABLE = _crc_table()


def crc32(data, seed=0xFFFFFFFF):
    for value in data:
        seed = ((seed << 8) ^ CRC_TABLE[(seed >> 24) ^ value]) & 0xFFFFFFFF
    return seed


def compress(data):
    if not 0 < len(data) <= MAX_DATABASE_SIZE:
        raise ValueError("Unsupported squad database size")
    output = bytearray(b"\x10\xfb" + len(data).to_bytes(3, "big"))
    position = 0
    while len(data) - position >= 4:
        size = min(112, (len(data) - position) & ~3)
        output.append(0xE0 + size // 4 - 1)
        output.extend(data[position:position + size])
        position += size
    output.append(0xFC + len(data) - position)
    output.extend(data[position:])
    return bytes(output)


def decompress(data):
    if len(data) < 6 or data[:2] != b"\x10\xfb":
        raise ValueError("Unsupported squad compression header")
    expected = int.from_bytes(data[2:5], "big")
    if not 0 < expected <= MAX_DATABASE_SIZE:
        raise ValueError("Unsupported squad database size")
    output = bytearray()
    position = 5
    while position < len(data):
        command = data[position]
        position += 1
        if command < 0xE0:
            raise ValueError("Unsupported squad compression command")
        final = command >= 0xFC
        size = command & 3 if final else ((command & 0x1F) + 1) * 4
        if position + size > len(data) or len(output) + size > expected:
            raise ValueError("Truncated or oversized squad payload")
        output.extend(data[position:position + size])
        position += size
        if final:
            if position != len(data) or len(output) != expected:
                raise ValueError("Squad payload length mismatch")
            return bytes(output)
    raise ValueError("Missing squad compression terminator")


def build_database(tables):
    chunks = []
    index = bytearray()
    position = 0
    for table in tables:
        fields = table["fields"]
        records = table["records"]
        size = table["record_size"]
        if len(fields) % 16 or len(fields) // 16 > 255 or not size or len(records) % size:
            raise ValueError("Invalid native table layout")
        rows = len(records) // size
        if rows > 65535:
            raise ValueError("Too many native squad rows")
        header = struct.pack("<4I4H2I", 2, size, table["delete_bit"], 0, rows, rows, table["cancelled"], 65535, len(fields) // 16, 0)
        content = fields + records
        chunk = header + struct.pack("<I", crc32(header)) + content + struct.pack("<I", crc32(content))
        index.extend(table["shortname"].encode("ascii") + struct.pack("<I", position))
        chunks.append(chunk)
        position += len(chunk)
    total = 28 + len(index) + position
    header = struct.pack("<5I", 0x08004244, 0, total, 0, len(tables))
    return header + struct.pack("<I", crc32(header)) + index + struct.pack("<I", crc32(index)) + b"".join(chunks)


def read_database(data):
    if len(data) < 36 or len(data) > MAX_DATABASE_SIZE:
        raise ValueError("Invalid squad database length")
    magic, endian, size, reserved, count, header_crc = struct.unpack_from("<6I", data)
    if magic != 0x08004244 or endian or reserved or size != len(data) or not 0 < count < 256:
        raise ValueError("Invalid squad database header")
    if crc32(data[:20]) != header_crc:
        raise ValueError("Squad database header checksum mismatch")
    index_end = 24 + count * 8
    base = index_end + 4
    if base > len(data) or crc32(data[24:index_end]) != struct.unpack_from("<I", data, index_end)[0]:
        raise ValueError("Squad database index checksum mismatch")
    tables = []
    expected_offset = 0
    for index in range(count):
        name, offset = struct.unpack_from("<4sI", data, 24 + index * 8)
        start = base + offset
        if offset != expected_offset or start + 36 > len(data):
            raise ValueError("Invalid squad table offset")
        flags, record_size, delete_bit, strings, rows, written, cancelled, unknown, field_count, unknown_crc, table_crc = struct.unpack_from("<4I4H3I", data, start)
        if flags != 2 or strings or not record_size or delete_bit >= record_size * 8 or rows != written or cancelled > written or unknown != 65535 or unknown_crc or not 0 < field_count <= 255:
            raise ValueError("Unsupported squad table layout")
        if crc32(data[start:start + 32]) != table_crc:
            raise ValueError("Squad table header checksum mismatch")
        records_start = start + 36 + field_count * 16
        end = records_start + written * record_size
        if end + 4 > len(data) or crc32(data[start + 36:end]) != struct.unpack_from("<I", data, end)[0]:
            raise ValueError("Squad table data checksum mismatch")
        fields = data[start + 36:records_start]
        for position in range(0, len(fields), 16):
            field_type, bit_offset, field_name, depth = struct.unpack_from("<II4sI", fields, position)
            if field_type not in (0, 3, 4) or not depth or bit_offset + depth > delete_bit:
                raise ValueError("Unsupported squad field layout")
        tables.append({"shortname": name.decode("ascii"), "record_size": record_size, "delete_bit": delete_bit, "cancelled": cancelled, "fields": fields, "records": data[records_start:end]})
        expected_offset = end + 4 - base
    if base + expected_offset != len(data) or len({table["shortname"] for table in tables}) != count:
        raise ValueError("Duplicate squad tables or trailing data")
    return tables


def database_crc(tables):
    state = 0xFFFFFFFF
    for table in tables:
        records = table["records"]
        size = table["record_size"]
        delete_byte, delete_bit = divmod(table["delete_bit"], 8)
        checksums = sorted(crc32(records[position:position + size]) for position in range(0, len(records), size) if not records[position + delete_byte] & (1 << delete_bit))
        if checksums:
            state = crc32(struct.pack("<" + "I" * len(checksums), *checksums), state)
    return state
