import bmesh
import bpy
import bpy_extras
import io
import os
import subprocess
from . import addon
from . import binary_io
from . import yaz0
from . import bfres_file


class ImportOperator(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    """Load a BFRES model file"""
    bl_idname = "import_scene.bfres"
    bl_label = "Import BFRES"
    bl_options = {'UNDO'}

    filename_ext = ".bfres"
    filter_glob = bpy.props.StringProperty(default="*.bfres;*.szs", options={'HIDDEN'})
    filepath = bpy.props.StringProperty(name="File Path", description="Filepath used for importing the BFRES or compressed SZS file", maxlen=1024)
    # Mesh Options
    lod_model_index = bpy.props.IntProperty(name="LoD Model Index", description="The index of the LoD model to import if it exists. Lower means more detail.", min=0)
    merge_seams = bpy.props.BoolProperty(name="Merge Seam Vertices", description="Merge vertices again which were split to create UV seams.", default=True)
    # Texture Options
    extract_textures = bpy.props.BoolProperty(name="Extract Textures", description="Extracts embedded textures into a work folder.", default=True)
    force_extract = bpy.props.BoolProperty(name="Force", description="Extracts textures even when they were already found in an existing work folder.")
    tex_import_diffuse = bpy.props.BoolProperty(name="Import Diffuse", description="Imports textures mapped to the 'a' attribute.", default=True)
    tex_import_normal = bpy.props.BoolProperty(name="Import Normal", description="Imports textures mapped to the 'n' attribute.", default=True)
    tex_import_specular = bpy.props.BoolProperty(name="Import Specular", description="Imports textures mapped to the 's' attribute.", default=True)
    tex_import_emissive = bpy.props.BoolProperty(name="Import Emissive", description="Imports textures mapped to the 'e' attribute.", default=True)
    tex_import_bake = bpy.props.BoolProperty(name="Import Bake", description="Imports textures mapped to the 'b' attribute.", default=False)
    tex_import_other = bpy.props.BoolProperty(name="Import Other", description="Imports textures mapped to unknown attributes.")
    # MK8Muunt
    parent_ob_name = bpy.props.StringProperty(name="Name of a parent object to which FSHP mesh objects will be added.")
    mat_name_prefix = bpy.props.StringProperty(name="Text prepended to material names to keep them unique.")

    def draw(self, context):
        # Mesh Options
        box = self.layout.box()
        box.label("Mesh Options:", icon='OUTLINER_OB_MESH')
        box.prop(self, "lod_model_index")
        box.prop(self, "merge_seams")
        # Texture Options
        tex_conv_path = context.user_preferences.addons[__package__].preferences.tex_conv_path
        box = self.layout.box()
        box.label("Texture Options:", icon='TEXTURE_DATA')
        if tex_conv_path:
            split = box.split(0.65)
            split.prop(self, "extract_textures")
            if self.extract_textures:
                split.prop(self, "force_extract")
                box.prop(self, "tex_import_diffuse")
                box.prop(self, "tex_import_normal")
                box.prop(self, "tex_import_specular")
                box.prop(self, "tex_import_emissive")
                box.prop(self, "tex_import_bake")
                box.prop(self, "tex_import_other")
        else:
            box.label("TexConv path not configured.", icon='ERROR')

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
        self.work_directory = os.path.join(self.directory, "{}.work".format(self.filename))
        self.gtx_directory = os.path.join(self.work_directory, "gtx")
        self.dds_directory = os.path.join(self.work_directory, "dds")
        os.makedirs(self.work_directory, exist_ok=True)
        os.makedirs(self.gtx_directory, exist_ok=True)
        os.makedirs(self.dds_directory, exist_ok=True)

    def run(self):
        # Ensure to have a stream with decompressed data.
        if self.fileext == ".SZS":
            raw = io.BytesIO(yaz0.decompress(open(self.filepath, "rb")))
        else:
            raw = open(self.filepath, "rb")
        bfres = bfres_file.BfresFile(raw)
        raw.close()
        # Import the data into Blender objects.
        self._convert(bfres)
        return {'FINISHED'}

    def _convert(self, bfres):
        # Go through the FTEX sections and export them to GTX, then convert to DDS.
        if self.operator.extract_textures and self.addon_prefs.tex_conv_path:
            for ftex_node in bfres.ftex_index_group[1:]:
                self._extract_ftex(ftex_node.data)
        # Go through the FMDL sections which map to a Blender object.
        for fmdl_node in bfres.fmdl_index_group[1:]:
            self._convert_fmdl(fmdl_node.data)

    def _extract_ftex(self, ftex):
        # Export the FTEX section referenced by the texture selector as a GTX file.
        texture_name = ftex.header.file_name_offset.name
        gtx_filename = os.path.join(self.gtx_directory, "{}.gtx".format(texture_name))
        dds_filename = os.path.join(self.dds_directory, "{}.dds".format(texture_name))
        # Only export when the file does not exist yet, or extracting is forced.
        if self.operator.force_extract or not os.path.isfile(dds_filename):
            addon.log(4, "Exporting     '{}'...".format(texture_name))
            ftex.export_gtx(open(gtx_filename, "wb"))
            # Decompress the GTX texture file with.
            addon.log(4, "Decompressing '{}'...".format(texture_name))
            subprocess.call([self.addon_prefs.tex_conv_path,
                             "-i", gtx_filename,
                             "-f", "GX2_SURFACE_FORMAT_TCS_R8_G8_B8_A8_SRGB",
                             "-o", gtx_filename])
            # Convert the decompressed GTX texture to DDS.
            addon.log(4, "Converting    '{}'...".format(texture_name))
            subprocess.call([self.addon_prefs.tex_conv_path,
                             "-i", gtx_filename,
                             "-o", dds_filename])

    def _convert_fmdl(self, fmdl):
        # If no parent is given, create an empty object holding the FSHP child mesh objects of this FMDL.
        if self.operator.parent_ob_name:
            fmdl_ob = None
        else:
            fmdl_ob = bpy.data.objects.new(fmdl.header.file_name_offset.name, None)
            Importer._add_object_to_group(fmdl_ob, "BFRES")
            bpy.context.scene.objects.link(fmdl_ob)
        # Go through the polygons in this model and create mesh objects representing them.
        for fshp_node in fmdl.fshp_index_group[1:]:
            fshp_ob = self._convert_fshp(fmdl, fshp_node.data)
            if self.operator.parent_ob_name:
                # Just parent the mesh object to the given object.
                fshp_ob.parent = bpy.data.objects[self.operator.parent_ob_name]
            else:
                # Parent to the empty FMDL object and link it to the scene.
                fshp_ob.parent = fmdl_ob
                Importer._add_object_to_group(fshp_ob, "BFRES")
                bpy.context.scene.objects.link(fshp_ob)

    def _convert_fshp(self, fmdl, fshp):
        # Get the vertices and indices of the closest LoD model.
        vertices = fmdl.fvtx_array[fshp.header.buffer_index].get_vertices()
        lod_model = fshp.lod_models[min(self.operator.lod_model_index, len(fshp.lod_models) - 1)]
        indices = lod_model.index_buffer.indices
        # Create a bmesh to represent the FSHP polygon.
        bm = bmesh.new()
        # Go through the vertices (starting at the given offset) and add them to the bmesh.
        # This would also add the vertices of all other LoD models. As there is no direct way to get the number of
        # vertices required for the current LoD model (the game does not need that), get the last indexed one with max.
        last_vertex = max(indices) + 1
        for vertex in vertices[lod_model.skip_vertices:lod_model.skip_vertices + last_vertex]:
            bm.verts.new((vertex.p0[0], -vertex.p0[2], vertex.p0[1]))  # Exchange Y with Z, mirror new Y
            # _.normal = vertex.n0 # Blender does not correctly support custom normals, and they look weird.
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        # Connect the faces (they are organized as a triangle list) and smooth shade them.
        for i in range(0, len(indices), 3):
            try:
                face = bm.faces.new(bm.verts[j] for j in indices[i:i + 3])
                face.smooth = True
            except ValueError:
                pass  # TODO: Handle multiple same faces correctly (they're probably part of other UV layers).
        # TODO: Import all UV layers, not only the first one.
        # If UV's exist, set the UV coordinates by iterating through the face loops and getting their vertex' index.
        if vertices[0].u0 is not None:  # Check the first vertex if it contains the required data.
            uv_layer = bm.loops.layers.uv.new()
            for face in bm.faces:
                for loop in face.loops:
                    uv = vertices[loop.vert.index + lod_model.skip_vertices].u0
                    loop[uv_layer].uv = (uv[0], 1 - uv[1])  # Flip Y
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
        # Return an object which represents the mesh.
        return bpy.data.objects.new(fshp_mesh.name, fshp_mesh)

    def _get_fmat_material(self, fmat):
        # Return a previously created material or make a new one.
        material_name = fmat.header.name_offset.name
        if self.operator.mat_name_prefix:
            material_name = "{}.{}".format(self.operator.mat_name_prefix, material_name)
        material = bpy.data.materials.get(material_name)
        if material:
            return material
        material = bpy.data.materials.new(material_name)
        material.specular_intensity = 0  # Do not make materials without specular map shine exaggeratedly.
        material.use_transparency = True
        material.alpha = 0
        material.specular_alpha = 0
        # Convert and load the textures into the materials' texture slots.
        if fmat.texture_selector_array:
            for texture, attrib in zip(fmat.texture_selector_array, fmat.texture_attribute_selector_index_group[1:]):
                texture_name = texture.name_offset.name
                attribute_name = Importer._get_attribute_type(texture_name, attrib.name_offset.name)
                # Check if the attribute should be imported, then create a correspondingly configured texture slot.
                if self._check_attribute_import(attribute_name):
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

    def _check_attribute_import(self, attribute):
        return (attribute == "a" and self.operator.tex_import_diffuse) \
               or (attribute == "n" and self.operator.tex_import_normal) \
               or (attribute == "s" and self.operator.tex_import_specular) \
               or (attribute == "e" and self.operator.tex_import_emissive) \
               or (attribute == "b" and self.operator.tex_import_bake) \
               or self.operator.tex_import_other

    def _get_ftex_texture(self, texture_name, attribute_type):
        # Check for a previously created texture with the same name to return (names seem to be unique).
        texture = bpy.data.textures.get(texture_name)
        if texture:
            return texture
        # Otherwise, load a new texture from the DDS file.
        image_file_name = "{}.dds".format(os.path.join(self.dds_directory, texture_name))
        # TexConv has a bug as it exports A8R8G8B8 data as a X8R8G8B8 DDS. Patch the DDS for diffuse textures.
        if attribute_type == "a":
            with binary_io.BinaryWriter(open(image_file_name, "r+b")) as writer:
                writer.seek(0x68)  # DDS_HEADER->DDS_PIXELFORMAT->dwABitMask
                writer.write_uint32(0xFF000000)  # Mask of the alpha data.
        texture = bpy.data.textures.new(texture_name, 'IMAGE')
        texture.image = bpy.data.images.load(image_file_name, check_existing=True)
        return texture

    @staticmethod
    def _get_attribute_type(texture_name, attribute_name):
        # Since the attributes provided to textures are often wrong, try to find the real attribute via texture name.
        # TODO: This correction often doesn't do much good and maps them badly too.
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
            addon.log(4, "Warning: Texture '{}': Unknown attribute '{}'".format(texture_name, attribute_name))
        # Log a correction.
        if attribute_type != fixed_attribute_type:
            addon.log(4, "Warning: Texture '{}': fixing type of attribute '{}' to '{}'".format(texture_name, attribute_name, fixed_attribute_type))
        return attribute_type

    @staticmethod
    def _add_object_to_group(ob, group_name):
        # Get or create the required group.
        group = bpy.data.groups.get(group_name, bpy.data.groups.new(group_name))
        # Link the provided object to it.
        if ob.name not in group.objects:
            group.objects.link(ob)
