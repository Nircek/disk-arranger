#!/usr/bin/env python3

# analyze.py -- part of disk-arranger
# Copyright (C) 2022-2024 Marcin Zepp <nircek-2103@protonmail.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# SPDX-License-Identifier: AGPL-3.0-or-later

import sys
import re
from collections import Counter
from typing import Optional
from dataclasses import dataclass

# import readline


def human_size(size: int):
    """Change `size` in bytes to human format.
    >>> human_size(0)
    '0 B'
    >>> human_size(1)
    '1 B'
    >>> human_size(1000)
    '1000 B'
    >>> human_size(1024)
    '1 KiB'
    >>> human_size(1.299*1024)
    '1.299 KiB'
    >>> human_size(1.299*1024**2)
    '1.299 MiB'
    >>> human_size(1.299*1024**8)
    '1.299 YiB'
    >>> human_size(1.299*1024**9)
    '1330 YiB'
    >>> human_size(1.299*1024**10)
    '1.362e+06 YiB'

    """
    size_names = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
    size_map = ((1 << (i * 10), e) for i, e in enumerate(size_names))
    r = f"{size} {size_names[0]}"
    for value, unit in size_map:
        if size < value:
            break
        q = size / value
        r = f"{q:.4g} {unit}"
    return r


def split_path(path: str) -> tuple[str, str, str]:
    "Split a filepath into parent path, filename and separator."
    matched_separator = re.search(r"[/\\]", path)
    if matched_separator is None:
        return "", path, ""
    matched_separator = matched_separator.group()
    splitted = path.rsplit(matched_separator, 1)
    return splitted[0] + matched_separator, splitted[1], matched_separator


def get_path_parent(path: str):
    return split_path(path)[0]


@dataclass
class FileInfo:
    """
    The holder of timestamps associated with path.
    """

    atime: str
    mtime: str
    ctime: Optional[str]


@dataclass
class SameFileHolder:
    """The holder of paths of files with same SHA."""

    size: int
    paths: dict[str, FileInfo]
    "Path -> PathInfo"

    def wasting_space(self, cluster_size=1):
        """Calculate space wasting by duplicates of this file."""
        cluster_sized = (self.size + cluster_size - 1) // cluster_size * cluster_size
        return cluster_sized * (len(self.paths) - 1)


def elementwise_tuple_sum(l: list[tuple[int, int]]):
    """
    >>> elementwise_tuple_sum([(1, 2), (3, 4), (5, 6)])
    (9, 12)
    >>> elementwise_tuple_sum([])
    """
    return tuple(map(lambda *e: sum(e), *l)) if l else None


