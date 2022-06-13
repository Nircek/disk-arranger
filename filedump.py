import os
import sys
import hashlib
import datetime
import pathlib


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


def props(path, dir=False):
    s = os.stat(path)
    sha, size = ('', 0) if dir else (sha256(path), s.st_size)
    return ([sha, size]
            + list(map(isotime, [s.st_atime, s.st_mtime, s.st_ctime])))


def trace(startpath):
    for root, _, files in os.walk(startpath):
        print(root, *props(root, True), sep='\t')
        for f in files:
            path = pathlib.Path(root) / f
            if not os.path.isfile(path):
                print(f'Ignoring {path}', file=sys.stderr)
                continue
            print(path, *props(path), sep='\t')


if __name__ == '__main__':
    # windows hack to get printing utf-8 to work
    sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)
    trace('.')
