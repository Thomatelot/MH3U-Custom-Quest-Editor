"""Sign an APK with APK Signature Scheme v2 (after a v1 / JAR signature and zipalign).

Usage: python sign_apk.py KEYSTORE.p12 PASSWORD IN.apk OUT.apk

Pure Python (needs the 'cryptography' package): Google's apksigner is not needed.
Follows https://source.android.com/docs/security/features/apksigning/v2 :
the content digest covers the ZIP entries, the central directory and the end of
central directory record (with its central directory offset as it was before the
signing block was inserted), in 1 MiB chunks.
"""
from __future__ import annotations

import hashlib
import struct
import sys

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12

V2_ID = 0x7109871A
RSA_PKCS1_SHA256 = 0x0103
CHUNK = 1 << 20


def lp(b: bytes) -> bytes:
    return struct.pack("<I", len(b)) + b


def find_eocd(data: bytes) -> int:
    for i in range(len(data) - 22, max(-1, len(data) - 22 - 0xFFFF - 1), -1):
        if data[i:i + 4] == b"PK\x05\x06":
            (comment_len,) = struct.unpack_from("<H", data, i + 20)
            if i + 22 + comment_len == len(data):
                return i
    raise ValueError("end of central directory not found")


def digest(sections) -> bytes:
    chunks = []
    for s in sections:
        for k in range(0, len(s), CHUNK):
            part = s[k:k + CHUNK]
            chunks.append(hashlib.sha256(b"\xa5" + struct.pack("<I", len(part)) + part).digest())
    return hashlib.sha256(b"\x5a" + struct.pack("<I", len(chunks)) + b"".join(chunks)).digest()


def sign(keystore: str, password: str, src: str, dst: str) -> None:
    data = open(src, "rb").read()
    eocd = find_eocd(data)
    (cd_off,) = struct.unpack_from("<I", data, eocd + 16)
    if data[cd_off - 16:cd_off] == b"APK Sig Block 42":
        raise ValueError("already signed with v2")
    entries, cd, end = data[:cd_off], data[cd_off:eocd], data[eocd:]
    key, cert, _extra = pkcs12.load_key_and_certificates(open(keystore, "rb").read(), password.encode())
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    pub_der = key.public_key().public_bytes(serialization.Encoding.DER,
                                           serialization.PublicFormat.SubjectPublicKeyInfo)
    content = digest([entries, cd, end])
    signed_data = (lp(lp(struct.pack("<I", RSA_PKCS1_SHA256) + lp(content)))   # digests
                   + lp(lp(cert_der))                                        # certificates
                   + lp(b""))                                                # additional attributes
    sig = key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())
    signer = lp(signed_data) + lp(lp(struct.pack("<I", RSA_PKCS1_SHA256) + lp(sig))) + lp(pub_der)
    value = lp(lp(signer))
    pair = struct.pack("<QI", 4 + len(value), V2_ID) + value
    size = len(pair) + 8 + 16
    block = struct.pack("<Q", size) + pair + struct.pack("<Q", size) + b"APK Sig Block 42"
    new_end = bytearray(end)
    struct.pack_into("<I", new_end, 16, cd_off + len(block))
    with open(dst, "wb") as f:
        f.write(entries + block + cd + bytes(new_end))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    sign(*sys.argv[1:])
