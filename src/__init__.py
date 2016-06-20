bl_info = {
    "name": "Nintendo BFRES format",
    "description": "Import-Export BFRES mesh, UV's, materials and textures",
    "author": "Syroot",
    "version": (0, 4, 0),
    "blender": (2, 75, 0),
    "location": "File > Import-Export",
    "warning": "This add-on is under development.",
    "wiki_url": "https://github.com/Syroot/io_scene_bfres/wiki",
    "tracker_url": "https://github.com/Syroot/io_scene_bfres/issues",
    "support": "COMMUNITY",
    "category": "Import-Export"
}

# Reload the classes when reloading add-ons in Blender with F8.
if "bpy" in locals():
    import importlib
    if "log" in locals():
        print("Reloading: " + str(log))
        importlib.reload(log)
    if "binary_io" in locals():
        print("Reloading: " + str(binary_io))
        importlib.reload(binary_io)
    if "yaz0" in locals():
        print("Reloading: " + str(yaz0))
        importlib.reload(yaz0)
    if "bfres_common" in locals():
        print("Reloading: " + str(bfres_common))
        importlib.reload(bfres_common)
    if "bfres_fmdl" in locals():
        print("Reloading: " + str(bfres_fmdl))
        importlib.reload(bfres_fmdl)
    if "bfres_ftex" in locals():
        print("Reloading: " + str(bfres_ftex))
        importlib.reload(bfres_ftex)
    if "bfres_embedded" in locals():
        print("Reloading: " + str(bfres_embedded))
        importlib.reload(bfres_embedded)
    if "bfres_file" in locals():
        print("Reloading: " + str(bfres_file))
        importlib.reload(bfres_file)
    if "importing" in locals():
        print("Reloading: " + str(importing))
        importlib.reload(importing)

import bpy
from . import log
from . import yaz0
from . import binary_io
from . import bfres_common
from . import bfres_fmdl
from . import bfres_ftex
from . import bfres_embedded
from . import bfres_file
from . import importing

class BfresAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    tex_conv_path = bpy.props.StringProperty(
        name='TexConv Path',
        description='Path of the proprietary TexConv utility to convert textures with.',
        subtype='FILE_PATH'
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'tex_conv_path')

def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(importing.ImportOperator.menu_func_import)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(importing.ImportOperator.menu_func_import)

# Register classes of the add-on when Blender runs this script.
if __name__ == "__main__":
    register()
