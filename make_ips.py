import sys
def ips(a, b):
    out = bytearray(b'PATCH'); i = 0; n = len(b)
    while i < n:
        if i < len(a) and a[i] == b[i]: i += 1; continue
        j = i
        while j < n and j - i < 0xFFFF and not (j < len(a) and a[j] == b[j] and j + 1 < n and a[j + 1] == b[j + 1]): j += 1
        if i == 0x454F46: i -= 1
        out += i.to_bytes(3, 'big') + (j - i).to_bytes(2, 'big') + b[i:j]; i = j
    return bytes(out + b'EOF')
if __name__ == '__main__':
    a = open(sys.argv[1], 'rb').read(); b = open(sys.argv[2], 'rb').read(); assert len(a) == len(b)
    open(sys.argv[3], 'wb').write(ips(a, b))
