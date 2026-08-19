"""Pure-Python Bitcoin key math for OnePiece Bitcoin.

No third-party dependencies. Everything here is standard, well-known
cryptography (secp256k1, SHA-256, RIPEMD-160, Base58Check) implemented so the
tool runs anywhere `python3` runs, with nothing to compile or install.

Speed is not the point of this file: the odds of the hunt are effectively
zero regardless, so correctness and portability win over raw throughput.
"""

from __future__ import annotations
import hashlib

# --- secp256k1 curve parameters ---
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
A = 0
B = 7
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
G = (GX, GY)


def _inv(x: int, m: int = P) -> int:
    return pow(x, -1, m)


def point_add(p, q):
    if p is None:
        return q
    if q is None:
        return p
    x1, y1 = p
    x2, y2 = q
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if p == q:
        m = (3 * x1 * x1 + A) * _inv(2 * y1) % P
    else:
        m = (y2 - y1) * _inv(x2 - x1) % P
    x3 = (m * m - x1 - x2) % P
    y3 = (m * (x1 - x3) - y1) % P
    return (x3, y3)


def scalar_mul(k: int, point=G):
    """Return k*point on secp256k1 (double-and-add)."""
    if k % N == 0 or point is None:
        return None
    if k < 0:
        return scalar_mul(-k, (point[0], (-point[1]) % P))
    result = None
    addend = point
    while k:
        if k & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        k >>= 1
    return result


def privkey_to_pubkey_compressed(k: int) -> bytes:
    """33-byte compressed SEC public key for private scalar k."""
    x, y = scalar_mul(k)
    prefix = 0x02 if (y % 2 == 0) else 0x03
    return bytes([prefix]) + x.to_bytes(32, "big")


