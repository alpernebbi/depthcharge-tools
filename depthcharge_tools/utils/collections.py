#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later

# depthcharge-tools collections utilities
# Copyright (C) 2021-2022 Alper Nebi Yasak <alpernebiyasak@gmail.com>
# See COPYRIGHT and LICENSE files for full copyright information.

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


# To write config sections in sort order
def SortedDict(key=None):
    if not callable(key):
        raise TypeError(
            "SortedDict argument must be a callable, not {}"
            .format(type(key).__name__)
        )

    class SortedDict(collections.UserDict):
        __key = key

        def __iter__(self):
            yield from sorted(super().__iter__(), key=type(self).__key)

    return SortedDict


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


class DirectedGraph:
    def __init__(self):
        self.__edges = {}

    def add_edge(self, node, child):
        self.add_node(node)
        self.add_node(child)
        self.__edges[node].add(child)

    def add_node(self, node):
        if node not in self.__edges:
            self.__edges[node] = set()

    def remove_edge(self, node, child):
        if node in self.__edges:
            self.__edges[node].discard(child)

    def remove_node(self, node):
        self.__edges.pop(node, None)
        for k, v in self.__edges.items():
            v.discard(node)

    def replace_node(self, node, replacement, merge=False):
        if replacement in self.__edges and not merge:
            raise ValueError(
                "Replacement node '{}' already in graph."
                .format(replacement)
            )

        parents = self.parents(node)
        children = self.children(node)
        self.remove_node(node)

        self.add_node(replacement)
        for p in parents:
            self.add_edge(p, replacement)
        for c in children:
            self.add_edge(replacement, c)

    def edges(self):
        return set(
            (n, c)
            for n, cs in self.__edges.items()
            for c in cs
        )

    def nodes(self):
        return set(self.__edges.keys())

    def children(self, *nodes):
        node_children = set()
        for node in nodes:
            node_children.update(self.__edges.get(node, set()))

        return node_children

    def parents(self, *nodes):
        node_parents = set()
        for parent, children in self.__edges.items():
            if children.intersection(nodes):
                node_parents.add(parent)

        return node_parents

    def ancestors(self, *nodes):
        nodes = set(nodes)

        ancestors = self.parents(*nodes)
        tmp = self.parents(*ancestors)
        while tmp - ancestors:
            ancestors.update(tmp)
            tmp = self.parents(*ancestors)

        return ancestors

    def descendants(self, *nodes):
        nodes = set(nodes)

        descendants = self.children(*nodes)
        tmp = self.children(*descendants)
        while tmp - descendants:
            descendants.update(tmp)
            tmp = self.children(*descendants)

        return descendants

    def leaves(self, *nodes):
        nodes = set(nodes)

        leaves = set()
        if len(nodes) == 0:
            leaves.update(k for k, v in self.__edges.items() if not v)
            return leaves

        leaves = self.leaves()
        node_leaves = set()
        while nodes:
            node_leaves.update(nodes.intersection(leaves))
            nodes.difference_update(node_leaves)
            nodes = self.children(*nodes)

        return node_leaves

    def roots(self, *nodes):
        nodes = set(nodes)

        roots = set()
        if len(nodes) == 0:
            roots.update(self.__edges.keys())
            roots.difference_update(*self.__edges.values())
            return roots

        roots = self.roots()
        node_roots = set()
        while nodes:
            node_roots.update(nodes.intersection(roots))
            nodes.difference_update(node_roots)
            nodes = self.parents(*nodes)

        return node_roots
