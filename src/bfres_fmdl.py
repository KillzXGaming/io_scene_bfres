import enum
import numpy
import struct
from . import addon
from .bfres_common import BfresOffset, BfresNameOffset, IndexGroup
from .bfres_file import *

'''
To build the vertices of an FMDL model, the following steps have to be done:
- Go through each FSHP (a polygon referencing its vertex buffer) and create a bmesh for it.
- Get the FVTX vertex buffer used by that FSHP, referenced by index in the FSHP header.
- Take the first LoD model of the FSHP which is the most detailled one.
- Get the indices of the index buffer (ignore the visibility groups to import the whole model and not only parts).
- To get only the vertices of the current LoD model, find the highest referenced vertex index by finding the biggest
  value in the index buffer (this can be done only with max(indices) + 1, as the game does not need to care about this).
- Retrieve the referenced vertices, make sure to add the LoD model offset to the vertex array index (skip_vertices).
  > FvtxSubsection.get_vertices()
- Iterate through the vertices, connect faces referenced by the indices, and set up additional vertex data.
'''


class FmdlSection:
    class Header:
        def __init__(self, reader):
            if reader.read_raw_string(4) != "FMDL":
                raise AssertionError("Invalid FMDL section header.")
            self.headerLength1 = reader.read_uint32()
            self.headerLength2 = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.file_name_offset = BfresNameOffset(reader)
            self.padding = reader.read_uint32()
            self.end_of_stringtable = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.fskl_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.fvtx_array_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.fshp_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.fshp_index_group_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.fmat_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.fmat_index_group_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.user_data_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.fvtx_count = reader.read_uint16()
            self.fshp_count = reader.read_uint16()
            self.fmat_count = reader.read_uint16()
            self.user_data_count = reader.read_uint16()
            self.toal_vert_count = reader.read_uint32()
            self.padding = reader.read_uint32()

            self.fshp_array = []
			
    class Parameter:
        def __init__(self, reader):
            self.variable_name_offset = BfresNameOffset(reader)
            self.unknown0x04 = reader.read_uint16()  # 0x0001
            self.unknown0x06 = reader.read_uint16()  # 0x0000
            self.unknown0x08 = reader.read_single()

    def __init__(self, reader):
        self.header = self.Header(reader)
        current_pos = reader.tell()
		
        addon.log(1, "FMDL " + self.header.file_name_offset.name)
        # Load the FSKL subsection.
        reader.seek(self.header.fskl_offset)
        self.fskl = FsklSubsection(reader)
        # Load the FVTX subsections.
        self.fvtx_array = []
        reader.seek(self.header.fvtx_array_offset)

       # for i in range(0, self.header.fvtx_count):
           # self.fvtx_array.append(FvtxSubsection(reader))
		   
        for i in range(0, self.header.fvtx_count):
            self.fvtx_array.append(FvtxSubsection(reader))

			
			
        # Load the FSHP index group.
		
        reader.seek(self.header.fshp_offset)
        for i in range(0, self.header.fshp_count):
            self.header.fshp_array.append(FshpSubsection(reader))
			#Load the FMAT index group.
			
        self.fmat_array = []

        reader.seek(self.header.fmat_offset)
        for i in range(0, self.header.fmat_count):
            self.fmat_array.append(FmatSubsection(reader))
			
        reader.seek(current_pos)



