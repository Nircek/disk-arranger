#!/usr/bin/env python3

# analyze.py -- part of disk-arranger
# Copyright (C) 2022-2023 Marcin Zepp <nircek-2103@protonmail.com>

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
# import readline

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

# it only supports Windows separators now :(
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
                path, sha, size, atime, mtime, ctime = line.rstrip().split('\t')
                path = escape(path)
                size, ctime = int(size), ctime
                parent, child, sep = splitParent(path)
                if sha == 'failed':
                    print(f'{sha=} {path=} {size=} {atime=} {mtime=} {ctime=}', file=sys.stderr)
                    continue
                if parent not in graph:
                    graph[parent] = []
                graph[parent] += [(child+('' if sha else sep), sha)]
                if sha not in db:
                    db[sha] = {}
                if '' in db[sha] and db[sha][''] != size:
                    print(f'{sha} sizes differ: {size} != {db[sha][""]}', file=sys.stderr)
                db[sha][''] = size
                db[sha][path] = (atime, mtime, ctime)
        except ValueError:
            print(f'Ignoring {repr(line)}')
    if ('.', '') in graph['']:
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


def best(dups):
    r = []
    for key, value in dups:
        adding = value['']
        size = human_size(adding)
        if len(value) > 2+1:
            q = len(value)-1-1
            adding = q * value['']
            total = human_size(adding)
            size = f'{total} = {q}*{size}'
        if adding < 2*1 << 20:
            break
        filenames = list(value.keys())
        filenames.remove('')
        r += [(size, key, filenames)]
    return r


def escape(t): return t.replace('^', '^^').replace(' ', '^s')


CARET_SPACE_RE = re.compile(r'(?<!\^)((\^\^)*)\^s')


def unescape(t): return '"' + CARET_SPACE_RE.sub(r'\1 ', t).replace('^^', '^') + '"'


def completer(text, state):
    parent, child, sep = splitParent(text)
    if parent not in graph:
        return None
    l = [parent+e for e, _ in graph[parent] if e.startswith(child)] + [None]
    if len(l) == 2 and l[0][-1] not in '\\/':
        l[0] += ' '
    return l[state]


if __name__ == "__main__":
    db, graph = getData('filedump')
    dups = getSortedDups(db)
    print((lambda x: f'{x[0]} / {x[1]}')(wasted(dups)), 'wasted')
    print()
    x = best(dups)
    X = [tuple(sorted([e.rsplit('\\', 1)[0] for e in files])) for _, _, files in x]
    from collections import Counter
    X = Counter(X)
    X = sorted([(-c, k) for k, c in filter(lambda e: e[1] > 1, X.items())])
    print(f'Duplicate dirs [list of {len(X)} dirs containing {sum(map(lambda e: -e[0], X))} dups]]:')
    for mc, k in X:
        k = ' '.join([unescape(e) for e in k])
        print(f'{-mc}: {k}')
    print(37*'\n')
    already = set([e[1] for e in X])
    x = list(filter(lambda el: tuple(sorted([e.rsplit('\\', 1)[0] for e in el[2]])) not in already, x))
    print(f'Entries saving ≥ 2 MiB [list of {len(x)}]:')
    for s, k, f in x:
        f = [unescape(e) for e in f]
        print(s, k, ' '.join(f), sep='\t')
    # readline.set_completer(completer)
    # readline.set_completer_delims(' ')
    # readline.parse_and_bind('tab: complete')
    # while True:
    #     try:
    #         input()
    #     except EOFError:
    #         break
