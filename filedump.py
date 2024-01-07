#!/usr/bin/env python3

# filedump.py -- part of disk-arranger
# Copyright (C) 2022, 2024 Marcin Zepp <nircek-2103@protonmail.com>

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

import os
import sys
from time import time
from platform import system
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from pathlib import Path
from argparse import ArgumentParser
from typing import IO

__version_info__ = ("2024", "01", "06")
__version__ = "-".join(__version_info__)


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


def isotime(unix: float) -> str:
    """
    Change Unix time in seconds into ISO8601 date.

    >>> isotime(1516969800)
    '2018-01-26T12:30:00Z'
    """
    date = datetime.fromtimestamp(unix, tz=timezone.utc)
    return date.isoformat().replace("+00:00", "Z")


def now() -> str:
    """Generate current ISO8601 date."""
    return isotime(int(time()))


def creation_date(st: os.stat_result) -> float | None:
    """Guess creation date from `os.stat_result`."""
    if system() == "Windows":
        return st.st_ctime  # it should test filesystem type, not the OS
    try:
        return st.st_birthtime  # type: ignore
    except AttributeError:
        return None


class LoggingUtility:
    """
    A helper class to:
    - limit throughput by specyfying logging interval,
    - gather processed files count and cumulative sum.
    """

    def __init__(self, stat_interval: float):
        self.start_time = time()
        self.stat_size = 0
        self.stat_count = 0
        self.stat_interval = stat_interval
        self.last_stat_time: float | None = None
        self.logged_count = 0
        self.logged_size = 0
        self.error_print("start")

    @classmethod
    def error_print(cls, msg: str, file: IO[str] = sys.stderr) -> None:
        """
        Print logging information.
        >>> LoggingUtility.error_print("a\\nb", sys.stdout)
        [...-...-...T...:...:...Z] a
        [...-...-...T...:...:...Z] b
        """
        msg = "\n".join([f"[{now()}] {l}" for l in msg.split("\n")])
        print(msg, file=file)

    def log(self, path: Path) -> None:
        """When it's time, log gathered stats."""
        if self.last_stat_time is None:
            self.last_stat_time = time()
        if time() - self.last_stat_time < self.stat_interval:
            return
        self.last_stat_time = time()
        self.logged_count, nc = self.stat_count, self.stat_count - self.logged_count
        self.logged_size, ns = self.stat_size, self.stat_size - self.logged_size
        hns = human_size(ns)
        duration = timedelta(seconds=(time() - self.start_time) // 1)
        msg = (
            f"{duration}\non {path}\nprocessed {self.stat_count:,} entities ({nc:,}"
            f" new)\nand {human_size(self.stat_size)} of data ({hns} new)"
        )
        self.error_print(msg)

    def print_stop(self) -> None:
        """Log the end time and final stats."""
        d = timedelta(seconds=time() - self.start_time)
        msg = (
            f"stop\n{d}\nprocessed {self.stat_count:,} entities"
            f"\nand {human_size(self.stat_size)} of data"
        )
        self.error_print(msg)


class FileTracer:
    """Dump whole path tree!"""

    def __init__(self, stat_interval: float = 5 * 60):
        self.logger = LoggingUtility(stat_interval)

    def sha256(self, path: Path, buf_size: int = 4 * 1024 * 1024) -> str:
        """Generate SHA256 hash of `path` file."""
        hasher = sha256()
        try:
            st = os.stat(path)
            with open(path, "rb") as f:
                while True:
                    data = f.read(buf_size)
                    if not data:
                        break
                    hasher.update(data)
            if os.stat(path).st_atime_ns != st.st_atime_ns:  # read-only filesystems
                try:
                    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
                except IOError as e:
                    msg = f"Cannot change `atime` {e}: {path}; {st} != {os.stat(path)}"
                    self.logger.error_print(msg)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error_print(f"Failed {path}\n{e}")
            return "failed"
        return hasher.hexdigest()

    def process_file(self, path: Path, folder: bool) -> None:
        """Dump information about file."""
        s = os.stat(path)
        sha, size = ("", 0) if folder else (self.sha256(path), s.st_size)
        self.logger.stat_size += size
        self.logger.stat_count += 1
        ctime = creation_date(s)
        props = [
            sha,
            size,
            *map(
                isotime,
                [s.st_atime, s.st_mtime, *([ctime] if ctime is not None else [])],
            ),
        ]
        self.logger.log(path)
        print(path, *props, sep="\t")

    def trace(self, startpath: str) -> None:
        """Walk recursively through starting directory and dump all paths."""
        for root, _, files in os.walk(startpath):
            root_path = Path(root)
            self.process_file(root_path, True)
            for f in files:
                path = root_path / f
                if not os.path.isfile(path):
                    print(f"Ignoring {path}", file=sys.stderr)
                    continue
                self.process_file(path, False)
        self.logger.print_stop()


if __name__ == "__main__":
    parser = ArgumentParser(prog="filedump.py")
    parser.add_argument("path", help="starting path", nargs="?", default=".")
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=5,
        help="interval between stats (in minutes)",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s ({__version__})"
    )
    args = parser.parse_args()
    # dirty windows hack to get printing utf-8 to work
    sys.stdout = open(1, "w", encoding="utf-8", closefd=False)
    tracer = FileTracer(args.interval * 60)
    tracer.trace(args.path)
