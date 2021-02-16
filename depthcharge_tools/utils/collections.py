#! /usr/bin/env python3

import collections

# Inheritance for config sections
class ConfigDict(collections.OrderedDict):
    def __getitem__(self, key):
        super_ = super()
        if not isinstance(key, str) or "/" not in key:
            return super_.__getitem__(key)

        def getitem(key):
            try:
                return super_.__getitem__(key)
            except KeyError:
                return KeyError

        def parents(leaf):
            idx = leaf.find("/")
            while idx != -1:
                yield leaf[:idx]
                idx = leaf.find("/", idx + 1)
            yield leaf

        items = list(
            item for item in reversed([
                getitem(p) for p in parents(key)
            ]) if item != KeyError
        )

        if all(isinstance(i, dict) for i in items):
            return collections.ChainMap(*items)

        if items:
            return items[0]

        raise KeyError(key)


