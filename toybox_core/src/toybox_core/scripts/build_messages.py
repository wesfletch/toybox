#!/usr/bin/env python3

import glob
import grpc_tools.protoc
from typing import Iterable
import pathlib
from proto_schema_parser.parser import Parser
import proto_schema_parser.ast as proto_ast


from toybox_core.metadata import ToyboxMetadata, find_tbx_packages


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

def get_message_packages(metadatas: Iterable[ToyboxMetadata]) -> dict[str, list[tuple[str,str,str]]]:

    returned: dict[str, list[tuple[str,str,str]]] = {}

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
                returned[proto_pkg_name].append((message, meta.package_name, proto_file))
                print((message, meta.package_name, proto_file))

    return returned

def build_messages(
    message_path: pathlib.Path,
    import_msgs_paths: list[pathlib.Path],
    pbuf_output_dir: str, 
    grpc_output_dir: str, 
    pyi_output: str
) -> bool:

    SCRIPT_NAME: str = "grpc_tools.protoc"

    # --proto_path IMPORTS, searched in order
    # --grpc_python_out GRPC python output
    # --python_out PROTOBUF python output
    # --pyi_out PYTHON interface file output

    proto_path: list[str] = [f"--proto_path={str(path)}/" for path in import_msgs_paths]
    python_out_str: str = f"--python_out={pbuf_output_dir}"
    grpc_python_out_str: str = f"--grpc_python_out={grpc_output_dir}"
    pyi_output_str: str = f"--pyi_out={pyi_output}"
    proto_files: list[str] = [f"{proto_file}" for proto_file in glob.glob(str(message_path) + "/*.proto")]
    
    protoc_args: list[str] = [SCRIPT_NAME]
    protoc_args += proto_path
    protoc_args.append(python_out_str),
    protoc_args.append(grpc_python_out_str),
    protoc_args.append(pyi_output_str),
    protoc_args += proto_files

    # print(protoc_args)
    return grpc_tools.protoc.main(protoc_args) == 0

def modify_generated_python(
    message_path: pathlib.Path, 
    import_msgs_paths: list[pathlib.Path]
) -> None:

    ALL_PROTOS = get_message_packages(find_tbx_packages().values())

    proto_files: list[str] =  [f"{proto_file}" for proto_file in glob.glob(str(message_path) + "/*.proto")]

    for proto_file_name in proto_files:
        proto_text: str = open(proto_file_name, 'r').read()

        parsed_proto: proto_ast.File = Parser().parse(proto_text)
        imports: list[proto_ast.Import] = []
        messages: list[proto_ast.Message] = []

        # Figure out our imports
        for element in parsed_proto.file_elements:
            if isinstance(element, proto_ast.Import):
                imports.append(element)
            elif isinstance(element, proto_ast.Message):
                messages.append(element)
        
        # For each import, go and find the file that is being imported.
        for imported_file in imports:
            proto_pkg, proto_file = imported_file.name.split('/')
            proto_file = proto_file.rstrip(".proto")
            print((proto_pkg, proto_file))
            
            # message_info: tuple[str,str,str] | None = ALL_PROTOS.get()



def main() -> None:
    
    tbx_packages: dict[str,ToyboxMetadata] = find_tbx_packages()
    message_paths: list[pathlib.Path] = get_message_paths(tbx_packages.values())
    
    # for message_path in message_paths:
    #     print(message_path)
    
    # print(message_paths[0])
    # build_messages(
    #     message_path=message_paths[0],
    #     import_msgs_paths=message_paths,
    #     pbuf_output_dir="/home/wfletcher/toybox/test",
    #     pyi_output="/home/wfletcher/toybox/test",
    #     grpc_output_dir="/home/wfletcher/toybox/test")
    
    modify_generated_python(message_path=message_paths[0], import_msgs_paths=message_paths)

    # print(get_message_packages(tbx_packages.values()))


if __name__ == "__main__":
    main()