class FsklSubsection:
    class Header:
        def __init__(self, reader):
            if reader.read_raw_string(4) != "FSKL":
                raise AssertionError("Invalid FSKL subsection header.")
            self.HeaderLength = reader.read_uint32()
            self.HeaderLength2 = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.bone_index_group_array_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.bone_array_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.inv_index_array_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.inv_matrix_array_offset = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()	
            self.flags = reader.read_uint32()
            self.bone_count = reader.read_uint16()
            self.inv_count = reader.read_uint16()  # Count of elements in inverse index and matrix arrays.
            self.extra_index_count = reader.read_uint16()  # Additional elements in inverse index array.
            self.padding = reader.read_uint32()	

    class Bone:
        CHILD_BONE_COUNT = 4  # Wiki says parent bones, but where does that make sense to have multiple parents?

        def __init__(self, reader):
            self.name_offset = BfresNameOffset(reader)
            addon.log(3, "Bone " + self.name_offset.name)
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint32()
            self.index = reader.read_uint16()
            self.parent = reader.read_uint16()
            self.smoothMatrixIndex = reader.read_uint16()
            self.rigidMatrixIndex = reader.read_uint16()  # 0x1001
            self.billboardIndex = reader.read_uint16()  # 0x1001
            self.userDataCount = reader.read_uint16()  # 0x1001
            self.flags = reader.read_uint32()  # Unknown purpose.
            self.scale = reader.read_singles(3)
            self.rotation = reader.read_singles(4)
            self.translation = reader.read_singles(3)

    def __init__(self, reader):
        self.header = self.Header(reader)
        addon.log(2, "FSKL")
        reader.seek(self.header.bone_array_offset)
        for bones in range (0, self.header.bone_count):
            Bone_Info = self.Bone(reader)
			
            Bone_TellOff = reader.tell()
			
            reader.seek(Bone_TellOff)
			
        # Load the inverse index array.
        reader.seek(self.header.inv_index_array_offset)
        self.inv_indices = []
        for i in range(0, self.header.inv_count + self.header.extra_index_count):
            self.inv_indices.append(reader.read_uint16())
        # Load the inverse matrix array.
        reader.seek(self.header.inv_matrix_array_offset)
        self.inv_matrices = []
        for i in range(0, self.header.inv_count):
            self.inv_matrices.append((reader.read_singles(3), reader.read_singles(3), reader.read_singles(3), reader.read_singles(3)))


