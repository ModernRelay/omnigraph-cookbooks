"""Read a SCIP index (https://github.com/sourcegraph/scip) with the standard library.

Only the fields the code-graph converter uses are decoded. Field numbers follow
scip.proto; an index that uses a field differently fails loudly rather than
being read as something else.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# SymbolRole bits.
DEFINITION = 0x1
IMPORT = 0x2
WRITE_ACCESS = 0x4
READ_ACCESS = 0x8
GENERATED = 0x10
TEST = 0x20
FORWARD_DEFINITION = 0x40


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = value = 0
    while True:
        b = buf[i]
        i += 1
        value |= (b & 0x7F) << shift
        if not b & 0x80:
            return value, i
        shift += 7
        if shift > 63:
            raise ValueError("varint longer than 64 bits")


def _fields(buf: bytes):
    """Yield (field_number, wire_type, value) for one message."""
    i, n = 0, len(buf)
    while i < n:
        key, i = _varint(buf, i)
        num, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _varint(buf, i)
        elif wire == 2:
            length, i = _varint(buf, i)
            value = buf[i:i + length]
            if len(value) != length:
                raise ValueError("truncated length-delimited field")
            i += length
        elif wire == 1:
            value, i = buf[i:i + 8], i + 8
        elif wire == 5:
            value, i = buf[i:i + 4], i + 4
        else:
            raise ValueError(f"unsupported wire type {wire} for field {num}")
        yield num, wire, value


def _int32s(wire: int, value) -> list[int]:
    if wire == 0:
        return [value]
    out, i = [], 0
    while i < len(value):
        v, i = _varint(value, i)
        out.append(v)
    return out


def _range(values: list[int]) -> tuple[int, int, int, int]:
    """Normalize a SCIP range to (start_line, start_char, end_line, end_char), zero-based."""
    if len(values) == 3:
        return values[0], values[1], values[0], values[2]
    if len(values) == 4:
        return tuple(values)  # type: ignore[return-value]
    raise ValueError(f"a SCIP range has 3 or 4 elements, not {len(values)}")


def _single(buf: bytes) -> tuple[int, int, int, int]:
    f = {num: v for num, _, v in _fields(buf)}
    line = f.get(1, 0)
    return line, f.get(2, 0), line, f.get(3, 0)


def _multi(buf: bytes) -> tuple[int, int, int, int]:
    f = {num: v for num, _, v in _fields(buf)}
    return f.get(1, 0), f.get(2, 0), f.get(3, 0), f.get(4, 0)


@dataclass
class Relationship:
    symbol: str
    is_reference: bool = False
    is_implementation: bool = False
    is_type_definition: bool = False
    is_definition: bool = False


@dataclass
class SymbolInformation:
    symbol: str = ""
    kind: int = 0
    display_name: str = ""
    enclosing_symbol: str = ""
    documentation: list[str] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)


@dataclass
class Occurrence:
    symbol: str = ""
    roles: int = 0
    range: tuple[int, int, int, int] | None = None
    enclosing_range: tuple[int, int, int, int] | None = None


@dataclass
class Document:
    relative_path: str = ""
    language: str = ""
    occurrences: list[Occurrence] = field(default_factory=list)
    symbols: list[SymbolInformation] = field(default_factory=list)


@dataclass
class Index:
    tool_name: str = ""
    tool_version: str = ""
    project_root: str = ""
    documents: list[Document] = field(default_factory=list)


def _relationship(buf: bytes) -> Relationship:
    r = Relationship(symbol="")
    for num, _, v in _fields(buf):
        if num == 1:
            r.symbol = v.decode()
        elif num == 2:
            r.is_reference = bool(v)
        elif num == 3:
            r.is_implementation = bool(v)
        elif num == 4:
            r.is_type_definition = bool(v)
        elif num == 5:
            r.is_definition = bool(v)
    return r


def _symbol_information(buf: bytes) -> SymbolInformation:
    s = SymbolInformation()
    for num, _, v in _fields(buf):
        if num == 1:
            s.symbol = v.decode()
        elif num == 3:
            s.documentation.append(v.decode())
        elif num == 4:
            s.relationships.append(_relationship(v))
        elif num == 5:
            s.kind = v
        elif num == 6:
            s.display_name = v.decode()
        elif num == 8:
            s.enclosing_symbol = v.decode()
    return s


def _occurrence(buf: bytes) -> Occurrence:
    o = Occurrence()
    legacy_range = legacy_enclosing = None
    for num, wire, v in _fields(buf):
        if num == 1:
            legacy_range = _range(_int32s(wire, v))
        elif num == 2:
            o.symbol = v.decode()
        elif num == 3:
            o.roles = v
        elif num == 7:
            legacy_enclosing = _range(_int32s(wire, v))
        elif num == 8:
            o.range = _single(v)
        elif num == 9:
            o.range = _multi(v)
        elif num == 10:
            o.enclosing_range = _single(v)
        elif num == 11:
            o.enclosing_range = _multi(v)
    # The typed forms take precedence over the deprecated repeated-int32 forms.
    o.range = o.range or legacy_range
    o.enclosing_range = o.enclosing_range or legacy_enclosing
    return o


def _document(buf: bytes) -> Document:
    d = Document()
    for num, _, v in _fields(buf):
        if num == 1:
            d.relative_path = v.decode()
        elif num == 2:
            d.occurrences.append(_occurrence(v))
        elif num == 3:
            d.symbols.append(_symbol_information(v))
        elif num == 4:
            d.language = v.decode()
    return d


def read_index(path: str) -> Index:
    with open(path, "rb") as f:
        buf = f.read()
    idx = Index()
    for num, _, v in _fields(buf):
        if num == 1:  # Metadata
            for mnum, _, mv in _fields(v):
                if mnum == 2:  # ToolInfo
                    for tnum, _, tv in _fields(mv):
                        if tnum == 1:
                            idx.tool_name = tv.decode()
                        elif tnum == 2:
                            idx.tool_version = tv.decode()
                elif mnum == 3:
                    idx.project_root = mv.decode()
        elif num == 2:
            idx.documents.append(_document(v))
    return idx
