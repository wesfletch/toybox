#!/usr/bin/env python3

from dataclasses import dataclass
import glob
import grpc_tools.protoc
import pathlib
from proto_schema_parser.parser import Parser
import proto_schema_parser.ast as proto_ast
import re
import sys
from typing import Iterable

from toybox_core.metadata import ToyboxMetadata, find_tbx_packages


@dataclass
class MessageSpec:
    message_name: str
    python_package_name: str
    proto_file_path: pathlib.Path
    proto_pkg_name: str

    @property
    def qualified_name(self) -> str:
        """
        The name that would be used to import this message from outside of its containing file.
        """
        return f"{self.proto_pkg_name}.{self.message_name}"
    

def get_message_paths(metadatas: Iterable[ToyboxMetadata]) -> list[pathlib.Path]:

    message_paths: list[pathlib.Path] = []
    for metadata in metadatas:
        for relative_path in metadata.message_file_locations:
            abs_path: pathlib.Path = metadata.package_root / relative_path
            message_paths.append(abs_path)
    return message_paths


def find_msg_file(msg_file: str, search_paths: list[pathlib.Path]) -> pathlib.Path | None:

    for search_path in search_paths:
        path: pathlib.Path = search_path / msg_file
        if path.exists():
            return path
        
    return None


def get_message_packages(metadatas: Iterable[ToyboxMetadata]) -> dict[str, list[MessageSpec]]:

    returned: dict[str, list[MessageSpec]] = {}

    for meta in metadatas:
        msg_paths: list[pathlib.Path] = get_message_paths([meta])
        
        all_messages: list[str] = []
        for msg_path in msg_paths:
            all_messages += \
                [f"{proto_file}" for proto_file in glob.glob(str(msg_path) + "/" + "**/*.proto", recursive=True)]

        for proto_file in all_messages:
            proto_file_text: str = open(proto_file, 'r').read()
            parsed_proto: proto_ast.File = Parser().parse(proto_file_text)
            
            proto_pkg_name: str | None = None
            messages: list[proto_ast.Message] = []
            for element in parsed_proto.file_elements:
                if isinstance(element, proto_ast.Package):
                    proto_pkg_name = element.name
                elif isinstance(element, proto_ast.Message):
                    messages.append(element.name)

            if proto_pkg_name not in returned.keys():
                returned[proto_pkg_name] = []

            for message in messages:
                spec: MessageSpec = MessageSpec(
                    message_name=message, 
                    python_package_name=meta.package_name, 
                    proto_file_path=pathlib.Path(proto_file),
                    proto_pkg_name=proto_pkg_name)
                
                returned[proto_pkg_name].append(spec)

    return returned


def generate_messages(
    message_path: pathlib.Path,
    import_msgs_paths: list[pathlib.Path],
    pbuf_output_dir: str, 
    grpc_output_dir: str, 
    pyi_output: str
) -> bool:

    SCRIPT_NAME: str = "grpc_tools.protoc"
    proto_path: list[str] = [f"--proto_path={str(path)}/" for path in import_msgs_paths]
    python_out_str: str = f"--python_out={pbuf_output_dir}"
    grpc_python_out_str: str = f"--grpc_python_out={grpc_output_dir}"
    pyi_output_str: str = f"--pyi_out={pyi_output}"

    glob_str: str = str(message_path) + "/" + "**/*.proto"
    proto_files: list[str] = \
        [f"{proto_file}" for proto_file in glob.glob(glob_str, recursive=True)]

    proto_files_rel_paths: list[str] = [f"{pathlib.Path(proto_file).relative_to(message_path)}" for proto_file in glob.glob(glob_str, recursive=True)]
    print(f".proto files to be built: {proto_files_rel_paths}")

    protoc_args: list[str] = [SCRIPT_NAME]
    protoc_args += proto_path                   # --proto_path IMPORTS, searched in order
    protoc_args.append(python_out_str),         # --python_out PROTOBUF python output
    protoc_args.append(grpc_python_out_str),    # --grpc_python_out GRPC python output
    protoc_args.append(pyi_output_str),         # --pyi_out PYTHON interface file output
    protoc_args += proto_files

    arg_string: str  = "".join([f"{arg} " for arg in protoc_args])
    print(f"Building messages with command: {arg_string}\n")

    return grpc_tools.protoc.main(protoc_args) == 0