def decompress_pubkey(pub) -> tuple[int, int]:
    """Recover the (x, y) point from a 33-byte compressed public key.

    Accepts a hex string or bytes. secp256k1 has p ≡ 3 (mod 4), so the square
    root is a single modular exponentiation.
    """
    b = bytes.fromhex(pub) if isinstance(pub, str) else bytes(pub)
    if len(b) != 33 or b[0] not in (0x02, 0x03):
        raise ValueError("expected a 33-byte compressed public key (02/03 prefix)")
    x = int.from_bytes(b[1:], "big")
    y2 = (pow(x, 3, P) + B) % P
    y = pow(y2, (P + 1) // 4, P)
    if (y * y - y2) % P != 0:
        raise ValueError("public key x is not on the curve")
    if (y & 1) != (b[0] & 1):
        y = P - y
    return (x, y)


# --- hashes ---

def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def _ripemd160_pure(msg: bytes) -> bytes:
    """Pure-Python RIPEMD-160 (used if hashlib lacks it, e.g. OpenSSL 3)."""
    import struct

    def rol(x, n):
        return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF

    rl = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
        7, 4, 13, 1, 10, 6, 15, 3, 12, 0, 9, 5, 2, 14, 11, 8,
        3, 10, 14, 4, 9, 15, 8, 1, 2, 7, 0, 6, 13, 11, 5, 12,
        1, 9, 11, 10, 0, 8, 12, 4, 13, 3, 7, 15, 14, 5, 6, 2,
        4, 0, 5, 9, 7, 12, 2, 10, 14, 1, 3, 8, 11, 6, 15, 13,
    ]
    rr = [
        5, 14, 7, 0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12,
        6, 11, 3, 7, 0, 13, 5, 10, 14, 15, 8, 12, 4, 9, 1, 2,
        15, 5, 1, 3, 7, 14, 6, 9, 11, 8, 12, 2, 10, 0, 4, 13,
        8, 6, 4, 1, 3, 11, 15, 0, 5, 12, 2, 13, 9, 7, 10, 14,
        12, 15, 10, 4, 1, 5, 8, 7, 6, 2, 13, 14, 0, 3, 9, 11,
    ]
    sl = [
        11, 14, 15, 12, 5, 8, 7, 9, 11, 13, 14, 15, 6, 7, 9, 8,
        7, 6, 8, 13, 11, 9, 7, 15, 7, 12, 15, 9, 11, 7, 13, 12,
        11, 13, 6, 7, 14, 9, 13, 15, 14, 8, 13, 6, 5, 12, 7, 5,
        11, 12, 14, 15, 14, 15, 9, 8, 9, 14, 5, 6, 8, 6, 5, 12,
        9, 15, 5, 11, 6, 8, 13, 12, 5, 12, 13, 14, 11, 8, 5, 6,
    ]
    sr = [
        8, 9, 9, 11, 13, 15, 15, 5, 7, 7, 8, 11, 14, 14, 12, 6,
        9, 13, 15, 7, 12, 8, 9, 11, 7, 7, 12, 7, 6, 15, 13, 11,
        9, 7, 15, 11, 8, 6, 6, 14, 12, 13, 5, 14, 13, 13, 7, 5,
        15, 5, 8, 11, 14, 14, 6, 14, 6, 9, 12, 9, 12, 5, 15, 8,
        8, 5, 12, 9, 12, 5, 14, 6, 8, 13, 6, 5, 15, 13, 11, 11,
    ]
    kl = [0x00000000, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E]
    kr = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0x00000000]

    def f(j, x, y, z):
        if j < 16:
            return x ^ y ^ z
        if j < 32:
            return (x & y) | (~x & z)
        if j < 48:
            return (x | ~y) ^ z
        if j < 64:
            return (x & z) | (y & ~z)
        return x ^ (y | ~z)

    ml = len(msg)
    msg = msg + b"\x80" + b"\x00" * ((55 - ml) % 64) + struct.pack("<Q", ml * 8)
    h0, h1, h2, h3, h4 = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0
    for off in range(0, len(msg), 64):
        x = list(struct.unpack("<16I", msg[off:off + 64]))
        al, bl, cl, dl, el = h0, h1, h2, h3, h4
        ar, br, cr, dr, er = h0, h1, h2, h3, h4
        for j in range(80):
            t = (al + f(j, bl, cl, dl) + x[rl[j]] + kl[j // 16]) & 0xFFFFFFFF
            t = (rol(t, sl[j]) + el) & 0xFFFFFFFF
            al, el, dl, cl, bl = el, dl, rol(cl, 10), bl, t
            t = (ar + f(79 - j, br, cr, dr) + x[rr[j]] + kr[j // 16]) & 0xFFFFFFFF
            t = (rol(t, sr[j]) + er) & 0xFFFFFFFF
            ar, er, dr, cr, br = er, dr, rol(cr, 10), br, t
        t = (h1 + cl + dr) & 0xFFFFFFFF
        h1 = (h2 + dl + er) & 0xFFFFFFFF
        h2 = (h3 + el + ar) & 0xFFFFFFFF
        h3 = (h4 + al + br) & 0xFFFFFFFF
        h4 = (h0 + bl + cr) & 0xFFFFFFFF
        h0 = t
    return struct.pack("<5I", h0, h1, h2, h3, h4)


def ripemd160(b: bytes) -> bytes:
    try:
        h = hashlib.new("ripemd160")
        h.update(b)
        return h.digest()
    except (ValueError, TypeError):
        return _ripemd160_pure(b)


def hash160(b: bytes) -> bytes:
    return ripemd160(sha256(b))


def pubkey_to_hash160(pubkey: bytes) -> bytes:
    return hash160(pubkey)


# --- Base58 / addresses ---
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_MAP = {c: i for i, c in enumerate(_B58)}


def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    out = ""
    while n > 0:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = 0
    for byte in b:
        if byte == 0:
            pad += 1
        else:
            break
    return "1" * pad + out


def b58decode(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + _B58_MAP[c]
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = 0
    for c in s:
        if c == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + body


def hash160_to_address(h160: bytes, version: int = 0x00) -> str:
    payload = bytes([version]) + h160
    checksum = sha256(sha256(payload))[:4]
    return b58encode(payload + checksum)


def address_to_hash160(addr: str) -> bytes:
    """Decode a P2PKH (version 0x00) base58check address to its 20-byte hash160.

    Raises ValueError on a bad checksum or non-P2PKH address.
    """
    raw = b58decode(addr)
    if len(raw) != 25:
        raise ValueError(f"unexpected decoded length {len(raw)} for {addr}")
    payload, checksum = raw[:-4], raw[-4:]
    if sha256(sha256(payload))[:4] != checksum:
        raise ValueError(f"bad checksum for {addr}")
    if payload[0] != 0x00:
        raise ValueError(f"not a P2PKH (version {payload[0]:#x}) address: {addr}")
    return payload[1:]


def privkey_to_address(k: int) -> str:
    return hash160_to_address(pubkey_to_hash160(privkey_to_pubkey_compressed(k)))


if __name__ == "__main__":
    # Self-test against known Bitcoin Puzzle values.
    # Puzzle #1: private key = 1
    pk1 = privkey_to_pubkey_compressed(1).hex()
    assert pk1 == "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798", pk1
    addr1 = privkey_to_address(1)
    assert addr1 == "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH", addr1
    # round-trip a known unsolved address (#71) through decode/encode
    a71 = "1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU"
    assert hash160_to_address(address_to_hash160(a71)) == a71
    # decompressing puzzle #1's public key must give the generator point G
    assert decompress_pubkey(pk1) == (GX, GY)
    print("crypto self-test OK")
    print("  puzzle #1 pubkey:", pk1)
    print("  puzzle #1 address:", addr1)
