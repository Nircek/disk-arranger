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
from collections.abc import Iterable, Collection
from dataclasses import dataclass
from os.path import commonprefix
import readline


def commonsuffixpath(words: list[str]) -> int:
    r"""
    >>> paths = [".\\c\\.git\\objects\\00\\", ".\\projects-c\\.git\\objects\\00\\"]
    >>> suffix = '.git\\objects\\00\\'
    >>> commonsuffixpath(paths) == len(suffix)
    True
    >>> commonsuffixpath(['/photos/', '/photos/']) == len('photos/')
    True
    >>> commonsuffixpath(['.\\b\\', '.\\a\\'])
    0
    """
    words = [re.sub(r"[/\\]", "/", w)[::-1] for w in words]
    return len(commonprefix(words).rsplit("/", 1)[0])


def human_size(size: int) -> str:
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
    """
    Split a filepath into parent path, filename and separator.
    >>> split_path("./")
    ('', '.', '')
    >>> split_path("./a")
    ('./', 'a', '/')
    >>> split_path("./a/")
    ('./', 'a', '/')
    >>> split_path("./a/b")
    ('./a/', 'b', '/')
    >>> split_path("./a/b/.")
    ('./a/b/', '.', '/')
    """
    if path and path[-1] in "/\\":
        path = path[:-1]
    match = re.search(r"[/\\]", path)
    if match is None:
        return "", path, ""
    matched_separator = match.group()
    splitted = path.rsplit(matched_separator, 1)
    return splitted[0] + matched_separator, splitted[1], matched_separator


def get_path_parent(path: str) -> str:
    r"""
    >>> get_path_parent(".\\a\\")
    '.\\'
    """
    return split_path(path)[0]


@dataclass
class FileInfo:
    """The holder of timestamps associated with path."""

    atime: str
    mtime: str
    ctime: str | None


@dataclass
class SameFileHolder:
    """The holder of paths of files with same SHA."""

    size: int
    paths: dict[str, FileInfo]
    "Path -> PathInfo"

    def wasting_space(self, cluster_size: int = 1) -> int:
        """Calculate space wasting by duplicates of this file."""
        cluster_sized = (self.size + cluster_size - 1) // cluster_size * cluster_size
        return cluster_sized * (len(self.paths) - 1)


def elementwise_tuple_sum(l: Iterable[tuple[int, ...]]) -> tuple[int, ...] | None:
    """
    >>> elementwise_tuple_sum([(1, 2), (3, 4), (5, 6)])
    (9, 12)
    >>> elementwise_tuple_sum([])
    """
    return tuple(map(lambda *e: sum(e), *l)) if l else None


