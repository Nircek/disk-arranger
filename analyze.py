#!/usr/bin/env python3

# analyze.py -- part of disk-arranger
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

import functools
import math
from filedump import human_size


def getData(filename):
    data = {}
    with open(filename, 'r') as file:
        try:
            for line in file:
                path, sha, size, atime, mtime, ctime = line.split('\t')
                size, ctime = int(size), ctime.strip()
                if (size, sha) not in data:
                    data[(size, sha)] = []
                data[(size, sha)] += [(path, atime, mtime, ctime)]
        except ValueError:
            print(f'Ignoring {repr(line)}')

    return sorted(filter(
        lambda x: len(x[1]) > 1,
        data.items()),
        key=lambda e: (-e[0][0]*(len(e[1])-1), e[0][1]))


def wasted(data):
    def s(e): return e[0][0]*(len(e[1])-1)
    def f(s): return lambda o, e: o+s(e)
    def p(s): return human_size(functools.reduce(f(s), data, 0))
    def c(b): return lambda x: math.ceil(s(x)/b)*b
    return p(s), p(c(4*1 << 10))


def best(data, n=10):
    r = []
    for key, value in data[:n]:
        size = human_size(key[0])
        if len(value) > 2:
            q = len(value)-1
            total = human_size(q*key[0])
            size = f'{total} = {q}*{size}'
        r += [(size, key[1], str(list(map(lambda x: x[0], value))))]
    return r


if __name__ == "__main__":
    data = getData('filedump.txt')
    print((lambda x: f'{x[0]} / {x[1]}')(wasted(data)), 'wasted')
    print()
    print('Best 10 entries:')
    print(*['\t'.join(e) for e in best(data)], sep='\n')