def modify_generated_python(
    message_path: pathlib.Path, 
    pbuf_output_dir: str, 
    grpc_output_dir: str,
    pyi_output_dir: str | None = None,
) -> bool:

    ALL_PROTOS: dict[str, list[MessageSpec]] = get_message_packages(find_tbx_packages().values())

    # proto_files: list[str] =  [f"{proto_file}" for proto_file in glob.glob(str(message_path) + "/*.proto")]
    glob_str: str = str(message_path) + "/" + "**/*.proto"
    proto_files: list[str] = \
        [f"{proto_file}" for proto_file in glob.glob(glob_str, recursive=True)]

    for proto_msg in proto_files:

        proto_path: pathlib.Path = pathlib.Path(proto_msg)

        proto_text: str = open(proto_path, 'r').read()

        parsed_proto: proto_ast.File = Parser().parse(proto_text)
        imports: list[proto_ast.Import] = []
        messages: list[proto_ast.Message] = []
        package: str | None = None

        # Figure out our imports; p.s. it's SUPER annoying that proto_schema_parser apparently doesn't
        # do this for me. Having to iterate through the AST and isinstance() everything is obnoxious.
        for element in parsed_proto.file_elements:
            if isinstance(element, proto_ast.Import):
                imports.append(element)
            elif isinstance(element, proto_ast.Message):
                messages.append(element)
            elif isinstance(element, proto_ast.Package):
                package = element.name
        
        # Resolve all of the file imports: go and find the file that is being imported.
        imported_messages: list[MessageSpec] = []
        for imported_file in imports:
            proto_pkg, proto_file_name = imported_file.name.split('/')
            proto_file = proto_file_name.removesuffix(".proto")

            # Find the spec on our proto file in the MessageSpecs
            message_specs: list[MessageSpec] | None = ALL_PROTOS.get(proto_pkg, None)
            if message_specs is None:
                raise Exception(f"No message specs for package {proto_pkg}")

            # Find the specific message spec we're looking for
            # TODO: this is dumb, just build it into the data structure
            # message_spec: MessageSpec | None = None
            for spec in message_specs:
                if spec.proto_file_path.stem == proto_file:
                    imported_messages.append(spec)

        # Add all of the specs from the messages package, even if they're not explicitly imported,
        # because the auto-generated python DOES import them when needed
        imported_messages += ALL_PROTOS.get(package, None)

        outfiles: list[pathlib.Path] = []
        proto_file_rel: str = str(proto_path.relative_to(message_path)).removesuffix(".proto")
        pbuf_output_file: pathlib.Path = pathlib.Path(f"{pbuf_output_dir}/{proto_file_rel}_pb2.py")
        grpc_output_file: pathlib.Path = pathlib.Path(f"{grpc_output_dir}/{proto_file_rel}_pb2_grpc.py")
        outfiles.append(pbuf_output_file)
        outfiles.append(grpc_output_file)

        if pyi_output_dir is not None:
            pyi_out_file: pathlib.Path = pathlib.Path(f"{pyi_output_dir}/{proto_file_rel}_pb2.pyi")
            outfiles.append(pyi_out_file)

        print(f"Updating files: {[str(outfile) for outfile in outfiles]}")

        # Figure out which specific messages we're importing for each message
        for _ in messages:
            result: bool = update_file(
                specs=imported_messages,
                output_files=outfiles)
            if not result:
                raise Exception("Fuck!")

    return True

def update_file(
    specs: list[MessageSpec],
    output_files: list[pathlib.Path]
) -> bool:

    for out_file in output_files:
        assert out_file.exists(), f"File to be updated {out_file} does not exist."

        output_txt: str = ""

        pattern: re.Pattern = re.compile(pattern=f"^from ([A-Za-z0-9_]*) import ([A-Za-z0-9_]*_pb2)", flags=re.MULTILINE)
        
        # Step line-by-line through the file, checking for lines that are attempting
        # imports so that we can "fix" them.
        with open(out_file, 'r') as f:
            for line in f:
                # Is this an import line? If not, just move on.
                match: re.Match | None = re.search(pattern=pattern, string=line)
                if match is None:
                    output_txt += line
                    continue

                # Unpack the import line
                assert len(match.groups()) == 2, f"Got wrong number of capture groups for {line}, expected 2, got {len(match.groups())}"
                proto_pkg_name, proto_file = match.groups()
                proto_file_name: str = str(proto_file).removesuffix("_pb2") + ".proto"

                # With the info from the import line, see if we have a relevant
                # MessageSpec that points to the message the file is ACTUALLY looking for
                spec_we_want: MessageSpec | None = None
                for spec in specs:
                    if spec.proto_file_path.name == proto_file_name and \
                        spec.proto_pkg_name == proto_pkg_name:
                        spec_we_want = spec
                if spec_we_want is None:
                    raise Exception(f"Couldn't find the spec we were looking for to match line: `{line}`")

                # Actually perform the replacement.
                replace_line: str = f"from {spec_we_want.python_package_name}.{spec_we_want.proto_pkg_name} import {spec_we_want.proto_file_path.stem}_pb2"
                print(f"In file {out_file}, performing replacement: `{str(pattern.pattern)}` --> `{replace_line}`")
                new_line = re.sub(
                    pattern=pattern,
                    repl=replace_line,
                    string=line)

                output_txt += new_line
        
        # Push our changes to the output file.
        with open(out_file, 'w') as f:
            f.write(output_txt)

    return True


def build_messages(package_name: str | None = None) -> bool:

    tbx_packages: dict[str,ToyboxMetadata] = find_tbx_packages()
    build_paths: list[pathlib.Path] 

    # Even if we're only building one package, we need to context
    # of all of the message paths to ensure that imports will work.
    ALL_MSG_PATHS: list[pathlib.Path] = get_message_paths(tbx_packages.values())

    if package_name is not None:
        package: ToyboxMetadata | None = tbx_packages.get(package_name, None)
        if package is None:
            print(f"Package {package_name} not found.")
            return False
        build_paths = get_message_paths([package])
    else:
        build_paths = get_message_paths(tbx_packages.values())


    for message_path in build_paths:

        print('------------------------------------------')
        print(f"Building messages at path: {message_path}")
        print('------------------------------------------')

        result: bool = generate_messages(
            message_path=message_path,
            import_msgs_paths=ALL_MSG_PATHS,
            pbuf_output_dir=message_path.parent,
            pyi_output=message_path.parent,
            grpc_output_dir=message_path.parent)
        if not result:
            print("Failed to build messages.")
            exit(1)

        print("Sucessfully built messages.\n")

        
        result = modify_generated_python(
            message_path=message_path, 
            pbuf_output_dir=message_path.parent,
            grpc_output_dir=message_path.parent,
            pyi_output_dir=message_path.parent)
        if not result:
            print("Failed to update built output files.")
            exit(1)
        
        print("Successfully updated output files.")

def main() -> None:
    
    if len(sys.argv) > 1:
        build_messages(package_name=sys.argv[1])
    else:
        build_messages()

    
if __name__ == "__main__":
    main()

