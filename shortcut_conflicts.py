"""Shared, Qt-independent shortcut conflict detection for the shortcut editor."""

def find_shortcut_conflicts(sequences):
    """Return each conflicting command and its peers, retaining editor order.

    Empty shortcuts are intentionally ignored; normalized strings should come
    from QKeySequence PortableText in the GUI, not from freeform user input.
    """
    used = {}
    conflicts = {}
    for name, sequence in sequences.items():
        key = str(sequence).strip().casefold()
        if not key:
            continue
        if key in used:
            previous = used[key]
            conflicts.setdefault(name, []).append(previous)
            conflicts.setdefault(previous, []).append(name)
        else:
            used[key] = name
    return conflicts
