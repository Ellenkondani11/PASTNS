"""Compile the small, simple PASTNS gettext catalog without a system msgfmt."""
from __future__ import annotations
import ast
import struct
from pathlib import Path

PO = Path(__file__).resolve().parents[1] / "core/locale/ny/LC_MESSAGES/django.po"
MO = PO.with_suffix(".mo")


def parse_po(path: Path):
    entries = []
    current = None
    field = None

    def flush():
        nonlocal current
        if current is not None:
            entries.append((current.get("msgid", ""), current.get("msgstr", "")))
            current = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            flush()
            field = None
            continue
        if line.startswith("msgid "):
            flush()
            current = {"msgid": ast.literal_eval(line[len("msgid "):])}
            field = "msgid"
        elif line.startswith("msgstr "):
            if current is None:
                current = {}
            current["msgstr"] = ast.literal_eval(line[len("msgstr "):])
            field = "msgstr"
        elif line.startswith('"') and field and current is not None:
            current[field] = current.get(field, "") + ast.literal_eval(line)
        else:
            raise ValueError(f"Unsupported gettext PO syntax: {raw}")
    flush()
    # GNU MO catalogs use a byte-sorted original string table.
    unique = {}
    for msgid, msgstr in entries:
        if msgid in unique and unique[msgid] != msgstr:
            raise ValueError(f"Duplicate msgid with different translations: {msgid!r}")
        unique[msgid] = msgstr
    return sorted(unique.items(), key=lambda entry: entry[0].encode("utf-8"))


def compile_mo(entries, destination: Path):
    originals = b"".join(msgid.encode("utf-8") + b"\0" for msgid, _ in entries)
    translations = b"".join(msgstr.encode("utf-8") + b"\0" for _, msgstr in entries)
    count = len(entries)
    originals_table = 28
    translations_table = originals_table + count * 8
    originals_data = translations_table + count * 8
    translations_data = originals_data + len(originals)
    output = bytearray(struct.pack("<7I", 0x950412DE, 0, count, originals_table, translations_table, 0, 0))
    offset = originals_data
    for msgid, _ in entries:
        raw = msgid.encode("utf-8")
        output.extend(struct.pack("<2I", len(raw), offset))
        offset += len(raw) + 1
    offset = translations_data
    for _, msgstr in entries:
        raw = msgstr.encode("utf-8")
        output.extend(struct.pack("<2I", len(raw), offset))
        offset += len(raw) + 1
    output.extend(originals)
    output.extend(translations)
    destination.write_bytes(output)


if __name__ == "__main__":
    catalog = parse_po(PO)
    compile_mo(catalog, MO)
    print(f"Compiled {len(catalog) - 1} message(s) to {MO.relative_to(PO.parents[3])}")
