#!/usr/bin/env python3

from dataclasses import dataclass, field
import importlib.util
import importlib.metadata
from importlib.machinery import ModuleSpec
import os
import pathlib
import toml
from typing import ClassVar
from typing_extensions import Self


def find_pyproject_toml(module_name: str) -> pathlib.Path:

    spec: ModuleSpec | None = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None:
        raise Exception(f"Couldn't find a module spec for `{module_name}`. Is it installed?")

    # spec.origin gives us the location of the modules __init__.py,
    # so the parent of spec.origin is our module root
    path_to_package: pathlib.Path = pathlib.Path(spec.origin).parent
    # Move up through the parents of our module origin to find the first pyproject.toml
    for parent in path_to_package.parents:
        toml_path: pathlib.Path = parent / "pyproject.toml"
        if toml_path.exists():
            return toml_path

    raise Exception(f"Found `{module_name}`, but failed to find pyproject.toml")


def process_pyproject_toml(pyproject_toml_path: pathlib.Path) -> dict:
    
    if not pyproject_toml_path.exists():
        raise Exception(f"pyproject.toml not found at path `{str(pyproject_toml_path)}`")

    try:
        toml_data: dict = toml.load(pyproject_toml_path)
    except (TypeError, toml.TomlDecodeError) as e:
        raise Exception(f"Failed to process toml file. Exception was: {e}")

    return toml_data


@dataclass
class ToyboxTableSpec:
    # Top-level name of the pyproject.toml "table" that contains toybox-specific metadata.
    TABLE_HEADER: ClassVar[str] = "toybox"
    # List of locations that we'll look for launch files in this package, relative to package_root.
    # Can be paths or filenames.
    LAUNCH_FILES: ClassVar[str] = "launch-files"
    # The locations that we'll look for message files in this package. Relative to package_root.
    # Can be a path or a filename.
    MESSAGE_FILES: ClassVar[str] = "message-files"
    # The locations that we'll search for misc. "resources" for this package. Relative to package root.
    # Can be a path or a filename.
    RESOURCE_FILES: ClassVar[str] = "resources"

    TBX_NAMESPACE: ClassVar[str] = "tbx."
    TBX_NODES: ClassVar[str] = TBX_NAMESPACE + "nodes"

