"""P1 usage-order tracking (renamed from recency.py, list ops re-expressed)."""


class UsageOrder:
    def __init__(self):
        self._seq = []  # front = coldest, back = hottest

    def bump(self, name):
        try:
            idx = self._seq.index(name)
        except ValueError:
            idx = -1
        if idx >= 0:
            del self._seq[idx]
        self._seq.append(name)

    def forget(self, name):
        self._seq = [n for n in self._seq if n != name]

    def coldest(self):
        return self._seq[0]
