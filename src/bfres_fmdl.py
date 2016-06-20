import enum
import mathutils
import numpy
import struct
from .log import Log
from .bfres_common import BfresOffset, BfresNameOffset, IndexGroup

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
            self.file_name_offset = BfresNameOffset(reader)
            self.data_offset = BfresOffset(reader) # Wiki says end of string table, but that's where FMDL data begins.
            self.fskl_offset = BfresOffset(reader)
            self.fvtx_array_offset = BfresOffset(reader)
            self.fshp_index_group_offset = BfresOffset(reader)
            self.fmat_index_group_offset = BfresOffset(reader)
            self.param_index_group_offset = BfresOffset(reader)
            self.fvtx_count = reader.read_uint16()
            self.fshp_count = reader.read_uint16()
            self.fmat_count = reader.read_uint16()
            self.param_count = reader.read_uint16()
            self.unknown0x28 = reader.read_uint32() # Maybe an unused face count.

    class Parameter:
        def __init__(self, reader):
            self.variable_name_offset = BfresNameOffset(reader)
            self.unknown0x04 = reader.read_uint16() # 0x0001
            self.unknown0x06 = reader.read_uint16() # 0x0000
            self.unknown0x08 = reader.read_single()

    def __init__(self, reader):
        self.header = self.Header(reader)
        Log.write(1, "FMDL " + self.header.file_name_offset.name)
        # Load the FSKL subsection.
        reader.seek(self.header.fskl_offset.to_file)
        self.fskl = FsklSubsection(reader)
        # Load the FVTX subsections.
        reader.seek(self.header.fvtx_array_offset.to_file)
        self.fvtx_array = []
        for i in range(0, self.header.fvtx_count):
            self.fvtx_array.append(FvtxSubsection(reader))
        # Load the FSHP index group.
        reader.seek(self.header.fshp_index_group_offset.to_file)
        self.fshp_index_group = IndexGroup(reader, lambda r: FshpSubsection(r))
        # Load the FMAT index group.
        reader.seek(self.header.fmat_index_group_offset.to_file)
        self.fmat_index_group = IndexGroup(reader, lambda r: FmatSubsection(r))
        # Load the parameter index group if it exists.
        if self.header.param_index_group_offset:
            reader.seek(self.header.param_index_group_offset.to_file)
            self.param_index_group = IndexGroup(reader, lambda r: self.Parameter(r))

class FsklSubsection:
    class Header:
        def __init__(self, reader):
            if reader.read_raw_string(4) != "FSKL":
                raise AssertionError("Invalid FSKL subsection header.")
            self.unknown0x04 = reader.read_uint16()
            self.unknown0x06 = reader.read_uint16() # 0x1100, 0x1200
            self.bone_count = reader.read_uint16()
            self.inv_count = reader.read_uint16() # Count of elements in inverse index and matrix arrays.
            self.extra_index_count = reader.read_uint16() # Additional elements in inverse index array.
            self.unknown0x0e = reader.read_uint16()
            self.bone_index_group_array_offset = BfresOffset(reader)
            self.bone_array_offset = BfresOffset(reader)
            self.inv_index_array_offset = BfresOffset(reader)
            self.inv_matrix_array_offset = BfresOffset(reader)

    class Bone:
        CHILD_BONE_COUNT = 4 # Wiki says parent bones, but where does that make sense to have multiple parents?

        def __init__(self, reader):
            self.name_offset = BfresNameOffset(reader)
            Log.write(3, "Bone " + self.name_offset.name)
            self.index = reader.read_uint16()
            self.child_indices = []
            for i in range(0, self.CHILD_BONE_COUNT):
                self.child_indices.append(reader.read_uint16()) # 0xFFFF for no child.
            self.unknown0x0e = reader.read_uint16()
            self.flags = reader.read_uint16() # Unknown purpose.
            self.unknown0x12 = reader.read_uint16() # 0x1001
            self.scale = reader.read_vector3f()
            self.rotation = reader.read_quaternion()
            self.translation = reader.read_vector3f()
            self.padding = reader.read_uint32() # 0x00000000.

    def __init__(self, reader):
        self.header = self.Header(reader)
        Log.write(2, "FSKL")
        # Load the bone index group.
        reader.seek(self.header.bone_index_group_array_offset.to_file)
        self.bone_index_group = IndexGroup(reader, lambda r: self.Bone(r))
        # Load the inverse index array.
        reader.seek(self.header.inv_index_array_offset.to_file)
        self.inv_indices = []
        for i in range(0, self.header.inv_count + self.header.extra_index_count):
            self.inv_indices.append(reader.read_uint16())
        # Load the inverse matrix array.
        reader.seek(self.header.inv_matrix_array_offset.to_file)
        self.inv_matrices = []
        for i in range(0, self.header.inv_count):
            self.inv_matrices.append(reader.read_matrix4x3())

