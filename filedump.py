import sys
import hashlib
import datetime
import os

sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)

def sha256(path, BUF_SIZE = 4*1024*1024):
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
    return datetime.datetime.fromtimestamp(unix, tz=datetime.timezone.utc).isoformat().replace('+00:00','Z')

def props(path, size=None):
    s = os.stat(path)
    if size is None:
        size = s.st_size
    return [size] + list(map(isotime, [s.st_atime, s.st_mtime, s.st_ctime]))

def trace(startpath):
    for root, dirs, files in os.walk(startpath):
        print(root, '', *props(root, 0), sep='\t')
        for f in files:
            path = root+os.sep+f
            if not os.path.isfile(path):
                print(f'Ignoring {path}', file=sys.stderr)
                continue
            print(path, sha256(path), *props(path), sep='\t')

if __name__ == '__main__':
    trace('.')
