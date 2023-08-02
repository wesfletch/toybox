# import os
# import importlib

# current_dir: str = os.path.dirname(os.path.realpath(__file__))
# suffix: str = "_pb2.py"

# pb2_files: 'List[str]' = []
# for file in os.listdir(current_dir):
#     print(f"{current_dir}/{file}")
#     if os.path.isfile(f"{current_dir}/{file}") and file.endswith(suffix):
#         pb2_files.append(file)

# for f in pb2_files:
#     f_stripped: str = f[:-len(suffix)]

#     importlib.import_module(name=f[:-3], package=".")
#     # exec(f"import {f[:-3]} as {f_stripped}")

# print(pb2_files)

# stolen: https://stackoverflow.com/a/53888787
import importlib
import pkgutil

for mod_info in pkgutil.walk_packages(__path__, __name__ + '.'):
    mod = importlib.import_module(mod_info.name)

    # Emulate `from mod import *`
    try:
        names = mod.__dict__['__all__']
    except KeyError:
        names = [k for k in mod.__dict__ if not k.startswith('_')]

    globals().update({k: getattr(mod, k) for k in names})