class FvtxSubsection:
    class Header:
        def __init__(self, reader):
            if reader.read_raw_string(4) != "FVTX":
                raise AssertionError("Invalid FVTX subsection header.")
            self.padding = reader.read_uint32()
            self.padding = reader.read_uint64()
            self.attribute_array_offset = reader.read_uint64()
            self.attribute_index_group_offset = reader.read_uint64()
            self.unk2 = reader.read_uint64()
            self.unk2 = reader.read_uint64()
            self.unk3 = reader.read_uint64()
            self.vertex_buffer_size_offset = reader.read_uint64()
            self.vertex_stride_offset = reader.read_uint64()
            self.buffer_array_offset = reader.read_uint64()
            self.buffer_offset = reader.read_uint32()
            self.attribute_count = reader.read_byte()
            self.buffer_count = reader.read_byte()
            self.index = reader.read_uint16()  # The index in the FMDL FVTX array.
            self.vertex_count = reader.read_uint32()
            self.skinWeightInfluence = reader.read_uint32()  # 0x00000000 (normally), 0x04000000

    class Attribute:
        def __init__(self, reader):
            self.name_offset = BfresNameOffset(reader)
            self.padding = reader.read_uint32()
            self.format = reader.read_uint16BE()
            self.padding = reader.read_uint16()
            self.element_offset = reader.read_uint16()  # Offset in each element.
            self.buffer_index = reader.read_uint16() # The index of the buffer containing this attrib.

			
            # Get a method parsing this attribute format.
            self.parser = self._parsers.get(self.format, None)
            if not self.parser:
                addon.log(0, "Warning: Attribute " + self.name_offset.name + ": unknown format " + str(self.format))
                # raise NotImplementedError("Attribute " + self.name_offset.name + ": unknown format " + str(self.format))

        def _parse_2x_8bit_normalized(self, buffData, offset):
            offset += self.element_offset
            return buffData.data[offset] / 0xFF, buffData.data[offset + 1] / 0xFF

        def _parse_2x_16bit_normalized(self, buffData, offset):
            offset += self.element_offset
            values = struct.unpack("<2H", buffData.data[offset:offset + 4])
            return tuple(x / 0xFFFF for x in values)

        def _parse_1x_8bit(self, buffData, offset):
            offset += self.element_offset
            return buffData.data[offset]

        def _parse_2x_8bit(self, buffData, offset):
            offset += self.element_offset
            return struct.unpack("<2B", buffData.data[offset:offset + 2])

        def _parse_4x_8bit(self, buffData, offset):
            offset += self.element_offset
            return struct.unpack("<4B", buffData.data[offset:offset + 4])

        def _parse_2x_16bit_short_as_float(self, buffData, offset):
            offset += self.element_offset
            return tuple(x / 0x7FFF for x in struct.unpack("<2H", buffData.data[offset:offset + 4]))

        def _parse_4x_8bit_signed(self, buffData, offset):
            offset += self.element_offset
            return struct.unpack("<4b", buffData.data[offset:offset + 4])

        def _parse_3x_10bit_signed(self, buffData, offset):
            offset += self.element_offset
            integer = struct.unpack("<I", buffData.data[offset:offset + 4])[0]
            # 8-bit values are aligned in 'integer' as follows:
            #   Bit: 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32
            # Value:  0  1  x  x  x  x  x  x  x  x  0  1  y  y  y  y  y  y  y  y  0  1  z  z  z  z  z  z  z  z  0  0
            # Those are then divided by 511 to retrieve the decimal value.
            x = ((integer & 0x3FC00000) >> 22) / 511
            y = ((integer & 0x000FF000) >> 12) / 511
            z = ((integer & 0x000003FC) >> 2) / 511
            return x, y, z

        def _parse_2x_16bit_float(self, buffData, offset):
            offset += self.element_offset
            return numpy.frombuffer(buffData.data, "<f2", 2, offset)

        def _parse_2x_32bit_float(self, buffData, offset):
            offset += self.element_offset
            return struct.unpack("<2f", buffData.data[offset:offset + 8])

        def _parse_4x_16bit_float(self, buffData, offset):
            offset += self.element_offset
            return numpy.frombuffer(buffData.data, "<f2", 4, offset)

        def _parse_3x_32bit_float(self, buffData, offset):
            offset += self.element_offset
         
            return struct.unpack("<3f", buffData.data[offset:offset + 12])

        _parsers = {
            0x00000109: _parse_2x_8bit_normalized,
            0x00000112: _parse_2x_16bit_normalized,
            0x0000010B: _parse_4x_8bit,
            0x00000302: _parse_1x_8bit,
            0x00000309: _parse_2x_8bit,
            0x0000030B: _parse_4x_8bit,
            0x00000212: _parse_2x_16bit_short_as_float,
            0x0000020b: _parse_4x_8bit_signed,
            0x0000020e: _parse_3x_10bit_signed,
            0x00000512: _parse_2x_16bit_float,
            0x00000517: _parse_2x_32bit_float,
            0x00000515: _parse_4x_16bit_float,
            0x00000518: _parse_3x_32bit_float
        }

    class buffData:
        def __init__(self,VertexBufferSize,stride,DataOffset,data):
            self.VertexBufferSize = VertexBufferSize
            self.stride = stride
            self.DataOffset = DataOffset
            self.data = data
		

    class Vertex:
        def __init__(self):
            # Member names must be kept as they allow a simple mapping in self.get_vertices().
            self.p0 = None  # Position
            self.n0 = None  # Normal
            self.t0 = None  # Tangent, lighting calculation
            self.b0 = None  # Binormal, lighting calculation
            self.w0 = None  # Blend weight, unknown purpose
            self.i0 = None  # Blend index, unknown purpose
            self.u0 = None  # UV texture coordinate layer 1
            self.u1 = None  # UV texture coordinate layer 2
            self.u2 = None  # UV texture coordinate layer 3
            self.u3 = None  # UV texture coordinate layer 4
            self.c0 = None  # Color for shadow mapping
            self.c1 = None  # Color for shadow mapping



			
    def __init__(self, reader):
        self.header = self.Header(reader)
        addon.log(2, "FVTX")
        # Load the attribute index group.
        current_pos = reader.tell()
		
		
        reader.seek(self.header.attribute_array_offset)
        self.att_array = []
        for i in range(0, self.header.attribute_count):
            self.att_array.append(self.Attribute(reader))
		
		
		
		
		
        reader.seek(0x18)
        self.RTLOffset = reader.read_uint32()  
        reader.seek(self.RTLOffset)
        reader.seek(0x30,1)
        self.DataStart = reader.read_uint32()  

		
		
        self.buffers = []
        # Load the buffer array.

        for i in range(0, self.header.buffer_count):
		
            reader.seek(self.header.vertex_buffer_size_offset + ((i) * 0x10))
            self.VertexBufferSize = reader.read_uint32()
            reader.seek(self.header.vertex_stride_offset + ((i) * 0x10))
            self.stride = reader.read_uint32()

            if i == 0:
                 DataOffset = (self.DataStart + self.header.buffer_offset);
            if i > 0:
                 DataOffset = ( self.buffers[i - 1].DataOffset +  self.buffers[i - 1].VertexBufferSize);
            if DataOffset % 8 != 0:
                 DataOffset = DataOffset + ((8 - DataOffset) % 8)
				
            reader.seek(DataOffset)
            self.data = reader.read_bytes(self.VertexBufferSize)  

            self.buffers.append(self.buffData(self.VertexBufferSize,self.stride,DataOffset, self.data))
			
      
            print( 'DataOffset = %s VertexBufferSize = %s stride = %s' %(DataOffset, self.VertexBufferSize, self.stride))
			
         
  
			
        # Seek back as FVTX headers are read as an array.
        reader.seek(current_pos)


		
    def get_vertices(self):
        # Create an array of empty vertex instances.
        vertices = [self.Vertex() for i in range(0, self.header.vertex_count)]
        # Get the data by attributes, as the data can be separated into different data arrays.
        for attribute in self.att_array:
            vertex_member = attribute.name_offset.name[1:]  # Remove the underscore of the attribute name.
            print(vertex_member + " " + str(attribute.buffer_index) + " " + str(attribute.element_offset) + "format" + str(attribute.format))
            buffData =  self.buffers[attribute.buffer_index]
       
            if attribute.parser is None:
                # Dump the attribute data into a file for further investigation.
                for i, offset in enumerate(range(0, buffData.VertexBufferSize, buffData.stride)):
                     (vertices[i], vertex_member, (0, 0, 0))
            else:
                for i, offset in enumerate(range(0, buffData.VertexBufferSize, buffData.stride)):
                    setattr(vertices[i], vertex_member, attribute.parser(attribute, buffData, offset))
                      

        return vertices


