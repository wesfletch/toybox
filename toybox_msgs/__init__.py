from . import primitive
from . import state
from . import core

# # stolen: https://stackoverflow.com/a/53888787
# import importlib
# import os
# import pkgutil

# print(__path__)
# print(__name__)
# print()
# path = "".join(__path__)
# print(path)
# print()
# # subdirs = [x[1] for x in os.walk(path)]
# subdirs = next(os.walk(path))[1]
# subdirs = [os.path.join(path, x) for x in subdirs]
# print(subdirs)

# for mod_info in pkgutil.walk_packages(subdirs, __name__ + '.' + ):
#     print(mod_info)
#     mod = importlib.import_module(mod_info.name)

#     # Emulate `from mod import *`
#     try:
#         names = mod.__dict__['__all__']
#     except KeyError:
#         names = [k for k in mod.__dict__ if not k.startswith('_')]

#     globals().update({k: getattr(mod, k) for k in names})