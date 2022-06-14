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

import sys
import math
import re
import functools
import readline
from filedump import human_size

SEP_RE = re.compile(r'[/\\]')


def splitParent(path):
    sep = SEP_RE.search(path)
    if sep is None:
        return '', path, ''
    sep = sep.group()
    s = path.rsplit(sep, 1)
    return s[0]+sep, s[1], sep


def getData(filename):
    db = {}
    graph = {}
    with open(filename, 'r') as file:
        try:
            for line in file:
                path, sha, size, atime, mtime, ctime = line.split('\t')
                path = escape(path)
                size, ctime = int(size), ctime.strip()
                parent, child, sep = splitParent(path)
                if parent not in graph:
                    graph[parent] = []
                graph[parent] += [(child+('' if sha else sep), sha)]
                if sha not in db:
                    db[sha] = {}
                if (db[sha][''] if '' in db[sha] else size) != size:
                    print(f'{sha} {size} {sha[path]}', file=sys.stderr)
                db[sha][''] = size
                db[sha][path] = (atime, mtime, ctime)
        except ValueError:
            print(f'Ignoring {repr(line)}')
    graph[''].remove(('.', ''))
    for e in ['./', '.\\']:
        if e in graph:
            graph[''] += [(e, '')]
    print(graph[''])
    return db, graph


def getSortedDups(db):
    return sorted(filter(
        lambda x: len(x[1]) > 1+1,
        db.items()),
        key=lambda e: (-e[1]['']*(len(e[1])-1-1), e[0]))


def wasted(dups):
    # total size = size * quantity
    def s(e): return e[1]['']*(len(e[1])-2)
    # func -- reduce total sizes with fn
    def f(s): return lambda o, e: o+s(e)
    # prettify reduced with fn
    def p(s): return human_size(functools.reduce(f(s), dups, 0))
    # ceil sizes to cluster size
    def c(b): return lambda x: math.ceil(s(x)/b)*b
    return p(s), p(c(4*1 << 10))


def best(dups, n=10):
    r = []
    for key, value in dups[:n]:
        size = human_size(value[''])
        if len(value) > 2+1:
            q = len(value)-1-1
            total = human_size(q*value[''])
            size = f'{total} = {q}*{size}'
        filenames = list(value.keys())
        filenames.remove('')
        r += [(size, key, str(filenames))]
    return r


def escape(t): return t.replace('^', '^^').replace(' ', '^s')


CARET_SPACE_RE = re.compile(r'(?<!\^)((\^\^)*)\^s')


def unescape(t): return CARET_SPACE_RE.sub(r'\1 ', t).replace('^^', '^')


def completer(text, state):
    parent, child, sep = splitParent(text)
    if parent not in graph:
        return None
    l = [parent+e for e, _ in graph[parent] if e.startswith(child)] + [None]
    if len(l) == 2 and l[0][-1] not in '\\/':
        l[0] += ' '
    return l[state]


if __name__ == "__main__":
    db, graph = getData('filedump.txt')
    dups = getSortedDups(db)
    print((lambda x: f'{x[0]} / {x[1]}')(wasted(dups)), 'wasted')
    print()
    print('Best 10 entries:')
    print(*['\t'.join(e) for e in best(dups)], sep='\n')
    readline.set_completer(completer)
    readline.set_completer_delims(' ')
    readline.parse_and_bind('tab: complete')
    while True:
        try:
            input()
        except EOFError:
            break