class FshpSubsection:
    class Header:
        def __init__(self, reader):
            if reader.read_raw_string(4) != "FSHP":
                raise AssertionError("Invalid FSHP subsection header.")
            self.padding = reader.read_uint32()  
            self.padding = reader.read_uint64()  
            self.name_offset = BfresNameOffset(reader)
            self.padding = reader.read_uint32()  
            self.fvtx_offset = reader.read_uint64() 
            self.lod_array_offset = reader.read_uint64()
            self.bone_index_group_array_offset = reader.read_uint64()
            self.padding = reader.read_uint64()  
            self.padding = reader.read_uint64()  
            self.visibility_group_tree_nodes_offset = reader.read_uint64()
            self.visibility_group_tree_ranges_offset = reader.read_uint64()
            self.padding = reader.read_uint64()  
            self.flag = reader.read_uint32()  
            self.index = reader.read_uint16()  # The index in the FMDL FSHP index group.
            self.material_index = reader.read_uint16()  # The index of the FMAT material for this polygon.
            self.bone_index = reader.read_uint16()  # The index of the bone this polygon is transformed with.
            self.buffer_index = reader.read_uint16()  
            self.fskl_index_array_count = reader.read_uint16()  
            self.VertexSkinCount = reader.read_byte() 
            self.lod_count = reader.read_byte()
            self.visibility_group_tree_node_count = reader.read_uint32()
            self.visibility_group_index = reader.read_uint16()  
            self.fsklarraycount = reader.read_uint16()  




    class LodModel:
        class VisibilityGroup:
            def __init__(self, reader):
                self.index_byte_offset = reader.read_uint32()  # Divide by 2 to get the array index; indices are 16-bit.
                self.index_count = reader.read_uint32()


        def __init__(self, reader):
            self.subMeshArrayOffset = reader.read_uint64()  # 0x00000004
            self.unk1 = reader.read_uint64()  
            self.unk2 = reader.read_uint64()  
            self.indexBufferOffset = reader.read_uint64()  
            self.FaceOffset = reader.read_uint32()  
            self.PrimativeFormat = reader.read_uint32()  
            self.facetype = reader.read_uint32()  
            self.facecount = reader.read_uint32()  
            self.skip_vertices = reader.read_uint32()  
            self.subMeshCount = reader.read_uint32()  
            # Load the visibility group array.
            current_pos = reader.tell()
         #   reader.seek(self.visibility_group_offset)
         #   self.visibility_groups = []
         #   for i in range(0, self.visibility_group_count):
         #       self.visibility_groups.append(self.VisibilityGroup(reader))
		 
            # Load the buffer.

            reader.seek(0x18)
            self.RTLOffset = reader.read_uint32()  
            reader.seek(self.RTLOffset)
            reader.seek(0x30,1)
            self.DataStart = reader.read_uint32()

            indexBufferOffset = self.DataStart + self.FaceOffset
            reader.seek(indexBufferOffset)
            self.indices = reader.read_uint16s(self.facecount)

			
			
		 
            # Seek back as multiple LoD models are stored in an array.
            reader.seek(current_pos)

    class VisibilityGroupTreeNode:
        def __init__(self, reader):
            self.left_child_index = reader.read_uint16()  # The current node's index if no left child.
            self.right_child_index = reader.read_uint16()  # The current node's index if no right child.
            self.unknown0x04 = reader.read_uint16()  # Always the same as left_child_index.
            self.next_sibling_index = reader.read_uint16()  # For left children the same as the parent's right index.
            self.visibility_group_index = reader.read_uint16()
            self.visibility_group_count = reader.read_uint16()

    class VisibilityGroupTreeRange:
        def __init__(self, reader):
            self.unknown0x00 = reader.read_singles(3)
            self.unknown0x0c = reader.read_singles(3)

    def __init__(self, reader):
        self.header = self.Header(reader)
        current_pos = reader.tell()
        addon.log(2, "FSHP " + self.header.name_offset.name)
        # Load the LoD model array.
        reader.seek(self.header.lod_array_offset)
        self.lod_models = []
        for i in range(0, self.header.lod_count):
            self.lod_models.append(self.LodModel(reader))
        # Load the visibility group tree node array.
 #       reader.seek(self.header.visibility_group_tree_nodes_offset.to_file)
 #       self.visibility_group_tree_nodes = []
 #       for i in range(0, self.header.visibility_group_tree_node_count):
 #           self.visibility_group_tree_nodes.append(self.VisibilityGroupTreeNode(reader))
        # Load the visibility group tree range array.
 #       reader.seek(self.header.visibility_group_tree_ranges_offset.to_file)
 #       self.visibility_group_tree_ranges = []
 #       for i in range(0, self.header.visibility_group_tree_node_count):
 #           self.visibility_group_tree_ranges.append(self.VisibilityGroupTreeRange(reader))
        # Load the visibility group tree index array.
 #       reader.seek(self.header.visibility_group_tree_indices_offset.to_file)
        # Count might be incorrect, wiki says it is number of visibility groups of FSHP, but which LoD model?
 #       self.visibility_group_tree_indices = reader.read_uint16s(self.header.visibility_group_tree_node_count)
        reader.seek(current_pos)

