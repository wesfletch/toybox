#!/usr/bin/env python3

from dataclasses import dataclass, field
from typing import Any, Callable, cast, Dict, List, Tuple

PLY_MAGIC: str = "ply"
PLY_FORMAT: str = "format"
PLY_COMMENT: str = "comment"
PLY_ELEMENT: str = "element"
PLY_PROPERTY: str = "property"
PLY_LIST: str = "list"
PLY_END_HEADER: str = "end_header"

DELIM: str = " "

# TODO: I'm not being very careful about byte-counts, which are part of the spec...
PLY_SCALAR_TYPES: Dict[str,type] = {
    "char": str,
    "uchar": str,
    "short": int,
    "ushort": int,
    "uint": int,
    "float": float,
    "double": float
}


class ParseError(Exception):
    def __init__(self, message: str, line_num: int | None = None) -> None:
        self.line_num = line_num
        self.message = message

    def __str__(self) -> str:
        if self.line_num is not None:
            return f"On line number <{self.line_num}>: \n\t{self.message}"
        else:
            return self.message

@dataclass(slots=True)
class PlyProperty:
    property_type: type
    property_name: str

    # only valid if type is a list
    list_length_type: type | None = None
    list_entry_type: type | None = None

@dataclass(slots=True)
class PlyElement:
    name: str
    number_of_entries: int
    number_of_entries_encountered: int = 0

    # per entry
    number_of_properties: int = 0
    properties: List[PlyProperty] = field(default_factory=list)

    data: List[Tuple[Any,...]] = field(default_factory=list)

    def create_data(self, line: List[str]) -> None:

        line_properties: List[Any] = []
        
        # Read the row entry by entry
        line_idx: int = 0
        for property in self.properties:

            if line_idx >= len(line):
                break

            if property.property_type == list:

                list_length_type: type = cast(type, property.list_length_type)
                list_entry_type: type = cast(type, property.list_entry_type)

                # First entry of list property is the length of the list
                length = list_length_type(line[line_idx])
                line_idx += 1
                
                try:
                    end_list_idx: int = line_idx + length + 1
                    line_properties.append([list_entry_type(x) for x in line[line_idx:end_list_idx]])
                except IndexError as e:
                    raise ParseError("Not enough entries!")
                
                line_idx += length
            else:
                try:
                    line_properties.append(property.property_type(line[line_idx]))
                except IndexError as e:
                    raise ParseError("Not enough entries!")

                line_idx +=1


        if len(line_properties) != self.number_of_properties:
            raise ParseError(f"Not enough properties; expected {self.number_of_properties}, got {len(line_properties)}")
        
        self.number_of_entries_encountered += 1
        self.data.append(tuple(line_properties))

@dataclass(slots=True)
class PlyModel:
    raw_text: str = ""
    elements: List[PlyElement] = field(default_factory=list)

    comments: List[str] = field(default_factory=list)

    _last: str = ""
    _elements_idx: int = -1

    def get_element(self, name: str) -> PlyElement | None:
        for element in self.elements:
            if element.name == name:
                return element
        return None


# 'ply'
def _magic(model: PlyModel, line: List[str]) -> None:
    
    if len(line) != 0:
        raise ParseError(f"Wrong number of fields for `{PLY_MAGIC}`: \
                         expected <0> got <{len(line)}>")


# 'format x y'
def _format(model: PlyModel, line: List[str]) -> None:

    # Don't care about this for now...
    return


# 'comment x'
def _comment(model: PlyModel, line: List[str]) -> None:
    model.comments.append("".join(line))


# 'element <name> <number-of-elements>'
def _element(model: PlyModel, line: List[str]) -> None:

    if len(line) != 2:
        raise ParseError(f"Wrong number of fields for `{PLY_ELEMENT}`: expected <2> got <{len(line)}>")

    name: str = line[0]
    number_of_entries: int = int(line[1])

    model.elements.append(PlyElement(name=name, number_of_entries=number_of_entries))
    
