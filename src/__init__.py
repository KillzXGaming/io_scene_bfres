bl_info = {
    "name": "Nintendo BFRES format",
    "description": "Import-Export BFRES mesh, UV's, materials and textures",
    "author": "Syroot",
    "version": (0, 5, 1),
    "blender": (2, 77, 0),
    "location": "File > Import-Export",
    "warning": "This add-on is under development.",
    "wiki_url": "https://github.com/Syroot/io_scene_bfres/wiki",
    "tracker_url": "https://github.com/Syroot/io_scene_bfres/issues",
    "support": 'COMMUNITY',
    "category": "Import-Export"
}

# Reload the package modules when reloading add-ons in Blender with F8.
if "bpy" in locals():
    import importlib
    if "addon" in locals():
        importlib.reload(addon)
    if "binary_io" in locals():
        importlib.reload(binary_io)
    if "yaz0" in locals():
        importlib.reload(yaz0)
    if "bfres_common" in locals():
        importlib.reload(bfres_common)
    if "bfres_fmdl" in locals():
        importlib.reload(bfres_fmdl)
    if "bfres_ftex" in locals():
        importlib.reload(bfres_ftex)
    if "bfres_embedded" in locals():
        importlib.reload(bfres_embedded)
    if "bfres_file" in locals():
        importlib.reload(bfres_file)
    if "importing" in locals():
        importlib.reload(importing)
import bpy
from . import importing


def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(importing.ImportOperator.menu_func_import)


def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(importing.ImportOperator.menu_func_import)
