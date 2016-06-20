# io_scene_bfres

This is a Blender add-on to import the BFRES model file format, which is typically used in several Nintendo Wii U games.

It is currently in the alpha stage and supports the following features:
- Completely load the BFRES file structure into memory.
- Convert FMDL sections, creating FSHP polygons and FMAT materials.
- Converting all FTEX textures on the fly by delegating the conversion task to TexConv.

The following features are not implemented yet:
- Multiple UV layers
- Skeleton

Other features missing from the lists above are not planned at this time.

Installation
=====

- Go to your Blender installation directory inside the version folder, and then to `scripts` > `addons`.
- Create a new folder called "io_scene_bfres".
- Copy in all `*.py` files from the `src` folder of this repository.
- In the Blender user preferences, enable the 'Import-Export: Nintendo BFRES format' add-on.
- Configure the path to the TexConv.exe utility if you want to import textures.

License
=======

<a href="http://www.wtfpl.net/"><img src="http://www.wtfpl.net/wp-content/uploads/2012/12/wtfpl.svg" height="20" alt="WTFPL" /></a> WTFPL

    Copyright © 2016 syroot.com <admin@syroot.com>
    This work is free. You can redistribute it and/or modify it under the
    terms of the Do What The Fuck You Want To Public License, Version 2,
    as published by Sam Hocevar. See the COPYING file for more details.
