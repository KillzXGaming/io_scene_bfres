import enum
import subprocess
from . import addon
from . import binary_io
from .bfres_common import BfresOffset, BfresNameOffset, IndexGroup
from .bfres_fmdl import FmdlSection
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
            if reader.read_raw_string(8) != "FRES    ":
                raise AssertionError("Invalid FRES file header.")
            self.version = reader.read_uint32() 
            self.bom = reader.read_uint16()  #Byte Order mark
            self.header_size = reader.read_uint16() #size of header to allignment
            self.file_name_offset_directly = reader.read_uint32() #Goes directly to the string but not the size
            self.file_alignment = reader.read_uint32()
            self.relocation_table_offset = reader.read_uint32()
            self.bfres_size = reader.read_uint32()
            self.file_name_offet = BfresNameOffset(reader)
            self.padding = reader.read_uint32()
            self.model_offset = reader.read_uint64()
            self.model_index_offset = reader.read_uint64()
            self.skeletal_anim_offset = reader.read_uint64()
            self.skeletal_anim_index_offset = reader.read_uint64()
            self.material_anim_offset = reader.read_uint64()
            self.material_anim_index_offset = reader.read_uint64()
            self.bonevis_anim_offset = reader.read_uint64()
            self.bonevis_anim_index_offset = reader.read_uint64()
            self.shape_anim_offset = reader.read_uint64()
            self.shape_anim_index_offset = reader.read_uint64()
            self.scene_anim_offset = reader.read_uint64()
            self.scene_anim_index_offset = reader.read_uint64()	
            self.buffer_mempool_offset = reader.read_uint64()
            self.buffer_mempool_info_offset = reader.read_uint64()
            self.externalfile_offset = reader.read_uint64()
            self.externalfile_index_offset = reader.read_uint64()
            self.padding = reader.read_uint64()
            self.string_table_offset = BfresOffset(reader)
            self.padding = reader.read_uint32()
            self.unk = reader.read_uint32()
            self.model_count = reader.read_uint16() 
            self.skeletal_anim_count = reader.read_uint16() 
            self.material_anim_count = reader.read_uint16() 
            self.visual_anim_count = reader.read_uint16()
            self.shape_anim_count = reader.read_uint16()
            self.scene_anim_count = reader.read_uint16()
            self.exteralfile_count = reader.read_uint16()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()

            # Read the fmdl offset and count
            self.fmdl_array = []
            self.ext_array = []
				
    class Rlt:
        def __init__(self, reader):
            reader.seek(0x18)
            self.RTLOffset = reader.read_uint32()  
            reader.seek(self.RTLOffset)
            reader.seek(0x30,1)
            self.DataStart = reader.read_uint32()  

    class External:
        def __init__(self, reader):
            self.dataOffset = reader.read_uint64()
            self.Size = reader.read_uint64()
				
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
        # Open a little-endian binary reader on the stream.
        with binary_io.BinaryReader(raw) as reader:
            reader.endianness = "<"
            # Read the header.
			
            self.header = self.Header(reader)
            addon.log(0, "FRES " + self.header.file_name_offet.name)
            print(str(self.header.externalfile_offset))
			
            reader.seek(self.header.model_offset)
            for i in range(0, self.header.model_count):
                self.header.fmdl_array.append(FmdlSection(reader))
            reader.seek(self.header.externalfile_offset)
            for i in range(0, self.header.exteralfile_count): #Read Textures
                self.header.ext_array.append(self.External(reader))
                current_pos = reader.tell()
               
                print(self.header.ext_array[i].dataOffset)
                reader.seek(self.header.ext_array[i].dataOffset)
                if reader.read_raw_string(4) == "BNTX":
                    print("Found BNTX Texture container")
                    reader.seek(-4, 1) #Seek back once bntx is found
                    self.bntx_file = reader.read_bytes(self.header.ext_array[i].Size)  #Create a byte array for entire bntx      
                reader.seek(current_pos)
                 # TODO: Read other sub file formats
				 
				 
				 
				 
				 
				 
				 
				 
				 
				 
				 
				 