class FileDump:
    """The presentation of filedump file."""

    def __init__(self) -> None:
        self.db: dict[str, SameFileHolder] = {}
        """Mapping of SHA to information about same file."""
        self.graph: dict[str, list[tuple[str, str]]] = {}
        """Mapping of folder path to content (filename, sha)"""
        self.dups: list[tuple[str, SameFileHolder]] = []
        """List of (sha, info) about duplicated files."""
        self.dup_paths: Collection[tuple[tuple[str, ...], int]] = []
        """List of (paths, file_count) about duplicated paths."""
        self.completer_cache: dict[str, list[str]] = {}
        """Cache of complter output: prompt to suggested paths."""

    def load_file(self, filename: str) -> None:
        """Loads paths from FileDump file."""
        with open(filename, "r", encoding="utf8") as file:
            try:
                for line in file:
                    path, sha, ssize, atime, mtime, *lctime = line.rstrip().split("\t")
                    path = escape(path)
                    size = int(ssize)
                    ctime = lctime[0] if lctime else None
                    self.add_path(path, sha, size, FileInfo(atime, mtime, ctime))
            except ValueError:
                print(f"Ignoring {repr(line)}")

        if (".", "") in self.graph[""]:
            self.graph[""].remove((".", ""))
        for e in ["./", ".\\"]:
            if e in self.graph:
                self.graph[""] += [(e, "")]
        print(self.graph[""])

    def print_db(self) -> None:
        """
        >>> fd = FileDump()
        >>> t, s1, s2 = "2023-12-31T23:00:00Z", "0"*64, "0"*63+"1"
        >>> fd.add_path("./xd", s1, 3, FileInfo(t, t, None))
        >>> fd.add_path("./xd2", s2, 5, FileInfo(t, t, None))
        >>> fd.add_path("./xd3", s2, 5, FileInfo(t, t, None))
        >>> fd.print_db()
        0000000000000000000000000000000000000000000000000000000000000000 1 ./xd
        0000000000000000000000000000000000000000000000000000000000000001 2 ./xd2
        """
        for k, v in self.db.items():
            for p in v.paths:
                path = p
                break
            print(k, len(v.paths), path)

    def add_path(self, path: str, sha: str, size: int, timeinfo: FileInfo) -> None:
        """Add new file to inner state."""
        parent, child, sep = split_path(path)
        if sha == "failed":
            print(
                f"{sha=} {path=} {size=} {timeinfo}",
                file=sys.stderr,
            )
            return
        if parent not in self.graph:
            self.graph[parent] = []
        self.graph[parent] += [(child + ("" if sha else sep), sha)]
        if sha not in self.db:
            self.db[sha] = SameFileHolder(size, {path: timeinfo})
        else:
            self.db[sha].paths[path] = timeinfo
            stored_size = self.db[sha].size
            if stored_size != size:
                print(
                    f"{sha} sizes differ: {size} != {stored_size}",
                    file=sys.stderr,
                )

    def get_sorted_dups(self, force: bool = False) -> list[tuple[str, SameFileHolder]]:
        """Get files wasting space in descending order."""
        if force or not self.dups:

            def is_not_unique(sha_sfh: tuple[str, SameFileHolder]) -> bool:
                _, sfh = sha_sfh
                return len(sfh.paths) >= 2

            dups = filter(is_not_unique, self.db.items())

            def wasting_space(sha_sfh: tuple[str, SameFileHolder]) -> int:
                _, sfh = sha_sfh
                return sfh.wasting_space()

            self.dups = sorted(dups, key=wasting_space, reverse=True)

        return self.dups

    def get_wasted_space(
        self, cluster_sizes: tuple[int, ...] = (1, 4096)
    ) -> tuple[int, ...]:
        """Get size of space wasted by duplicates stored on disk with given cluster size."""
        self.get_sorted_dups()  # make sure self.dups is initiated

        def get_dups_info(sfh: SameFileHolder) -> tuple[int, ...]:
            return tuple((sfh.wasting_space(c) for c in cluster_sizes))

        r = elementwise_tuple_sum([get_dups_info(sfh) for _, sfh in self.dups])
        return r if r else (0, 0)

    def best(self) -> list[tuple[int, str, str, list[str]]]:
        """
        Get list of best duplicates to resolve.

        Returns:
            list[int, tuple[str, str, list[str]]]: (size, human_size, sha, paths))
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

    def get_dup_paths(
        self, force: bool = False
    ) -> Collection[tuple[tuple[str, ...], int]]:
        """
        Calculate paths with a lot of same duplicates.

        Rationale:
            Compress `a/{a,b,...}` and `b/{a,b,...}` into just `a` and `b`.
        """
        if force or not self.dup_paths:
            dups = [sfh.paths.keys() for _, sfh in self.dups]

            def find_not_common_dir_tuple(paths: Iterable[str]) -> tuple[str, ...]:
                paths = [get_path_parent(p) for p in paths]
                opaths = list(paths)
                suffix = commonsuffixpath(paths)
                paths = [p if suffix in (0, len(p)) else p[:-suffix] for p in paths]
                if len(re.findall(r"[/\\]", paths[0])) <= 1:
                    paths = opaths
                return tuple(sorted(paths))

            parent_paths = [find_not_common_dir_tuple(paths) for paths in dups]
            self.dup_paths = Counter(parent_paths).items()
            self.dup_paths = sorted(filter(lambda e: e[1] > 1, self.dup_paths))
        return self.dup_paths

    def print_info(self) -> None:
        """Print basic info about FileDump."""
        c1, c4k = map(human_size, self.get_wasted_space())
        print(f"{c1} / {c4k} wasted\n")

        self.get_dup_paths()  # make sure self.dup_paths is initiated
        dirs = len(self.dup_paths)
        dirdups = sum(map(lambda e: e[1], self.dup_paths))
        print(f"Duplicate dirs [list of {dirs} dirs containing {dirdups} dups]:")
        for escaped_dir_tuple, cnt in self.dup_paths:
            dir_tuple = " ".join([unescape(e) for e in escaped_dir_tuple])
            print(f"{cnt}: {dir_tuple}")
        print(37 * "\n")
        already = {f for e in self.dup_paths for f in e[0]}

        def is_already(p: str) -> bool:
            p = get_path_parent(p)
            if not p:
                return False
            return True if p in already else is_already(p)

        x = list(
            filter(
                lambda el: el[0] > 2 * 1024**2
                and not all([is_already(e) for e in el[3]]),
                self.best(),
            )
        )
        print(f"Entries saving ≥ 2 MiB [list of {len(x)}]:")
        for _, hs, k, f in x:
            f = [unescape(e) for e in f]
            print(hs, k, " ".join(f), sep="\t")

    def _completer(self, prompt: str) -> None:
        """Generate suggested paths from prompt."""
        parent, child, _ = split_path(prompt + ".")
        child = child[:-1]
        # print((parent, child))
        if parent not in self.graph:
            self.completer_cache[prompt] = []
            return
        l = [parent + e for e, _ in self.graph[parent] if e.startswith(child)]
        if len(l) == 1:
            if l[0][-1] not in "\\/" or l[0] not in self.graph:
                l[0] += " "
        self.completer_cache[prompt] = l

    def _completer_wrapper(self, text: str, state: int) -> str | None:
        if text not in self.completer_cache:
            self._completer(text)
        cache = self.completer_cache[text]
        return cache[state] if state < len(cache) else None

    def console(self) -> None:
        """Open a console to surf through paths."""

        readline.set_completer(self._completer_wrapper)
        readline.set_completer_delims(" ")
        readline.parse_and_bind("tab: complete")
        try:
            while True:
                input()
        except EOFError:
            pass


def escape(t: str) -> str:
    """
    >>> escape('Lorem ipsum dolor sit amet.')
    'Lorem^sipsum^sdolor^ssit^samet.'
    >>> escape('^ ^^ ^s^^^')
    '^^^s^^^^^s^^s^^^^^^'
    """
    return t.replace("^", "^^").replace(" ", "^s")


def unescape(t: str) -> str:
    """
    >>> unescape('Lorem^sipsum^sdolor^ssit^samet.')
    '"Lorem ipsum dolor sit amet."'
    >>> unescape('^^^s^^^^^s^^s^^^^^^')
    '"^ ^^ ^s^^^"'
    """
    return '"' + re.sub(r"(?<!\^)((\^\^)*)\^s", r"\1 ", t).replace("^^", "^") + '"'


if __name__ == "__main__":
    fd = FileDump()
    fd.load_file("filedump.txt")
    # fd.print_info()
    if len(sys.argv) > 1:
        fd.console()
    else:
        fd.print_db()