class FvtxSubsection:
    class Header:
        def __init__(self, reader):
            if reader.read_raw_string(4) != "FVTX":
                raise AssertionError("Invalid FVTX subsection header.")
            self.attribute_count = reader.read_byte()
            self.buffer_count = reader.read_byte()
            self.index = reader.read_uint16() # The index in the FMDL FVTX array.
            self.vertex_count = reader.read_uint32()
            self.unknown0x0c = reader.read_uint32() # 0x00000000 (normally), 0x04000000
            self.attribute_array_offset = BfresOffset(reader)
            self.attribute_index_group_offset = BfresOffset(reader)
            self.buffer_array_offset = BfresOffset(reader)
            self.padding = reader.read_uint32() # 0x00000000

    class Attribute:
        def __init__(self, reader):
            self.name_offset = BfresNameOffset(reader)
            index_and_offset = reader.read_uint32() # XXYYYYYY, where X is the buffer index and Y the offset.
            self.buffer_index = index_and_offset >> 24 # The index of the buffer containing this attrib.
            self.element_offset = index_and_offset & 0x00FFFFFF # Offset in each element.
            self.format = reader.read_uint32()
            # Get a method parsing this attribute format.
            self.parser = self._parsers.get(self.format, None)
            if not self.parser:
                Log.write(0, "Warning: Attribute " + self.name_offset.name + ": unknown format " + str(self.format))
                #raise NotImplementedError("Attribute " + self.name_offset.name + ": unknown format " + str(self.format))

        def _parse_2x_8bit_normalized(self, buffer, offset):
            offset += self.element_offset
            return buffer.data[offset] / 0xFF, buffer.data[offset + 1] / 0xFF

        def _parse_2x_16bit_normalized(self, buffer, offset):
            offset += self.element_offset
            values = struct.unpack(">2H", buffer.data[offset:offset + 4])
            return tuple(x / 0xFFFF for x in values)

        def _parse_1x_8bit(self, buffer, offset):
            offset += self.element_offset
            return buffer.data[offset]

        def _parse_2x_8bit(self, buffer, offset):
            offset += self.element_offset
            return struct.unpack(">2B", buffer.data[offset:offset + 2])

        def _parse_4x_8bit(self, buffer, offset):
            offset += self.element_offset
            return struct.unpack(">4B", buffer.data[offset:offset + 4])

        def _parse_2x_16bit_short_as_float(self, buffer, offset):
            offset += self.element_offset
            return tuple(x / 0x7FFF for x in struct.unpack(">2H", buffer.data[offset:offset + 4]))

        def _parse_4x_8bit_signed(self, buffer, offset):
            offset += self.element_offset
            return struct.unpack(">4b", buffer.data[offset:offset + 4])

        def _parse_3x_10bit_signed(self, buffer, offset):
            offset += self.element_offset
            integer = struct.unpack(">I", buffer.data[offset:offset + 4])[0]
            # 8-bit values are aligned in 'integer' as follows:
            #   Bit: 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32
            # Value:  0  1  x  x  x  x  x  x  x  x  0  1  y  y  y  y  y  y  y  y  0  1  z  z  z  z  z  z  z  z  0  0
            # Those are then divided by 511 to retrieve the decimal value.
            x = ((integer & 0x3FC00000) >> 22) / 511
            y = ((integer & 0x000FF000) >> 12) / 511
            z = ((integer & 0x000003FC) >>  2) / 511
            return x, y, z

        def _parse_2x_16bit_float(self, buffer, offset):
            offset += self.element_offset
            return numpy.frombuffer(buffer.data, ">f2", 2, offset)

        def _parse_2x_32bit_float(self, buffer, offset):
            offset += self.element_offset
            return struct.unpack(">2f", buffer.data[offset:offset + 8])

        def _parse_4x_16bit_float(self, buffer, offset):
            offset += self.element_offset
            return numpy.frombuffer(buffer.data, ">f2", 4, offset)

        def _parse_3x_32bit_float(self, buffer, offset):
            offset += self.element_offset
            return struct.unpack(">3f", buffer.data[offset:offset + 12])

        _parsers = {
            0x00000004: _parse_2x_8bit_normalized,
            0x00000007: _parse_2x_16bit_normalized,
            0x0000000a: _parse_4x_8bit,
            0x00000100: _parse_1x_8bit,
            0x00000104: _parse_2x_8bit,
            0x0000010a: _parse_4x_8bit,
            0x00000207: _parse_2x_16bit_short_as_float,
            0x0000020a: _parse_4x_8bit_signed,
            0x0000020b: _parse_3x_10bit_signed,
            0x00000808: _parse_2x_16bit_float,
            0x0000080d: _parse_2x_32bit_float,
            0x0000080f: _parse_4x_16bit_float,
            0x00000811: _parse_3x_32bit_float
        }

    class Buffer:
        def __init__(self, reader):
            self.unknown0x00 = reader.read_uint32() # 0x00000000
            self.size_in_bytes = reader.read_uint32()
            self.unknown0x08 = reader.read_uint32() # 0x00000000
            self.stride = reader.read_uint16() # Size of each element in the buffer.
            self.unknown0x0e = reader.read_uint16() # 0x0001
            self.unknown0x10 = reader.read_uint32() # 0x00000000
            self.data_offset = BfresOffset(reader)
            # Read in the raw data.
            current_pos = reader.tell()
            reader.seek(self.data_offset.to_file)
            self.data = reader.read_bytes(self.size_in_bytes)
            reader.seek(current_pos)

    class Vertex:
        def __init__(self):
            # Member names must be kept as they allow a simple mapping in self.get_vertices().
            self.p0 = None # Position
            self.n0 = None # Normal
            self.t0 = None # Tangent, lighting calculation
            self.b0 = None # Binormal, lighting calculation
            self.w0 = None # Blend weight, unknown purpose
            self.i0 = None # Blend index, unknown purpose
            self.u0 = None # UV texture coordinate layer 1
            self.u1 = None # UV texture coordinate layer 2
            self.u2 = None # UV texture coordinate layer 3
            self.u3 = None # UV texture coordinate layer 4
            self.c0 = None # Color for shadow mapping
            self.c1 = None # Color for shadow mapping

    def __init__(self, reader):
        self.header = self.Header(reader)
        Log.write(2, "FVTX")
        # Load the attribute index group.
        current_pos = reader.tell()
        reader.seek(self.header.attribute_index_group_offset.to_file)
        self.attribute_index_group = IndexGroup(reader, lambda r: self.Attribute(r))
        # Load the buffer array.
        reader.seek(self.header.buffer_array_offset.to_file)
        self.buffers = []
        for i in range(0, self.header.buffer_count):
            self.buffers.append(self.Buffer(reader))
        # Seek back as FVTX headers are read as an array.
        reader.seek(current_pos)

    def get_vertices(self):
        # Create an array of empty vertex instances.
        vertices = [self.Vertex() for i in range(0, self.header.vertex_count)]
        # Get the data by attributes, as the data can be separated into different data arrays.
        for attribute_node in self.attribute_index_group[1:]:
            attribute = attribute_node.data
            vertex_member = attribute.name_offset.name[1:] # Remove the underscore of the attribute name.
            buffer = self.buffers[attribute.buffer_index]
            if attribute.parser is None:
                # Dump the attribute data into a file for further investigation.
                for i, offset in enumerate(range(0, buffer.size_in_bytes, buffer.stride)):
                    setattr(vertices[i], vertex_member, (0, 0, 0))
            else:
                for i, offset in enumerate(range(0, buffer.size_in_bytes, buffer.stride)):
                    setattr(vertices[i], vertex_member, attribute.parser(attribute, buffer, offset))
        return vertices

