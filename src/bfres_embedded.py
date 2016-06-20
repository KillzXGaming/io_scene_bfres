from .bfres_common import BfresOffset

class EmbeddedFile:
    def __init__(self, reader):
        self.offset = BfresOffset(reader)
        self.size_in_bytes = reader.read_uint32()
        # Load the raw data.
        reader.seek(self.offset.to_file)
        self.data = reader.read_bytes(self.size_in_bytes)