class FmatSubsection:
    class Header:
        def __init__(self, reader):
            if reader.read_raw_string(4) != "FMAT":
                raise AssertionError("Invalid FMAT subsection header.")
            self.HeaderLength = reader.read_uint32()
            self.HeaderLength2 = reader.read_uint64()
            self.name_offset = BfresNameOffset(reader)
            self.padding = reader.read_uint32()
            self.render_info_offset = reader.read_uint64()
            self.render_info_index_group_offset = reader.read_uint64()
            self.shader_control_structure_offset = reader.read_uint64()
            self.unk = reader.read_uint64()
            self.texture_attribute_selector_array_offset = reader.read_uint64()
            self.unk2 = reader.read_uint64()
            self.texture_selector_array_offset = reader.read_uint64()
            self.texture_attribute_selector_index_group_offset = reader.read_uint64()
            self.material_param_array_offset = reader.read_uint64()
            self.material_param_index_group_offset = reader.read_uint64()
            self.material_param_data_offset = reader.read_uint64()
            self.user_param_offset = reader.read_uint64()
            self.user_index_group_offset = reader.read_uint64()
            self.viotile_flags_offset = reader.read_uint64()
            self.user_offset = reader.read_uint64()
            self.sampler_slot_offset = reader.read_uint64()
            self.texture_slot_offset = reader.read_uint64()
            self.flags = reader.read_uint32() 
            self.index = reader.read_uint16()  # The index in the FMDL FMAT index group.
            self.render_param_count = reader.read_uint16()
            self.texture_selector_count = reader.read_byte()
            self.texture_attribute_selector_count = reader.read_byte()  # Equal to texture_selector_count
            self.material_param_count = reader.read_uint16()
            self.viotile_param_count = reader.read_uint16()
            self.material_param_data_size = reader.read_uint16()
            self.raw_param_size = reader.read_uint16()  # 0x00000001, 0x00000001, 0x00000002
            self.user_count = reader.read_uint16()  # 0x00000001, 0x00000001, 0x00000002
            self.padding = reader.read_uint32()

    class RenderParameter:
        class Type(enum.IntEnum):
            Unknown8BytesNull = 0x00
            Unknown2Floats = 0x01
            StringOffset = 0x02

        def __init__(self, reader):
            self.unknown0x00 = reader.read_uint16()  # 0x0000, 0x0001
            self.type = reader.read_byte()  # self.Type
            self.unknown0x03 = reader.read_byte()  # 0x00
            self.variable_name_offset = BfresNameOffset(reader)
            # Read the value, depending on self.type.
            if self.type == self.Type.Unknown8BytesNull:
                self.value = reader.read_bytes(8)
            elif self.type == self.Type.Unknown2Floats:
                self.value = reader.read_singles(2)
            elif self.type == self.Type.StringOffset:
                self.value = BfresNameOffset(reader)

    class MaterialStructure:
        def __init__(self, reader):
            self.unknown0x00 = reader.read_uint32()  # < 0x00000014
            self.unknown0x04 = reader.read_uint16()  # 0x0028
            self.unknown0x06 = reader.read_uint16()  # 0x0240, 0x0242 or 0x0243
            self.unknown0x08 = reader.read_uint32()  # 0x49749732, 0x49749736
            self.unknown0x0c = reader.read_uint32()  # < 0x0000000e
            self.unknown0x10 = reader.read_single()  # < 1.0
            self.unknown0x14 = reader.read_uint16()  # 0x00cc
            self.unknown0x16 = reader.read_uint16()  # 0x0000, 0x0100
            self.unknown0x18 = reader.read_uint32()  # 0x00000000
            self.unknown0x1c = reader.read_uint16()  # 0x2001
            self.unknown0x1e = reader.read_byte()  # 0x01, 0x05
            self.unknown0x1f = reader.read_byte()  # 0x01, 0x04
            self.unknown0x20 = reader.read_uint32s(4)  # all 0x00000000

    class ShaderControl:
        def __init__(self, reader):
            self.shader_1_name_offset = BfresNameOffset(reader)  # Probably
            self.shader_2_name_offset = BfresNameOffset(reader)  # Probably
            self.unknown0x08 = reader.read_uint32()  # 0x00000000, 0x00000001
            self.vertex_shader_input_count = reader.read_byte()
            self.pixel_shader_input_count = reader.read_byte()
            self.param_count = reader.read_uint16()
            self.vertex_shader_input_index_group_offset = BfresOffset(reader)
            self.pixel_shader_input_index_group_offset = BfresOffset(reader)
            self.param_index_group_offset = BfresOffset(reader)
            # Load the vertex shader input index group (mapping FVTX attribute names to vertex shader variables).
            reader.seek(self.vertex_shader_input_index_group_offset.to_file)
            self.vertex_shader_index_group = IndexGroup(reader, lambda r: r.read_0_string())
            # Load the pixel shader input index group (mapping FVTX attribute names to pixel shader variables).
            reader.seek(self.pixel_shader_input_index_group_offset.to_file)
            self.pixel_shader_index_group = IndexGroup(reader, lambda r: r.read_0_string())
            # Load the parameter index group (mapping uniform variables to a value which is always a string).
            reader.seek(self.param_index_group_offset.to_file)
            self.param_index_group = IndexGroup(reader, lambda r: r.read_0_string())

    class TextureSelector:
        def __init__(self, reader):
            self.name_offset = BfresNameOffset(reader)  
            self.padding = reader.read_uint32()
            addon.log(3, "Texture " + self.name_offset.name)

    class SamplerSelectors:
        def __init__(self, reader):
            self.name_offset = BfresNameOffset(reader)
            self.padding = reader.read_uint32()
            addon.log(6, "Sampler " + self.name_offset.name)

    class MaterialParameter:
        class Type(enum.IntEnum):
            Int32 = 0x04
            Float = 0x0c
            Vector2f = 0x0d
            Vector3f = 0x0e
            Vector4f = 0x0f
            Matrix2x3 = 0x1e

        def __init__(self, reader):
            self.type = reader.read_byte()  # self.Type
            self.size = reader.read_byte()
            self.value_offset = reader.read_uint16()  # Offset in the FMAT material parameter data array.
            self.unknown0x04 = reader.read_uint32()  # 0xffffffff
            self.unknown0x08 = reader.read_uint32()  # 0x00000000
            self.index = reader.read_uint16()
            self.index_again = reader.read_uint16()  # same as self.index
            self.variable_name_offset = BfresNameOffset(reader)

    class ShadowParameter:
        def __init__(self, reader):
            self.variable_name_offset = BfresNameOffset(reader)
            self.unknown0x04 = reader.read_uint16()  # 0x0001
            self.unknown0x06 = reader.read_byte()  # type or offset?
            self.unknown0x07 = reader.read_byte()  # 0x00
            self.value = reader.read_uint32()

    def __init__(self, reader):
        self.header = self.Header(reader)
        current_pos = reader.tell()
        addon.log(2, "FMAT " + self.header.name_offset.name)
        self.texture_selector_array = []
        self.sampler_names = []
        reader.seek(self.header.texture_attribute_selector_array_offset)
        for i in range(0, self.header.texture_selector_count):
            self.texture_selector_array.append(self.TextureSelector(reader))
            tex_sel_pos = reader.tell()
			
            reader.seek(self.header.texture_attribute_selector_index_group_offset + 24 + i * 16)
            reader.seek(8, 1)
            self.sampler_names.append(self.SamplerSelectors(reader))
            reader.seek(tex_sel_pos)
        reader.seek(current_pos)

        # Load the render parameter index group.
       # reader.seek(self.header.render_param_index_group_offset.to_file)
       # self.render_param_index_group = IndexGroup(reader, lambda r: self.RenderParameter(reader))
        # Load the material structure. Purpose unknown.
       # reader.seek(self.header.material_structure_offset.to_file)
       # self.material_structure = self.MaterialStructure(reader)
        # Load the shader control structure.
       # reader.seek(self.header.shader_control_structure_offset.to_file)
      #  self.shader_control = self.ShaderControl(reader)
        # Load the texture selector array.

        # Load the texture attribute selector index group.

        # Load the material parameter index group.
        # reader.seek(self.header.material_param_index_group_offset.to_file)
        # self.material_param_index_group = IndexGroup(reader, lambda r: self.MaterialParameter(r))
        # # Load the material parameter data array.
        # reader.seek(self.header.material_param_data_offset.to_file)
        # self.material_param_data = reader.read_bytes(self.header.material_param_data_size)
        # # Load the values of the material parameters stored in the material parameter data array.
        # for node in self.material_param_index_group[1:]:
            # material_param = node.data
            # offset = material_param.value_offset
            # if material_param.type == self.MaterialParameter.Type.Int32:
                # material_param.value = struct.unpack(">i", self.material_param_data[offset:offset + 4])[0]
            # elif material_param.type == self.MaterialParameter.Type.Float:
                # material_param.value = struct.unpack(">f", self.material_param_data[offset:offset + 4])[0]
            # elif material_param.type == self.MaterialParameter.Type.Vector2f:
                # material_param.value = struct.unpack(">2f", self.material_param_data[offset:offset + 8])
            # elif material_param.type == self.MaterialParameter.Type.Vector3f:
                # material_param.value = struct.unpack(">3f", self.material_param_data[offset:offset + 12])
            # elif material_param.type == self.MaterialParameter.Type.Vector4f:
                # material_param.value = struct.unpack(">4f", self.material_param_data[offset:offset + 16])
            # elif material_param.type == self.MaterialParameter.Type.Matrix2x3:
                # material_param.value = struct.unpack(">6f", self.material_param_data[offset:offset + 24])
        # # Load the shadow parameter index group if it exists.
        # if self.header.shadow_param_index_group_offset:
            # reader.seek(self.header.shadow_param_index_group_offset.to_file)
            # self.shadow_param_index_group = IndexGroup(reader, lambda r: self.ShadowParameter(r))
