"""Read student identifiers from the supplied semicolon-delimited roster."""

import csv


def load_roster(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        if not {"ID", "Name"}.issubset(reader.fieldnames or []):
            raise ValueError("Student CSV must contain ID;Name columns.")
        roster = {}
        identifiers = set()
        for row in reader:
            name = (row.get("Name") or "").strip().title()
            identifier = (row.get("ID") or "").strip()
            if not name or not identifier or name in roster or identifier in identifiers:
                raise ValueError("Student CSV contains an empty or duplicate name/ID.")
            roster[name] = identifier
            identifiers.add(identifier)
    return roster