class FileDump:
    """The presentation of filedump file."""

    def __init__(self, filename: str):
        self.db: dict[str, SameFileHolder] = {}
        self.graph = {}
        self.dups: list[tuple[str, SameFileHolder]] = None
        self.dup_paths = None
        with open(filename, "r", encoding="utf8") as file:
            try:
                for line in file:
                    path, sha, size, atime, mtime, *ctime = line.rstrip().split("\t")
                    path = escape(path)
                    size, ctime = int(size), ctime[0] if ctime else None
                    parent, child, sep = split_path(path)
                    if sha == "failed":
                        print(
                            f"{sha=} {path=} {size=} {atime=} {mtime=} {ctime=}",
                            file=sys.stderr,
                        )
                        continue
                    if parent not in self.graph:
                        self.graph[parent] = []
                    self.graph[parent] += [(child + ("" if sha else sep), sha)]
                    pathinfo = FileInfo(atime, mtime, ctime)
                    if sha not in self.db:
                        self.db[sha] = SameFileHolder(size, {path: pathinfo})
                    else:
                        self.db[sha].paths[path] = pathinfo
                        stored_size = self.db[sha].size
                        if stored_size != size:
                            print(
                                f"{sha} sizes differ: {size} != {stored_size}",
                                file=sys.stderr,
                            )
            except ValueError:
                print(f"Ignoring {repr(line)}")
        if (".", "") in self.graph[""]:
            self.graph[""].remove((".", ""))
        for e in ["./", ".\\"]:
            if e in self.graph:
                self.graph[""] += [(e, "")]
        print(self.graph[""])

    def get_sorted_dups(self):
        "Get files wasting space in descending order."
        if self.dups is None:

            def is_not_unique(sha_sfh: tuple[str, SameFileHolder]):
                _, sfh = sha_sfh
                return len(sfh.paths) >= 2

            dups = filter(is_not_unique, self.db.items())

            def wasting_space(sha_sfh: tuple[str, SameFileHolder]):
                _, sfh = sha_sfh
                return sfh.wasting_space()

            self.dups = list(sorted(dups, key=wasting_space, reverse=True))

        return self.dups

    def get_wasted_space(self, cluster_sizes=(1, 4096)) -> tuple[int, ...]:
        """
        Get size of space wasted by duplicates stored on disk with given cluster size.
        """
        self.get_sorted_dups()  # make sure self.dups is initiated

        def get_dups_info(sfh: SameFileHolder):
            return (sfh.wasting_space(c) for c in cluster_sizes)

        r = elementwise_tuple_sum([get_dups_info(sfh) for _, sfh in self.dups])
        return r if r else (0, 0)

    def best(self) -> list[tuple[str, str, list[str]]]:
        """Get list of best duplicates to resolve.

        Returns:
            list[tuple[str, str, list[str]]]: (size, human_size, sha, paths))
        """
        r = []
        self.get_sorted_dups()  # make sure self.dups is initiated
        for sha, sfh in self.dups:
            quantity = len(sfh.paths) - 1
            wasted = quantity * sfh.size
            if wasted <= 0:
                break
            size = human_size(sfh.size)
            if quantity >= 2:
                size = f"{human_size(wasted)} = {quantity}*{size}"
            paths = list(sfh.paths.keys())
            r += [(wasted, size, sha, paths)]
        return r

    def get_dup_paths(self):
        # TODO: add suffix recognition
        if self.dup_paths is None:
            dups = [sfh.paths.keys() for _, sfh in self.dups]
            parent_paths = [
                tuple(sorted([get_path_parent(p) for p in paths])) for paths in dups
            ]
            counted_dir_tuples = Counter(parent_paths).items()
            counted_dir_tuples = filter(lambda e: e[1] > 1, counted_dir_tuples)

            counted_dir_tuples = sorted(
                counted_dir_tuples, key=lambda e: e[1], reverse=True
            )
            self.dup_paths = counted_dir_tuples
        return self.dup_paths

    def print_info(self):
        c1, c4k = map(human_size, self.get_wasted_space())
        print(f"{c1} / {c4k} wasted\n")

        self.get_dup_paths()  # make sure self.dup_paths is initiated
        dirs = len(self.dup_paths)
        dirdups = sum(map(lambda e: e[1], self.dup_paths))
        print(f"Duplicate dirs [list of {dirs} dirs containing {dirdups} dups]:")
        for dir_tuple, cnt in self.dup_paths:
            dir_tuple = " ".join([unescape(e) for e in dir_tuple])
            print(f"{cnt}: {dir_tuple}")
        print(37 * "\n")
        already = {f for e in self.dup_paths for f in e[0]}
        x = list(
            filter(
                lambda el: el[0] > 2 * 1024**2
                and not all([get_path_parent(e) in already for e in el[3]]),
                self.best(),
            )
        )
        print(f"Entries saving ≥ 2 MiB [list of {len(x)}]:")
        for s, hs, k, f in x:
            f = [unescape(e) for e in f]
            print(hs, k, " ".join(f), sep="\t")


def escape(t):
    """
    >>> escape('Lorem ipsum dolor sit amet.')
    'Lorem^sipsum^sdolor^ssit^samet.'
    >>> escape('^ ^^ ^s^^^')
    '^^^s^^^^^s^^s^^^^^^'
    """
    return t.replace("^", "^^").replace(" ", "^s")


def unescape(t):
    """
    >>> unescape('Lorem^sipsum^sdolor^ssit^samet.')
    '"Lorem ipsum dolor sit amet."'
    >>> unescape('^^^s^^^^^s^^s^^^^^^')
    '"^ ^^ ^s^^^"'
    """
    return '"' + re.sub(r"(?<!\^)((\^\^)*)\^s", r"\1 ", t).replace("^^", "^") + '"'


# def completer(text, state):
#     parent, child, sep = split_path(text)
#     if parent not in graph:
#         return None
#     l = [parent + e for e, _ in graph[parent] if e.startswith(child)] + [None]
#     if len(l) == 2 and l[0][-1] not in "\\/":
#         l[0] += " "
#     return l[state]


if __name__ == "__main__":
    fd = FileDump("filedump.txt")
    fd.print_info()
    # readline.set_completer(completer)
    # readline.set_completer_delims(' ')
    # readline.parse_and_bind('tab: complete')
    # while True:
    #     try:
    #         input()
    #     except EOFError:
    #         break