class FshpSubsection:
    class Header:
        def __init__(self, reader):
            if reader.read_raw_string(4) != "FSHP":
                raise AssertionError("Invalid FSHP subsection header.")
            self.name_offset = BfresNameOffset(reader)
            self.unknown0x08 = reader.read_uint32() # 0x00000002
            self.index = reader.read_uint16() # The index in the FMDL FSHP index group.
            self.material_index = reader.read_uint16() # The index of the FMAT material for this polygon.
            self.bone_index = reader.read_uint16() # The index of the bone this polygon is transformed with.
            self.buffer_index = reader.read_uint16() # Same as self.index in MK8.
            self.fskl_index_array_count = reader.read_uint16() # Often 0x0000, unknown purpose, related to FSKL.
            self.unknown0x16 = reader.read_byte() # Tends to be 0x00 if fskl_index_array_count is 0x0000.
            self.lod_count = reader.read_byte()
            self.visibility_group_tree_node_count = reader.read_uint32()
            self.unknown0x1c = reader.read_single()
            self.fvtx_offset = BfresOffset(reader)
            self.lod_array_offset = BfresOffset(reader)
            self.fskl_index_array_offset = BfresOffset(reader)
            self.unknown0x2c = BfresOffset(reader) # 0x00000000
            self.visibility_group_tree_nodes_offset = BfresOffset(reader)
            self.visibility_group_tree_ranges_offset = BfresOffset(reader)
            self.visibility_group_tree_indices_offset = BfresOffset(reader)
            self.padding = reader.read_uint32() # 0x00000000

    class LodModel:
        class VisibilityGroup:
            def __init__(self, reader):
                self.index_byte_offset = reader.read_uint32() # Divide by 2 to get the array index; indices are 16-bit.
                self.index_count = reader.read_uint32()

        class IndexBuffer:
            def __init__(self, reader):
                self.unknown0x00 = reader.read_uint32() # 0x00000000
                self.size_in_bytes = reader.read_uint32() # Divide by 2 to get the number of array elements.
                self.unknown0x08 = reader.read_uint32() # 0x00000000
                self.unknown0x0c = reader.read_uint16() # 0x0000
                self.unknown0x0e = reader.read_uint16() # 0x0001
                self.unknown0x10 = reader.read_uint32() # 0x00000000
                self.data_offset = BfresOffset(reader)
                # Read in the raw data.
                reader.seek(self.data_offset.to_file)
                self.indices = reader.read_uint16s(self.size_in_bytes / 2)

        def __init__(self, reader):
            self.unknown0x00 = reader.read_uint32() # 0x00000004
            self.unknown0x04 = reader.read_uint32() # 0x00000004
            self.total_index_count = reader.read_uint32()
            self.visibility_group_count = reader.read_uint16()
            self.unknown0x0e = reader.read_uint16() # 0x0000
            self.visibility_group_offset = BfresOffset(reader)
            self.index_buffer_offset = BfresOffset(reader)
            self.skip_vertices = reader.read_uint32() # The number of elements to skip in the FVTX buffer.
            # Load the visibility group array.
            current_pos = reader.tell()
            reader.seek(self.visibility_group_offset.to_file)
            self.visibility_groups = []
            for i in range(0, self.visibility_group_count):
                self.visibility_groups.append(self.VisibilityGroup(reader))
            # Load the index buffer.
            reader.seek(self.index_buffer_offset.to_file)
            self.index_buffer = self.IndexBuffer(reader)
            # Seek back as multiple LoD models are stored in an array.
            reader.seek(current_pos)

    class VisibilityGroupTreeNode:
        def __init__(self, reader):
            self.left_child_index = reader.read_uint16() # The current node's index if no left child.
            self.right_child_index = reader.read_uint16() # The current node's index if no right child.
            self.unknown0x04 = reader.read_uint16() # Always the same as left_child_index.
            self.next_sibling_index = reader.read_uint16() # For left children the same as the parent's right index.
            self.visibility_group_index = reader.read_uint16()
            self.visibility_group_count = reader.read_uint16()

    class VisibilityGroupTreeRange:
        def __init__(self, reader):
            self.unknown0x00 = reader.read_vector3f()
            self.unknown0x0c = reader.read_vector3f()

    def __init__(self, reader):
        self.header = self.Header(reader)
        Log.write(2, "FSHP " + self.header.name_offset.name)
        # Load the LoD model array.
        reader.seek(self.header.lod_array_offset.to_file)
        self.lod_models = []
        for i in range(0, self.header.lod_count):
            self.lod_models.append(self.LodModel(reader))
        # Load the visibility group tree node array.
        reader.seek(self.header.visibility_group_tree_nodes_offset.to_file)
        self.visibility_group_tree_nodes = []
        for i in range(0, self.header.visibility_group_tree_node_count):
            self.visibility_group_tree_nodes.append(self.VisibilityGroupTreeNode(reader))
        # Load the visibility group tree range array.
        reader.seek(self.header.visibility_group_tree_ranges_offset.to_file)
        self.visibility_group_tree_ranges = []
        for i in range(0, self.header.visibility_group_tree_node_count):
            self.visibility_group_tree_ranges.append(self.VisibilityGroupTreeRange(reader))
        # Load the visibility group tree index array.
        reader.seek(self.header.visibility_group_tree_indices_offset.to_file)
        # Count might be incorrect, wiki says it is number of visibility groups of FSHP, but which LoD model?
        self.visibility_group_tree_indices = reader.read_uint16s(self.header.visibility_group_tree_node_count)

