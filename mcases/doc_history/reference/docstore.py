"""Document field store with bounded undo/redo. Behavioral contract.

- DocStore(max_history): int (bool rejected) in [1, 256], else
  ValueError("max_history must be an integer between 1 and 256").
  max_history bounds the UNDO stack; pushing past it silently drops the
  OLDEST entry (which becomes un-undoable).
- Field keys everywhere: non-empty str of at most 64 chars, else
  ValueError("field must be a non-empty string of at most 64 characters").
- set(field, value) -> None: applies the write (a new field appends to
  insertion order; an existing field keeps its position), records an undo
  entry, and CLEARS the redo stack. Setting an existing field to the same
  value is still a mutation (recorded, redo cleared). sets += 1.
- remove(field) -> bool: absent field is a FULL no-op (returns False,
  nothing recorded, redo NOT cleared). Present: deletes, records, clears
  redo, removes += 1, returns True.
- get(field) -> value: KeyError(field) when absent.
- fields() -> list of field names in insertion order.
- undo() -> bool: False when nothing to undo. Reverts the latest mutation:
  a created field is deleted; an overwrite restores the old value IN
  PLACE; a remove re-creates the field at the END of insertion order
  (documented convention). Moves the entry to the redo stack. undos += 1.
- redo() -> bool: False when nothing to redo. Replays the entry and pushes
  it back onto the undo stack. redos += 1.
- depth() -> {"undo": n, "redo": n}.
- stats() -> {"sets", "removes", "undos", "redos", "fields"}: counts of
  SUCCESSFUL API mutations (undo does not decrement sets); fields is the
  live count.

Deterministic: no wall clock, no randomness.
"""

_HISTORY_MSG = "max_history must be an integer between 1 and 256"
_FIELD_MSG = "field must be a non-empty string of at most 64 characters"

_CREATED = object()  # sentinel: the set() created the field


def _check_field(field):
    if not isinstance(field, str) or not 1 <= len(field) <= 64:
        raise ValueError(_FIELD_MSG)


class DocStore:
    def __init__(self, max_history):
        if not isinstance(max_history, int) or isinstance(max_history, bool) \
                or not 1 <= max_history <= 256:
            raise ValueError(_HISTORY_MSG)
        self._max_history = max_history
        self._data = {}
        self._undo = []  # ("set", field, value, old) | ("remove", field, old)
        self._redo = []
        self._sets = 0
        self._removes = 0
        self._undos = 0
        self._redos = 0

    def _push_undo(self, entry):
        self._undo.append(entry)
        if len(self._undo) > self._max_history:
            del self._undo[0]

    def set(self, field, value):
        _check_field(field)
        old = self._data.get(field, _CREATED)
        self._data[field] = value
        self._push_undo(("set", field, value, old))
        self._redo.clear()
        self._sets += 1
        return None

    def remove(self, field):
        _check_field(field)
        if field not in self._data:
            return False
        old = self._data.pop(field)
        self._push_undo(("remove", field, old))
        self._redo.clear()
        self._removes += 1
        return True

    def get(self, field):
        _check_field(field)
        if field not in self._data:
            raise KeyError(field)
        return self._data[field]

    def fields(self):
        return list(self._data)

    def undo(self):
        if not self._undo:
            return False
        entry = self._undo.pop()
        if entry[0] == "set":
            _, field, _, old = entry
            if old is _CREATED:
                del self._data[field]
            else:
                self._data[field] = old
        else:
            _, field, old = entry
            self._data[field] = old   # re-created at the END (documented)
        self._redo.append(entry)
        self._undos += 1
        return True

    def redo(self):
        if not self._redo:
            return False
        entry = self._redo.pop()
        if entry[0] == "set":
            self._data[entry[1]] = entry[2]
        else:
            del self._data[entry[1]]
        self._undo.append(entry)      # was popped from undo, so still <= cap
        self._redos += 1
        return True

    def depth(self):
        return {"undo": len(self._undo), "redo": len(self._redo)}

    def stats(self):
        return {
            "sets": self._sets,
            "removes": self._removes,
            "undos": self._undos,
            "redos": self._redos,
            "fields": len(self._data),
        }
