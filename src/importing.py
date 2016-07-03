import bmesh
import bpy
import bpy_extras
import io
import os
import subprocess
from .log import Log
from .binary_io import BinaryWriter
from .yaz0 import Yaz0Compression
from .bfres_file import BfresFile

class ImportOperator(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = "import_scene.bfres"
    bl_label = "Import BFRES"
    bl_options = {"UNDO"}

    filename_ext = ".bfres"
    filter_glob = bpy.props.StringProperty(
        default="*.bfres;*.szs",
        options={"HIDDEN"}
    )
    filepath = bpy.props.StringProperty(
        name="File Path",
        description="Filepath used for importing the BFRES or compressed SZS file",
        maxlen=1024,
        default=""
    )
    import_textures = bpy.props.BoolProperty(
        name="Import Textures",
        description="Loads the embedded textures, requires TexConv to be set up in the add-on preferences.",
        default=True
    )
    force_reimport = bpy.props.BoolProperty(
        name="Force Reimport",
        description="Reimports textures even when they were already found in an existing work folder.",
        default=False
    )
    merge_seams = bpy.props.BoolProperty(
        name="Merge Seam Vertices",
        description="Remerge vertices which were split to create UV seams.",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        addon_prefs = context.user_preferences.addons[__package__].preferences
        # Import Textures / Force Reimport
        row = layout.row()
        row.enabled = bool(addon_prefs.tex_conv_path)
        row.prop(self, "import_textures")
        row.prop(self, "force_reimport")
        # Merge Seams
        layout.prop(self, "merge_seams")

    def execute(self, context):
        importer = Importer(self, context, self.properties.filepath)
        return importer.run()

    @staticmethod
    def menu_func_import(self, context):
        self.layout.operator(ImportOperator.bl_idname, text="Nintendo BFRES (.bfres/.szs)")

class Importer:
    def __init__(self, operator, context, filepath):
        self.operator = operator
        self.context = context
        # Keep a link to the add-on preferences.
        self.addon_prefs = context.user_preferences.addons[__package__].preferences
        # Extract path information.
        self.filepath = filepath
        self.directory = os.path.dirname(self.filepath)
        self.filename = os.path.basename(self.filepath)
        self.fileext = os.path.splitext(self.filename)[1].upper()
        # Create work directories for temporary files.
        self.work_directory = os.path.join(self.directory, self.filename + ".work")
        self.gtx_directory = os.path.join(self.work_directory, "gtx")
        self.dds_directory = os.path.join(self.work_directory, "dds")
        os.makedirs(self.work_directory, exist_ok=True)
        os.makedirs(self.gtx_directory, exist_ok=True)
        os.makedirs(self.dds_directory, exist_ok=True)

    def run(self):
        # Ensure to have a stream with decompressed data.
        if self.fileext == ".SZS":
            raw = io.BytesIO(Yaz0Compression.decompress(open(self.filepath, "rb")))
        else:
            raw = open(self.filepath, "rb")
        bfres_file = BfresFile(raw)
        raw.close()
        # Import the data into Blender objects.
        self._convert_bfres(bfres_file)
        return {"FINISHED"}

    def _convert_bfres(self, bfres):
        # Go through the FTEX sections and export them to GTX, then to DDS.
        if self.operator.import_textures and self.addon_prefs.tex_conv_path:
            for ftex_node in bfres.ftex_index_group[1:]:
                self._convert_ftex(ftex_node.data)
        # Go through the FMDL sections which map to a Blender object.
        for fmdl_node in bfres.fmdl_index_group[1:]:
            self._convert_fmdl(fmdl_node.data)

    def _convert_ftex(self, ftex):
        # Export the FTEX section referenced by the texture selector as a GTX file.
        texture_name = ftex.header.file_name_offset.name
        gtx_filename = os.path.join(self.gtx_directory, texture_name + ".gtx")
        dds_filename = os.path.join(self.dds_directory, texture_name + ".dds")
        # Only export when the file does not exist yet, or reimporting is forced.
        if self.operator.force_reimport or not os.path.isfile(dds_filename):
            Log.write(0, "Exporting     '" + texture_name + "'...")
            ftex.export_gtx(open(gtx_filename, "wb"))
            # Decompress the GTX texture file with.
            Log.write(0, "Decompressing '" + texture_name + "'...")
            subprocess.call([self.addon_prefs.tex_conv_path,
                "-i", gtx_filename,
                "-f", "GX2_SURFACE_FORMAT_TCS_R8_G8_B8_A8_SRGB",
                "-o", gtx_filename])
            # Convert the decompressed GTX texture to DDS.
            Log.write(0, "Converting    '" + texture_name + "'...")
            subprocess.call([self.addon_prefs.tex_conv_path,
                "-i", gtx_filename,
                "-o", dds_filename])

    def _convert_fmdl(self, fmdl):
        # Create an object for this FMDL in the current scene.
        fmdl_obj = bpy.data.objects.new(fmdl.header.file_name_offset.name, None)
        bpy.context.scene.objects.link(fmdl_obj)
        # Go through the polygons in this model.
        for fshp_node in fmdl.fshp_index_group[1:]:
            self._convert_fshp(fmdl, fmdl_obj, fshp_node.data)

    def _convert_fshp(self, fmdl, fmdl_obj, fshp):
        # Get the vertices and indices of the most detailled LoD model.
        vertices = fmdl.fvtx_array[fshp.header.buffer_index].get_vertices()
        lod_model = fshp.lod_models[0]
        indices = lod_model.index_buffer.indices
        # Create a bmesh to represent the FSHP polygon.
        bm = bmesh.new()
        # Go through the vertices (starting at the given offset) and add them to the bmesh.
        # This would also add the vertices of all other LoD models. As there is no direct way to get the number of
        # vertices required for the current LoD model (the game does not need that), get the last indexed one with max.
        last_vertex = max(indices) + 1
        for vertex in vertices[lod_model.skip_vertices:lod_model.skip_vertices + last_vertex]:
            bm_vert = bm.verts.new((vertex.p0[0], -vertex.p0[2], vertex.p0[1])) # Exchange Y with Z, mirror new Y
            #bm_vert.normal = vertex.n0 # Blender does not correctly support custom normals, and they look weird.
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        # Connect the faces (they are organized as a triangle list) and smooth shade them.
        for i in range(0, len(indices), 3):
            try:
                face = bm.faces.new(bm.verts[j] for j in indices[i:i + 3])
            except ValueError:
                pass # TODO: Handle multiple same faces correctly (they're probably part of other UV layers).
            face.smooth = True
        # TODO: Import all UV layers, not only the first one.
        # If UV's exist, set the UV coordinates by iterating through the face loops and getting their vertex' index.
        if not vertices[0].u0 is None: # Check the first vertex if it contains the required data.
            uv_layer = bm.loops.layers.uv.new()
            for face in bm.faces:
                for loop in face.loops:
                    uv = vertices[loop.vert.index + lod_model.skip_vertices].u0
                    loop[uv_layer].uv = (uv[0], 1 - uv[1]) # Flip Y
        # Optimize the mesh if requested.
        if self.operator.merge_seams:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0)
        # Write the bmesh data back to a new mesh.
        fshp_mesh = bpy.data.meshes.new(fshp.header.name_offset.name)
        bm.to_mesh(fshp_mesh)
        bm.free()
        # Apply the referenced material to the mesh if TexConv is set up.
        fmat = fmdl.fmat_index_group[fshp.header.material_index + 1].data
        if self.addon_prefs.tex_conv_path:
            fshp_mesh.materials.append(self._get_fmat_material(fmat))
        # Create an object to represent the mesh with.
        fshp_obj = bpy.data.objects.new(fshp_mesh.name, fshp_mesh)
        fshp_obj.parent = fmdl_obj
        bpy.context.scene.objects.link(fshp_obj)

    def _get_fmat_material(self, fmat):
        # Return a previously created material or make a new one.
        material_name = fmat.header.name_offset.name
        material = bpy.data.materials.get(material_name)
        if material is not None:
            return material
        material = bpy.data.materials.new(material_name)
        material.specular_intensity = 0 # Do not make materials without specular map shine exaggeratedly.
        material.use_transparency = True
        material.alpha = 0
        material.specular_alpha = 0
        # Convert and load the textures into the materials' texture slots.
        if len(fmat.texture_selector_array):
            for texture, attrib in zip(fmat.texture_selector_array, fmat.texture_attribute_selector_index_group[1:]):
                texture_name = texture.name_offset.name
                attribute_name = self._get_attribute_type(texture_name, attrib.name_offset.name)
                # Check if the attribute is supported at all, and create a correspondingly configured texture slot if it is.
                if attribute_name != "b": # TODO: Bake textures are not supported yet.
                    slot = material.texture_slots.add()
                    slot.texture = self._get_ftex_texture(texture_name, attribute_name)
                    if attribute_name == "a":
                        # Diffuse (albedo) map.
                        slot.use_map_alpha = True
                    elif attribute_name == "s":
                        # Specular map.
                        slot.use_map_color_diffuse = False
                        slot.use_map_specular = True
                        slot.use_map_color_spec = True
                    elif attribute_name == "n":
                        # Normal map.
                        slot.use_map_color_diffuse = False
                        slot.use_map_normal = True
                        slot.texture.use_normal_map = True
                    elif attribute_name == "e":
                        # Emmissive map.
                        # TODO: Slot settings might be wrong (s. Wild Woods' glowing circles).
                        slot.use_map_color_diffuse = False
                        slot.use_map_emit = True
        return material

    def _get_ftex_texture(self, texture_name, attribute_type):
        # Return a previously created texture if it exists.
        texture = bpy.data.textures.get(texture_name)
        if texture is not None:
            return texture
        # Load a new texture from the DDS file.
        image_file_name = os.path.join(self.dds_directory, texture_name) + ".dds"
        # TexConv has a bug as it exports A8R8G8B8 data as a X8R8G8B8 DDS. Patch the DDS for diffuse textures.
        if attribute_type == "a":
            with BinaryWriter(open(image_file_name, "r+b")) as writer:
                writer.seek(0x68) # DDS_HEADER->DDS_PIXELFORMAT->dwABitMask
                writer.write_uint32(0xFF000000) # Mask of the alpha data.
        texture = bpy.data.textures.new(texture_name, "IMAGE")
        texture.image = bpy.data.images.load(image_file_name, check_existing=True)
        return texture

    def _get_attribute_type(self, texture_name, attribute_name):
        # Since the attributes provided to textures are often wrong, try to find the real attribute via texture name.
        attribute_type = attribute_name[1]
        if "_Alb" in texture_name:
            fixed_attribute_type = "a"
        elif "_Emm" in texture_name:
            fixed_attribute_type = "e"
        elif "_Nrm" in texture_name:
            fixed_attribute_type = "n"
        elif "_Spm" in texture_name:
            fixed_attribute_type = "s"
        else:
            fixed_attribute_type = attribute_type
            Log.write(0, "Warning: Texture '" + texture_name + "': Unknown attribute '" + attribute_name + "'")
        # Log a correction.
        if attribute_type != fixed_attribute_type:
            Log.write(0, "Warning: Texture '" + texture_name + "': fixing type of attribute '" + attribute_name
                + "' to '" + fixed_attribute_type + "'")
        return attribute_type
