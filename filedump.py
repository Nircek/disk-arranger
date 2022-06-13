#!/usr/bin/env python3

# filedump.py
# Copyright (C) 2022 Marcin Zepp <nircek-2103@protonmail.com>

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
import time
import hashlib
import datetime
import pathlib
import argparse


def human_size(size):
    size_names = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB')
    size_map = ((1 << (i*10), e) for i, e in enumerate(size_names))
    r = f'{size} {size_names[0]}'
    for value, unit in size_map:
        if size < value:
            break
        q = size / value
        r = f'{q:.4g} {unit}'
    return r


def sha256(path, BUF_SIZE=4*1024*1024):
    sha256 = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha256.update(data)
    except Exception as e:
        print(f'Failed {path}', file=sys.stderr)
        print(e, file=sys.stderr)
        return 'failed'
    return sha256.hexdigest()


def isotime(unix):
    return (datetime.datetime.fromtimestamp(unix, tz=datetime.timezone.utc)
            .isoformat()
            .replace('+00:00', 'Z'))


def duration(stop=None, start=None):
    global START_TIME
    if stop is None:
        stop = time.time()
    if start is None:
        start = START_TIME
    return datetime.timedelta(seconds=(stop-start)//1)


STAT_SIZE = 0
STAT_COUNT = 0


def props(path, dir=False):
    global STAT_SIZE, STAT_COUNT
    s = os.stat(path)
    sha, size = ('', 0) if dir else (sha256(path), s.st_size)
    STAT_SIZE += size
    STAT_COUNT += 1
    return ([sha, size]
            + list(map(isotime, [s.st_atime, s.st_mtime, s.st_ctime])))


LAST_STAT = None
LAST_STAT_C, LAST_STAT_S = 0, 0
STAT_INTERVAL = 5*60


def log(path, props):
    global START_TIME, LAST_STAT, LAST_STAT_C, LAST_STAT_S, STAT_INTERVAL
    if LAST_STAT is None:
        LAST_STAT = time.time()
    if time.time() - LAST_STAT >= STAT_INTERVAL:
        LAST_STAT = time.time()
        LAST_STAT_C, nc = STAT_COUNT, STAT_COUNT - LAST_STAT_C
        LAST_STAT_S, ns = STAT_SIZE, STAT_SIZE - LAST_STAT_S
        ns = human_size(ns)
        now, v = lambda: isotime(time.time()), {"file": sys.stderr}
        print(f'[{now()}] {duration()}', **v)
        print(f'[{now()}] on {path}', **v)
        print(f'[{now()}] processed {STAT_COUNT:,} entities ({nc:,} new)', **v)
        print(f'[{now()}] and {human_size(STAT_SIZE)} of data ({ns} new)', **v)
    print(path, *props, sep='\t')


def trace(startpath):
    for root, _, files in os.walk(startpath):
        log(root, props(root, True))
        for f in files:
            path = pathlib.Path(root) / f
            if not os.path.isfile(path):
                print(f'Ignoring {path}', file=sys.stderr)
                continue
            log(path, props(path))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='starting path', nargs='?', default='.')
    parser.add_argument('-i', '--interval', type=float, default=5,
                        help='interval between stats (in minutes)')
    args = parser.parse_args()
    STAT_INTERVAL = args.interval*60
    # dirty windows hack to get printing utf-8 to work
    sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)
    START_TIME = time.time()
    print(f'[{isotime(START_TIME)}] start', file=sys.stderr)
    trace(args.path)
    STOP_TIME = time.time()
    print(f'[{isotime(STOP_TIME)}] stop', file=sys.stderr)
    d = datetime.timedelta(seconds=STOP_TIME-START_TIME)
    print(f'[{isotime(time.time())}] {d}', file=sys.stderr)
    print(f'processed {STAT_COUNT:,} entities', file=sys.stderr)
    print(f'and {human_size(STAT_SIZE)} of data', file=sys.stderr)
