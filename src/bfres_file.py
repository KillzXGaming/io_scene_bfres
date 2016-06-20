import enum
from .log import Log
from .binary_io import BinaryReader
from .bfres_common import BfresOffset, BfresNameOffset, IndexGroup
from .bfres_fmdl import FmdlSection
from .bfres_ftex import FtexSection
from .bfres_embedded import EmbeddedFile

'''
Hierarchically visualized, the layout of a BFRES file is as follows:
- BFRES File
  - String Table
  - 12 Index Groups
    - Index Group 0
      - FMDL[] (Models, mostly only 1 of these)
        - FSKL (Skeleton)
          - Bones[]
        - FVTX[] (Vertex Buffers)
          - Attributes[] (referencing the buffer in which they are in)
          - Buffers[]
        - FSHP[] (Polygons)
          - LoD Models[] (probably one when multiple visiblity groups)
            - Visibility Groups[] (index buffer slices, probably one when multiple LoD models)
            - Index Buffer
          - Visibility Group Tree (Nodes[], Ranges[], Indices[], unknown purpose)
        - FMAT[] (Materials)
          - Render Parameters[]
          - Material Structure (unknown purpose)
          - Shader Control
          - Texture Selectors[]
          - Texture Attribute Selectors[]
          - Material Parameters[]
          - Shadow Parameters[]
        - Parameters[]
    - Index Group 1
      - FTEX[] (Texture Data)
        - ...
    - Index Group 2
      - FSKA[] (Skeleton Animations)
        - ?
    - Index Group 3, 4, 5
      - FSHU[] (Unknown Purpose)
        - ?
    - Index Group 6
      - FTXP[] (Texture Pattern Animations)
        - ?
    - Index Group 7, 8
      - FVIS[] (Bone Visibility)
        - ?
    - Index Group 9
      - FSHA[] (Unknown Purpose)
    - Index Group 10
      - FSCN[] (Scene Data, Unknown Purpose)
        - ?
    - Index Group 11
      - Embedded Files[]
        - Raw Data (pointed to by offset and length pairs, partially shader code)

However, this is just a silly simplification. The BFRES file is by far not as sequential as expectable from the layout
given above. Actually, the headers of the specific sections just point around in the file (relative to themselves, not
the file), and strings are globally collected in a file-wide string table. Data is found in an order as follows:
- BFRES Header
- Index Groups
- Headers of the sections referenced by the Index Groups
- String Table
- Data referenced by the section and subsection headers
- Embedded File data
This order was probably chosen to keep graphical data together, so it can be uploaded to the GPU in one step, while data
which needs CPU access is stored in the bunch of headers and tables at the beginning of the file.

Index Groups are technically binary trees allowing a quick named lookup of elements in a corresponding array. Combined
with the array, they are easier to imagine as an OrderedDict which items can be accessed by index or name. This add-on
wraps the logic inside IndexGroup classes however, preserving the index group node information and allowing access to
entries via name, index or offset.

All this makes it quite non-trivial to create an exporter later on, as offsets have to be satisfied after the file is
completely written. This needs some brain-storming as it was probably solved with C pointer maths originally.
'''

class BfresFile:
    class Header:
        INDEX_GROUP_COUNT = 12

        def __init__(self, reader):
            if reader.read_raw_string(4) != "FRES":
                raise AssertionError("Invalid FRES file header.")
            self.unknown0x04 = reader.read_byte() # 0x03 in MK8
            self.unknown0x05 = reader.read_byte() # 0x00, 0x03 or 0x04 in MK8
            self.unknown0x06 = reader.read_byte() # 0x00 in MK8
            self.unknown0x07 = reader.read_byte() # 0x01, 0x02 or 0x04 in MK8
            self.embedded_byte_order = reader.read_uint16()
            self.version = reader.read_uint16() # 0x0010 in MK8
            self.file_length = reader.read_uint32()
            self.file_alignment = reader.read_uint32()
            self.file_name_offset = BfresNameOffset(reader)
            self.string_table_length = reader.read_uint32()
            self.string_table_offset = BfresOffset(reader)
            # Read the index group offsets and counts, then load the index groups.
            self.index_group_offsets = []
            for i in range(0, self.INDEX_GROUP_COUNT):
                self.index_group_offsets.append(BfresOffset(reader))
            self.index_group_nodes = []
            for i in range(0, self.INDEX_GROUP_COUNT):
                self.index_group_nodes.append(reader.read_uint16())

    class IndexGroupType(enum.IntEnum):
        Fmdl0 = 0
        Ftex1 = 1
        Fska2 = 2
        Fshu3 = 3
        Fshu4 = 4
        Fshu5 = 5
        Ftxp6 = 6
        Fvis7 = 7
        Fvis8 = 8
        Fsha9 = 9
        Fscn10 = 10
        EmbeddedFile11 = 11

    def __init__(self, raw):
        # Open a big-endian binary reader on the stream.
        with BinaryReader(raw) as reader:
            reader.endianness = ">"
            # Read the header.
            self.header = self.Header(reader)
            Log.write(0, "FRES " + self.header.file_name_offset.name)
            # Load the typed data referenced by the specific index groups, if present.
            for i in range(0, self.Header.INDEX_GROUP_COUNT):
                offset = self.header.index_group_offsets[i]
                if offset:
                    reader.seek(offset.to_file)
                    if i == self.IndexGroupType.Fmdl0:
                        self.fmdl_index_group = IndexGroup(reader, lambda r: FmdlSection(r))
                    elif i == self.IndexGroupType.Ftex1:
                        self.ftex_index_group = IndexGroup(reader, lambda r: FtexSection(r))
                    elif i == self.IndexGroupType.EmbeddedFile11:
                        self.embedded_file_index_group = IndexGroup(reader, lambda r: EmbeddedFile(r))
                    # TODO: Read other index group types.
