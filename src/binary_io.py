import io
import struct


class BinaryReader:
    def __init__(self, raw):
        self.raw = raw
        self.endianness = "<"  # Little-endian

    def __enter__(self):
        self.reader = io.BufferedReader(self.raw)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.reader.close()

    def align(self, alignment):
        self.reader.seek(-self.reader.tell() % alignment, io.SEEK_CUR)

    def seek(self, offset, whence=io.SEEK_SET):
        self.reader.seek(offset, whence)

    def tell(self):
        return self.reader.tell()

    def read_0_string(self):
        text = ""
        i = self.read_byte()
        while i != 0:
            text += chr(i)
            i = self.read_byte()
        return text

    def read_byte(self):
        return self.reader.read(1)[0]

    def read_bytes(self, count):
        return self.reader.read(count)

    def read_int32(self):
        return struct.unpack(self.endianness + "i", self.reader.read(4))[0]

    def read_int32s(self, count):
        return struct.unpack(self.endianness + str(int(count)) + "i", self.reader.read(4 * count))

    def read_sbyte(self):
        return struct.unpack(self.endianness + "b", self.reader.read(1))[0]

    def read_sbytes(self, count):
        return struct.unpack(self.endianness + str(int(count)) + "b", self.reader.read(1 * count))

    def read_single(self):
        return struct.unpack(self.endianness + "f", self.reader.read(4))[0]

    def read_singles(self, count):
        return struct.unpack(self.endianness + str(int(count)) + "f", self.reader.read(4 * count))

    def read_uint16(self):
        return struct.unpack(self.endianness + "H", self.reader.read(2))[0]

    def read_uint16s(self, count):
        return struct.unpack(self.endianness + str(int(count)) + "H", self.reader.read(2 * count))

    def read_uint32(self):
        return struct.unpack(self.endianness + "I", self.reader.read(4))[0]

    def read_uint32s(self, count):
        return struct.unpack(self.endianness + str(int(count)) + "I", self.reader.read(4 * count))

    def read_raw_string(self, length, encoding="ascii"):
        return self.reader.read(length).decode(encoding)


class BinaryWriter:
    def __init__(self, raw):
        self.raw = raw
        self.endianness = "<"  # Little-endian

    def __enter__(self):
        self.writer = io.BufferedWriter(self.raw)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.writer.close()

    def align(self, alignment):
        self.writer.seek(-self.writer.tell() % alignment, io.SEEK_CUR)

    def reserve_offset(self):
        return Offset(self)

    def satisfy_offset(self, offset, value=None):
        offset.satisfy(self, value)

    def seek(self, offset, whence=io.SEEK_SET):
        self.writer.seek(offset, whence)

    def tell(self):
        return self.writer.tell()

    def write_0_string(self, value, encoding="ascii"):
        self.write_raw_string(value, encoding)
        self.write_byte(0)

    def write_byte(self, value):
        self.writer.write(struct.pack("B", value))

    def write_bytes(self, value):
        self.writer.write(value)

    def write_int32(self, value):
        self.writer.write(struct.pack(self.endianness + "i", value))

    def write_int32s(self, value):
        self.writer.write(struct.pack(self.endianness + str(len(value)) + "i", *value))

    def write_sbyte(self, value):
        self.writer.write(struct.pack(self.endianness + "b", value))

    def write_sbytes(self, value):
        self.writer.write(struct.pack(self.endianness + str(len(value)) + "b", *value))

    def write_single(self, value):
        self.writer.write(struct.pack(self.endianness + "f", value))

    def write_singles(self, value):
        self.writer.write(struct.pack(self.endianness + str(len(value)) + "f", *value))

    def write_uint16(self, value):
        self.writer.write(struct.pack(self.endianness + "H", value))

    def write_uint16s(self, value):
        self.writer.write(struct.pack(self.endianness + str(len(value)) + "H", *value))

    def write_uint32(self, value):
        self.writer.write(struct.pack(self.endianness + "I", value))

    def write_uint32s(self, value):
        self.writer.write(struct.pack(self.endianness + str(len(value)) + "I", *value))

    def write_raw_string(self, value, encoding="ascii"):
        self.writer.write(bytearray(value, encoding))


class Offset:
    def __init__(self, writer):
        # Remember the position of the offset to change it later.
        self.position = writer.tell()
        # Write an empty offset for now.
        self.value = 0
        writer.write_uint32(self.value)

    def satisfy(self, writer, value=None):
        self.value = value if value else writer.tell()
        # Seek back temporarily to the offset position to write the final offset value.
        current_position = writer.tell()
        writer.seek(self.position)
        writer.write_uint32(self.value)
        writer.seek(current_position)