# 'property <data-type> <property-name> ...'
def _property(model: PlyModel, line: List[str]) -> None:

    if model._last == PLY_ELEMENT:
        model._elements_idx += 1
    elif model._last != PLY_PROPERTY:
        raise ParseError(f"We shouldn't be parsing a property right now!")
    
    # Either a scalar (length 2) or a list (length 4)
    if len(line) not in [2,4]:
        raise ParseError(f"Wrong number of fields for `{PLY_PROPERTY}`: expected <{[2,4]}> got <{len(line)}>")

    new_property: PlyProperty

    # Is this property a list?
    property_type: type
    if line[0] == "list":
        property_type = list
        type_of_num_of_indices: type
        type_of_list_entry: type
        try:
            type_of_num_of_indices = PLY_SCALAR_TYPES[line[1]]
            type_of_list_entry = PLY_SCALAR_TYPES[line[2]]
        except KeyError as e:
            raise ParseError(f"Type not understood: <{line[1]} or {line[2]}>")
        list_name: str = line[3]

        new_property = PlyProperty(
            property_type=property_type,
            property_name=list_name,
            list_length_type=type_of_num_of_indices,
            list_entry_type=type_of_list_entry)
        
    else: # It's not a list, so it must be a scalar
        try:
            property_type = PLY_SCALAR_TYPES[line[0]]
        except KeyError as e:
            raise ParseError(f"Type not understood: <{line[0]}>")
        property_name: str = line[1]

        new_property = PlyProperty(property_type=property_type, property_name=property_name)

    model.elements[model._elements_idx].number_of_properties += 1
    model.elements[model._elements_idx].properties.append(new_property)

# 'end_header'
def _end_header(model: PlyModel, line: List[str]) -> None:
    model._elements_idx = 0



CALLBACKS: Dict[str, Callable[[PlyModel,List[str]],None]] = {
    PLY_MAGIC: _magic,
    PLY_FORMAT: _format,
    PLY_COMMENT: _comment,
    PLY_ELEMENT: _element,
    PLY_PROPERTY: _property,
    PLY_END_HEADER: _end_header,
}


def parse(filename: str) -> PlyModel:
    
    model: PlyModel = PlyModel()

    line_number: int = 0 
    
    w = open(filename, mode="r", encoding="utf-8")
    for line in w:
        model.raw_text += line
        line_number += 1

        # ignore empty lines
        if line == "\n":
            continue

        line_split: List[str] = line.rstrip().split(sep=DELIM)
        
        if line_split[0] in CALLBACKS:
            try:
                CALLBACKS[line_split[0]](model,line_split[1:])
            except ParseError as e:
                raise ParseError(f"Parsing unit <{line_split[0]}> failed: {e}", line_num=line_number)
            
            if line_split[0] != PLY_COMMENT:
                model._last = line_split[0]
        else:
            if model._last != PLY_END_HEADER:
                raise ParseError(line_num=line_number, message=f"Key is unrecognized: [{line_split[0]}]")
            else:
                try:
                    model.elements[model._elements_idx].create_data(line_split)
                except ParseError as e:
                    raise ParseError(f"Failed to parse element: {e}", line_num=line_number)

        # If we've finished processing the header...
        if model._last == PLY_END_HEADER:
            # AND we've seen all of the elements that we expect to see...
            if model.elements[model._elements_idx].number_of_entries_encountered == model.elements[model._elements_idx].number_of_entries:
                model._elements_idx += 1
                # AND 
                if model._elements_idx > (len(model.elements)-1):
                    return model
                    # TODO: should probably check to make sure there's not more data... But whatever
                    # raise ParseError(f"On line <{line_number}>: `{line.rstrip()}` \n\tToo many values!")

    return model

def main() -> None:
    
    resources_dir: str = "../../resources/"
    model: PlyModel = parse(resources_dir + "box.ply")

    print(model)

if __name__ == "__main__":
    main()