class FmatSubsection:
    class Header:
        def __init__(self, reader):
            if reader.read_raw_string(4) != "FMAT":
                raise AssertionError("Invalid FMAT subsection header.")
            self.name_offset = BfresNameOffset(reader)
            self.unknown0x08 = reader.read_uint32() # 0x00000001
            self.index = reader.read_uint16() # The index in the FMDL FMAT index group.
            self.render_param_count = reader.read_uint16()
            self.texture_selector_count = reader.read_byte()
            self.texture_attribute_selector_count = reader.read_byte() # Equal to texture_selector_count
            self.material_param_count = reader.read_uint16()
            self.material_param_data_size = reader.read_uint32()
            self.unknown0x18 = reader.read_uint32() # 0x00000001, 0x00000001, 0x00000002
            self.render_param_index_group_offset = BfresOffset(reader)
            self.material_structure_offset = BfresOffset(reader)
            self.shader_control_structure_offset = BfresOffset(reader)
            self.texture_selector_array_offset = BfresOffset(reader)
            self.texture_attribute_selector_array_offset = BfresOffset(reader)
            self.texture_attribute_selector_index_group_offset = BfresOffset(reader)
            self.material_param_array_offset = BfresOffset(reader)
            self.material_param_index_group_offset = BfresOffset(reader)
            self.material_param_data_offset = BfresOffset(reader)
            self.shadow_param_index_group_offset = BfresOffset(reader) # 0 if it does not exist.
            self.unknown0x44 = BfresOffset(reader) # Points to 12 0 bytes; 0 if it does not exist.

    class RenderParameter:
        class Type(enum.IntEnum):
            Unknown8BytesNull = 0x00
            Unknown2Floats    = 0x01
            StringOffset      = 0x02

        def __init__(self, reader):
            self.unknown0x00 = reader.read_uint16() # 0x0000, 0x0001
            self.type = reader.read_byte() # self.Type
            self.unknown0x03 = reader.read_byte() # 0x00
            self.variable_name_offset = BfresNameOffset(reader)
            # Read the value, depending on self.type.
            if self.type == self.Type.Unknown8BytesNull:
                self.value = reader.read_bytes(8)
            elif self.type == self.Type.Unknown2Floats:
                self.value = reader.read_vector2f()
            elif self.type == self.Type.StringOffset:
                self.value = BfresNameOffset(reader)

    class MaterialStructure:
        def __init__(self, reader):
            self.unknown0x00 = reader.read_uint32() # < 0x00000014
            self.unknown0x04 = reader.read_uint16() # 0x0028
            self.unknown0x06 = reader.read_uint16() # 0x0240, 0x0242 or 0x0243
            self.unknown0x08 = reader.read_uint32() # 0x49749732, 0x49749736
            self.unknown0x0c = reader.read_uint32() # < 0x0000000e
            self.unknown0x10 = reader.read_single() # < 1.0
            self.unknown0x14 = reader.read_uint16() # 0x00cc
            self.unknown0x16 = reader.read_uint16() # 0x0000, 0x0100
            self.unknown0x18 = reader.read_uint32() # 0x00000000
            self.unknown0x1c = reader.read_uint16() # 0x2001
            self.unknown0x1e = reader.read_byte() # 0x01, 0x05
            self.unknown0x1f = reader.read_byte() # 0x01, 0x04
            self.unknown0x20 = reader.read_uint32s(4) # all 0x00000000

    class ShaderControl:
        def __init__(self, reader):
            self.shader_1_name_offset = BfresNameOffset(reader) # Probably
            self.shader_2_name_offset = BfresNameOffset(reader) # Probably
            self.unknown0x08 = reader.read_uint32() # 0x00000000, 0x00000001
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
            self.name_offset = BfresNameOffset(reader) # Same as the FTEX name.
            Log.write(3, "Texture " + self.name_offset.name)
            self.ftex_offset = BfresOffset(reader)

    class TextureAttributeSelector:
        def __init__(self, reader):
            self.unknown0x00 = reader.read_byte() # 0x02
            self.unknown0x01 = reader.read_byte() # 0x00, 0x02, 0x04, 0x12
            self.unknown0x02 = reader.read_byte() # 0x00, 0x10, 0x12, 0x5a
            self.unknown0x03 = reader.read_byte() # near 0x00 or near 0x80 (flags?)
            self.unknown0x04 = reader.read_sbyte() # close to 0x00
            self.unknown0x05 = reader.read_byte() # small value
            self.unknown0x06 = reader.read_uint16() # flags?
            self.unknown0x08 = reader.read_uint32() # 0x80000000
            self.unknown0x0c = reader.read_uint32() # 0x00000000
            self.name_offset = BfresNameOffset(reader)
            index_and_unknown = reader.read_uint32()
            self.index = index_and_unknown >> 24
            self.unknown = index_and_unknown & 0x00FFFFFF

    class MaterialParameter:
        class Type(enum.IntEnum):
            Int32     = 0x04
            Float     = 0x0c
            Vector2f  = 0x0d
            Vector3f  = 0x0e
            Vector4f  = 0x0f
            Matrix2x3 = 0x1e

        def __init__(self, reader):
            self.type = reader.read_byte() # self.Type
            self.size = reader.read_byte()
            self.value_offset = reader.read_uint16() # Offset in the FMAT material parameter data array.
            self.unknown0x04 = reader.read_uint32() # 0xffffffff
            self.unknown0x08 = reader.read_uint32() # 0x00000000
            self.index = reader.read_uint16()
            self.index_again = reader.read_uint16() # same as self.index
            self.variable_name_offset = BfresNameOffset(reader)

    class ShadowParameter:
        def __init__(self, reader):
            self.variable_name_offset = BfresNameOffset(reader)
            self.unknown0x04 = reader.read_uint16() # 0x0001
            self.unknown0x06 = reader.read_byte() # type or offset?
            self.unknown0x07 = reader.read_byte() # 0x00
            self.value = reader.read_uint32()

    def __init__(self, reader):
        self.header = self.Header(reader)
        Log.write(2, "FMAT " + self.header.name_offset.name)
        # Load the render parameter index group.
        reader.seek(self.header.render_param_index_group_offset.to_file)
        self.render_param_index_group = IndexGroup(reader, lambda r: self.RenderParameter(reader))
        # Load the material structure. Purpose unknown.
        reader.seek(self.header.material_structure_offset.to_file)
        self.material_structure = self.MaterialStructure(reader)
        # Load the shader control structure.
        reader.seek(self.header.shader_control_structure_offset.to_file)
        self.shader_control = self.ShaderControl(reader)
        # Load the texture selector array.
        reader.seek(self.header.texture_selector_array_offset.to_file)
        self.texture_selector_array = []
        for i in range(0, self.header.texture_selector_count):
            self.texture_selector_array.append(self.TextureSelector(reader))
        # Load the texture attribute selector index group.
        if self.header.texture_attribute_selector_index_group_offset:
            reader.seek(self.header.texture_attribute_selector_index_group_offset.to_file)
            self.texture_attribute_selector_index_group = IndexGroup(reader, lambda r: self.TextureAttributeSelector(r))
        else:
            self.texture_attribute_selector_index_group = None
        # Load the material parameter index group.
        reader.seek(self.header.material_param_index_group_offset.to_file)
        self.material_param_index_group = IndexGroup(reader, lambda r: self.MaterialParameter(r))
        # Load the material parameter data array.
        reader.seek(self.header.material_param_data_offset.to_file)
        self.material_param_data = reader.read_bytes(self.header.material_param_data_size)
        # Load the values of the material parameters stored in the material parameter data array.
        for node in self.material_param_index_group[1:]:
            material_param = node.data
            offset = material_param.value_offset
            if material_param.type == self.MaterialParameter.Type.Int32:
                material_param.value = struct.unpack(">i", self.material_param_data[offset:offset + 4])[0]
            elif material_param.type == self.MaterialParameter.Type.Float:
                material_param.value = struct.unpack(">f", self.material_param_data[offset:offset + 4])[0]
            elif material_param.type == self.MaterialParameter.Type.Vector2f:
                material_param.value = struct.unpack(">2f", self.material_param_data[offset:offset + 8])
            elif material_param.type == self.MaterialParameter.Type.Vector3f:
                material_param.value = struct.unpack(">3f", self.material_param_data[offset:offset + 12])
            elif material_param.type == self.MaterialParameter.Type.Vector4f:
                material_param.value = struct.unpack(">4f", self.material_param_data[offset:offset + 16])
            elif material_param.type == self.MaterialParameter.Type.Matrix2x3:
                material_param.value = struct.unpack(">6f", self.material_param_data[offset:offset + 24])
        # Load the shadow parameter index group if it exists.
        if self.header.shadow_param_index_group_offset:
            reader.seek(self.header.shadow_param_index_group_offset.to_file)
            self.shadow_param_index_group = IndexGroup(reader, lambda r: self.ShadowParameter(r))
