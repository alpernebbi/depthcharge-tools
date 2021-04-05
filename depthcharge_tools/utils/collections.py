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


def TypedList(T):
    if not isinstance(T, type):
        raise TypeError(
            "TypedList argument must be a type, not {}"
            .format(type(T).__name__)
        )

    name = "TypedList.{}List".format(str.title(T.__name__))

    class TypedList(collections.UserList):
        __type = T
        __name__ = name
        __qualname__ = name

        def __init__(self, initlist=None):
            if initlist is not None:
                self.__typecheck(*initlist)
            super().__init__(initlist)

        def __typecheck(self, *values):
            if not all(isinstance(value, self.__type) for value in values):
                raise TypeError(
                    "{} items must be of type {}."
                    .format(type(self).__name__, self.__type.__name__)
                )

        def __setitem__(self, idx, value):
            self.__typecheck(value)
            return super().__setitem__(idx, value)

        def __iadd__(self, other):
            self.__typecheck(*other)
            return super().__iadd__(other)

        def append(self, value):
            self.__typecheck(value)
            return super().append(value)

        def insert(self, idx, value):
            self.__typecheck(value)
            return super().insert(idx, value)

        def extend(self, other):
            self.__typecheck(*other)
            return super().extend(other)

    return TypedList