@dataclass
class ToyboxMetadata:
    # Name of the package. Since toybox packages are python packages, this is easy.
    package_name: str
    # The location of the package root (i.e., where the pyproject.toml file is).
    package_root: pathlib.Path
    # The locations that we'll look for launch files in this package, relative to package_root.
    # Can be a path or a filename.
    launch_file_locations: list[str] = field(default_factory=list)
    # The locations that we'll look for message files in this package. Relative to package_root.
    # Can be a path or a filename.
    message_file_locations: list[str] = field(default_factory=list)
    # The locations that we'll search for misc. "resources" for this package. Relative to package root.
    # Can be a path or a filename.
    resource_file_locations: list[str] = field(default_factory=list)
    # Launchable node "entrypoints". Matches what would be returned by importlib.metadata.
    launchable_nodes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def extract_from_toml(cls, toml_path: pathlib.Path) -> Self | None:

        try:
            toml_data: dict = process_pyproject_toml(pyproject_toml_path=toml_path)
        except Exception as e:
            raise Exception(f"Failed to process toml. Exception was: {e}")
        
        # Grab the top-level "project" and "tools" mappings, 
        # since our metadata could be in either of them.
        project: dict = toml_data.get("project")
        tools: dict | None = toml_data.get("tool", None)
        
        # TBX nodes use python entrypoints for discoverability (for now).
        # That means that they are held in project.entry-points.`tbx.nodes`.
        launchable_nodes: dict | None = None
        entrypoints: dict | None = project.get("entry-points", None)
        if entrypoints is not None:
            launchable_nodes = entrypoints.get(ToyboxTableSpec.TBX_NODES, None)

        # The toybox "table" is under `tools.toybox`.
        tbx_data: dict | None = None
        if tools is not None:
            tbx_data = tools.get(ToyboxTableSpec.TABLE_HEADER, None)

        # This pyproject.toml doesn't have any toybox fields in it, so it doesn't
        # get to be a toybox package.
        if tbx_data is None and launchable_nodes is None:
            return None
        
        # Actually grab the fields from pyproject.toml. ALL FIELDS ARE OPTIONAL.
        meta: ToyboxMetadata = ToyboxMetadata(package_name=project["name"], package_root=toml_path.parent)
        meta.launch_file_locations = tbx_data.get(ToyboxTableSpec.LAUNCH_FILES, [])
        meta.message_file_locations = tbx_data.get(ToyboxTableSpec.MESSAGE_FILES, [])
        meta.resource_file_locations = tbx_data.get(ToyboxTableSpec.RESOURCE_FILES, [])
        meta.launchable_nodes = launchable_nodes if launchable_nodes else {}

        return meta

    def search_for_file_in_paths(self, file_name: str, paths: list[str]) -> pathlib.Path | None:

        for path in paths:
            file_path: pathlib.Path = self.package_root / path
            if not file_path.exists():
                raise Exception(f"Given search path `{file_path}` doesn't exist.")
            
            # First, we need to know if the provided path was a directory or a file...
            if file_path.is_file() and file_path.stem == file_name:
                return file_path
            elif file_path.is_dir():
                # Does the launch file we're looking for exist in this directory?
                if (file_path / file_name).exists():
                    return file_path / file_name

    def get_launch_file(self, launch_file_name: str) -> pathlib.Path:

        launch_file: pathlib.Path | None = self.search_for_file_in_paths(
            file_name=launch_file_name,
            paths=self.launch_file_locations)
        if launch_file is None:
            raise Exception(f"Couldn't find launch file `{launch_file_name}` on any configured path: {[str(self.package_root / path) for path in self.launch_file_locations]}")
    
        return launch_file

    def get_message_file(self, message_file_name: str) -> pathlib.Path:

        message_file: pathlib.Path | None = self.search_for_file_in_paths(
            file_name=message_file_name,
            paths=self.message_file_locations)
        if message_file is None:
            raise Exception(f"Couldn't find launch file `{message_file_name}` on any configured path: {[str(self.package_root / path) for path in self.message_file_locations]}")
    
        return message_file

    def get_resource(self, resource_name: str) -> pathlib.Path:

        resource_file: pathlib.Path | None = self.search_for_file_in_paths(
            file_name=resource_name,
            paths=self.resource_file_locations)
        if resource_file is None:
            raise Exception(f"Couldn't find launch file `{resource_name}` on any configured path: {[str(self.package_root / path) for path in self.resource_file_locations]}")
    
        return resource_file

    def _walk(
        self,
        path: pathlib.Path, 
        ignore_files: list[str] | None = None,
        indent: str = "    "
    ) -> str:
        """
        To generate human-readable output, we can walk a path and generate a "human-readable"
        string for it.
        This is slightly different than os.walk (and uses os.walk internally).
        """
        ignore_files: list[str] = ignore_files if ignore_files else []
        
        returned: str = ""
        
        if not path.exists() or path.name in ignore_files:
            pass
        elif not path.is_dir():
            # If the path is just a file, we're done at this point.
            returned += f"{indent}-> {path.name}: ({path})\n"
        else:
            for root, dirs, files in os.walk(path):
                dirs.sort()
                indent_num: int = 1
                root_path: pathlib.Path = pathlib.Path(root)

                relative_path: pathlib.Path = root_path.relative_to(path)
                if relative_path.name in ignore_files:
                    continue
                elif len(files) == 0:
                    continue
                if relative_path != pathlib.Path("."):
                    returned += f"{indent * indent_num}-> {relative_path}: ({root_path})\n"
                    indent_num += 1
                
                if root_path.name in ignore_files:
                    continue
                for file in [pathlib.Path(x) for x in files]:
                    if file.name in ignore_files:
                        continue
                    returned += f"{indent*indent_num}-> {file.name}\n"
                
                indent_num += 1

        return returned

    def human_readable(self) -> str:
        """
        Return a human-readable string containing metadata info.
        This ISN'T __str__() because I don't necessarily want this output appearing
        in my logs.
        """
        # Junk files that I'm sick of seeing in my output.
        ignore_files: list[str] = ["__pycache__", "__init.py__"]

        s: str = ""
        s += f"{self.package_name}: \n"
        s += f"* Location: {self.package_root}\n"
        s += f"* Launch files: \n"
        for location in self.launch_file_locations:
            path: pathlib.Path = pathlib.Path(f"{self.package_root}/{location}")
            s += self._walk(path=path, ignore_files=ignore_files)
        s += f"* Messages: \n"
        for message_path in self.message_file_locations:
            path: pathlib.Path = pathlib.Path(f"{self.package_root}/{message_path}")
            s += self._walk(path=path, ignore_files=ignore_files)
        s += f"* Resources: \n"
        for resource_path in self.resource_file_locations:
            path: pathlib.Path = pathlib.Path(f"{self.package_root}/{resource_path}")
            s += f"    -> {path}\n"
        s += f"* Nodes: \n"
        for node_key, node_val in self.launchable_nodes.items():
            s += f"    -> {node_key}: ({node_val})\n"

        return s


def find_tbx_packages() -> dict[str,ToyboxMetadata]:

    tbx_packages: dict[str,ToyboxMetadata] = {}

    for distn in importlib.metadata.distributions():

        module_name: str = distn.name
        try:
            toml_path: pathlib.Path = find_pyproject_toml(module_name=distn.name)
        except Exception as e:
            continue

        meta: ToyboxMetadata | None = ToyboxMetadata.extract_from_toml(toml_path=toml_path)
        if meta is None:
            continue

        tbx_packages[module_name] = meta

    return tbx_packages


def main() -> None:

    packages: dict[str,ToyboxMetadata] = find_tbx_packages()
    print(packages["toybox_examples"].get_launch_file(pathlib.Path("example.launch.py")))
    print(packages["toybox_examples"].get_launch_file(pathlib.Path("pico_bridge.launch.py")))


if __name__ == "__main__":
    main()