from collections import Mapping
from itertools import product


def key_in_slice(k, s):
    """Check if the key k is part of the slice s."""
    if not isinstance(k, tuple):
        k = (k,)
    for i in range(len(s)):
        if (not isinstance(s[i], slice)) and k[i] != s[i]:
            return False
        if isinstance(s[i], slice):
            if s[i].start is not None and k[i] < s[i].start:
                return False
            if s[i].stop is not None and k[i] >= s[i].stop:
                return False
    return True


def key_from_slice(k, s):
    """Take a slice s of the key k."""
    if not isinstance(k, tuple):
        k = (k,)
    ans = []
    for i in range(len(s)):
        if isinstance(s[i], slice):
            ans.append(k[i])
    if len(ans) > 1:
        return tuple(ans)
    else:
        return ans[0]


class Slict(Mapping):
    """Sliceable interface to wrap the Mapping d

    Slict wraps an existing Mapping (e.g. dictionary) with a sliceable
    interface to tuple keys.  The slice argument sl is used internally
    when returning a slice.
    """
    def __init__(self, d, sl=None):
        self.d = d
        if sl is None:
            self.dim = max([len(key)
                            if isinstance(key, tuple) else 1 for key in d])
            self.locs = [i for i in range(self.dim)]
            self.pins = []
            self.sl = tuple([slice(None, None, None)]*self.dim)
        else:
            self.dim = len(sl)
            self.sl = sl
            self.locs = []
            self.pins = []
            self.bounds = []
            j = 0
            k = 0
            for i in range(self.dim):
                if isinstance(sl[i], slice):
                    self.locs.append(j)
                    self.bounds.append((slice.start, slice.stop))
                    j = j+1
                else:
                    self.locs.append(-k - 1)
                    self.pins.append(sl[i])

    def _full_key(self, key):
        if not isinstance(key, tuple):
            key = (key,)
        full_key = []
        j = 0
        for i in range(self.dim):
            if not isinstance(self.sl[i], slice):
                full_key.append(self.sl[i])
            elif not isinstance(key[j], slice):
                full_key.append(key[j])
                j = j + 1
            else:
                if self.sl[i].start is None and key[j].start is None:
                    start = None
                elif self.sl[i].start is None and key[j].start is not None:
                    start = key[j].start
                elif self.sl[i].start is not None and key[j].start is None:
                    start = self.sl[i].start
                else:
                    start = max(self.sl[i].start, key[j].start)
                if self.sl[i].stop is None and key[j].stop is None:
                    stop = None
                elif self.sl[i].stop is None and key[j].stop is not None:
                    stop = key[j].stop
                elif self.sl[i].stop is not None and key[j].stop is None:
                    stop = self.sl[i].stop
                else:
                    stop = min(self.sl[i].stop, key[j].stop)
                full_key.append(slice(start, stop, None))
                j = j + 1

        return tuple(full_key)

    def __getitem__(self, key):
        """If the key contains slices, return a new Slict."""
        full_key = self._full_key(key)

        if not any([isinstance(k, slice) for k in full_key]):
            if len(full_key) == 1:
                full_key = full_key[0]
            return self.d[full_key]

        return Slict(self.d, sl=full_key)

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len([k for k in self.d if key_in_slice(k, self.sl)])

    def __contains__(self, key):
        full_key = self._full_key(key)
        if len(full_key) == 1:
            full_key = full_key[0]
        return key_in_slice(full_key, self.sl) and full_key in self.d

    def keys(self):
        return [key_from_slice(k, self.sl)
                for k in self.d if key_in_slice(k, self.sl)]

    def full_keys(self):
        return [k
                for k in self.d if key_in_slice(k, self.sl)]

    def items(self):
        return [(key_from_slice(k, self.sl), v)
                for (k, v) in self.d.items() if key_in_slice(k, self.sl)]


class CachedSlict(Slict):
    """Slict that stores sorted keyspaces

    CachedSlict guarantee lexographical ordering of keys(), values(),
    and items(), allowing it to act more like a table.  You can call
    update_cache() to sync the stored keyspaces when the backend dictionary
    changes.
    """

    def __init__(self, d, sl=None):
        super(CachedSlict, self).__init__(d, sl)
        self.update_cache()

    def __getitem__(self, key):
        """If the key contains slices, return a new CachedSlict."""
        full_key = self._full_key(key)
        if not any([isinstance(k, slice) for k in full_key]):
            if len(full_key) == 1:
                full_key = full_key[0]
            return self.d[full_key]

        return CachedSlict(self.d, sl=full_key)

    def update_cache(self):
        """Update the sorted keyspaces stored in key_parts."""
        self.key_parts = []
        if self.dim == 1:
            self.key_parts.append(sorted(list(set(
                key_from_slice(k, self.sl)
                for k in self.d if key_in_slice(k, self.sl)))))
            return
        for i in range(self.dim):
            if not isinstance(self.sl[i], slice):
                continue
            self.key_parts.append(sorted(list(set(
                k[i]
                for k in self.d if key_in_slice(k, self.sl)))))
        return

    def keys(self):
        if len(self.key_parts) == 1:
            return self.key_parts[0]
        return [k for k in product(*self.key_parts) if k in self]

    def values(self):
        if len(self.key_parts) == 1:
            return [self[k] for k in self.key_parts[0]]
        return [self[k] for k in product(*self.key_parts) if k in self]

    def items(self):
        if self.dim == 1:
            return [(k, self[k]) for k in self.key_parts[0]]
        return [(k, self[k]) for k in product(*self.key_parts) if k in self]
