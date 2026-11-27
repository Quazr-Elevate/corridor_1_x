"""Field-level encryption for KYB values (GSTIN, PAN, IEC, TRN…).

* :func:`encrypt` / :func:`decrypt` — AES-256-GCM with a random 96-bit nonce
  per value. The key version is bound into the ciphertext as associated
  data, so a value can't be decrypted under the wrong key slot.
  Stored form: ``base64(nonce || ciphertext+tag)``.
* :func:`value_hash` — HMAC-SHA256 of the normalised value under a separate
  key; lets the database reject a duplicate GSTIN without decrypting.
  :func:`value_hashes` gives the value under every hash key, current first,
  so a lookup still finds rows hashed before a rotation (CX-035).
* :func:`last4` — masked display hint.

Keys come from ``KYB_ENC_KEYS`` (``version:base64key,...``) and
``KYB_HASH_KEY`` (plus ``KYB_HASH_KEY_PREVIOUS``, match only); they never
touch the database or git. ``scripts/rotate_keys.py`` moves stored values to
the newest keys. With DEBUG=false the
app refuses to start without them (:func:`check_keys`). Development uses a
fixed, clearly-marked local key so it works out of the box — data encrypted
with it is NOT protected.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings, settings

_NONCE_BYTES = 12
_KEY_BYTES = 32
_DEV_ENC_KEY = hashlib.sha256(b"cor1x-dev-only-kyb-encryption-key").digest()
_DEV_HASH_KEY = hashlib.sha256(b"cor1x-dev-only-kyb-hash-key").digest()


class CryptoConfigError(RuntimeError):
    """Missing or malformed key configuration."""


class DecryptionError(RuntimeError):
    """Ciphertext is corrupt, or was encrypted with an unknown key."""


@dataclass(frozen=True)
class _Keys:
    enc: dict[int, bytes]
    current: int
    hash_key: bytes
    is_dev: bool
    previous_hash_keys: tuple[bytes, ...] = ()


def _b64key(raw: str, what: str) -> bytes:
    try:
        key = base64.b64decode(raw.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise CryptoConfigError(f"{what} is not valid base64.") from None
    if len(key) != _KEY_BYTES:
        raise CryptoConfigError(f"{what} must decode to {_KEY_BYTES} bytes (got {len(key)}).")
    return key


def load_keys(s: Settings) -> _Keys:
    """Parse key settings. With both settings empty, the development keys
    are used while DEBUG is on or STRICT_STARTUP is off (A-069); malformed
    keys are always refused, since data written with them couldn't be read."""
    enc_raw, hash_raw = s.kyb_enc_keys.strip(), s.kyb_hash_key.strip()
    if not enc_raw and not hash_raw and (s.debug or not s.strict_startup):
        return _Keys(enc={1: _DEV_ENC_KEY}, current=1, hash_key=_DEV_HASH_KEY, is_dev=True)
    if not enc_raw or not hash_raw:
        raise CryptoConfigError("KYB_ENC_KEYS and KYB_HASH_KEY must both be set when DEBUG=false and STRICT_STARTUP=true.")
    enc: dict[int, bytes] = {}
    for part in enc_raw.split(","):
        version, sep, key = part.strip().partition(":")
        if not sep or not version.isdigit() or not 1 <= int(version) <= 32767:
            raise CryptoConfigError("KYB_ENC_KEYS entries must look like 'version:base64key' (version 1–32767).")
        if int(version) in enc:
            raise CryptoConfigError(f"KYB_ENC_KEYS lists version {version} twice.")
        enc[int(version)] = _b64key(key, f"KYB_ENC_KEYS version {version}")
    hash_key = _b64key(hash_raw, "KYB_HASH_KEY")
    if hash_key in enc.values():
        raise CryptoConfigError("KYB_HASH_KEY must differ from every encryption key.")
    previous: list[bytes] = []
    for i, raw in enumerate(p for p in s.kyb_hash_key_previous.split(",") if p.strip()):
        key = _b64key(raw, f"KYB_HASH_KEY_PREVIOUS entry {i + 1}")
        if key == hash_key or key in previous or key in enc.values():
            raise CryptoConfigError("Each KYB_HASH_KEY_PREVIOUS entry must differ from KYB_HASH_KEY, each other and the encryption keys.")
        previous.append(key)
    return _Keys(enc=enc, current=max(enc), hash_key=hash_key, is_dev=False, previous_hash_keys=tuple(previous))


@lru_cache(maxsize=1)
def _keys() -> _Keys:
    return load_keys(settings)


def check_keys(s: Settings = settings) -> bool:
    """Validate configuration at startup; returns True when dev keys are in
    use. Raises :class:`CryptoConfigError` otherwise misconfigured."""
    return load_keys(s).is_dev


def encrypt(plaintext: str) -> tuple[str, int]:
    """Return ``(ciphertext_b64, key_version)``."""
    k = _keys()
    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(k.enc[k.current]).encrypt(nonce, plaintext.encode("utf-8"), _aad(k.current))
    return base64.b64encode(nonce + ct).decode("ascii"), k.current


def decrypt(ciphertext_b64: str, key_version: int) -> str:
    k = _keys()
    key = k.enc.get(key_version)
    if key is None:
        raise DecryptionError(f"No key configured for version {key_version}.")
    try:
        blob = base64.b64decode(ciphertext_b64, validate=True)
        return AESGCM(key).decrypt(blob[:_NONCE_BYTES], blob[_NONCE_BYTES:], _aad(key_version)).decode("utf-8")
    except (InvalidTag, binascii.Error, ValueError):
        raise DecryptionError("Value could not be decrypted.") from None


def current_version() -> int:
    """The key version :func:`encrypt` writes with."""
    return _keys().current


def configured_versions() -> list[int]:
    return list(_keys().enc)


def _aad(version: int) -> bytes:
    return f"cor1x-kyb-v{version}".encode()


_SPACE = re.compile(r"\s+")
_SEPARATORS = re.compile(r"[\s\-./]+")


def normalize_value(raw: str) -> str:
    """Stored / validated form: upper-case, whitespace removed
    (``22aaaaa 0000a1z5`` → ``22AAAAA0000A1Z5``; dashes in ``UDYAM-KA-…`` stay)."""
    return _SPACE.sub("", raw).upper()


def value_hash(normalized: str, *, scope: str) -> str:
    """Keyed hash, scoped to a document type so equal numbers of different
    types don't collide. Separators are ignored, so ``UDYAM-KA-01-…`` and
    ``UDYAMKA01…`` count as the same number."""
    return _hash(_keys().hash_key, normalized, scope)


def value_hashes(normalized: str, *, scope: str) -> list[str]:
    """The value under the current hash key, then every previous one."""
    k = _keys()
    return [_hash(key, normalized, scope) for key in (k.hash_key, *k.previous_hash_keys)]


def _hash(key: bytes, normalized: str, scope: str) -> str:
    msg = f"{scope}\x00{_SEPARATORS.sub('', normalized)}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def last4(normalized: str) -> str:
    return normalized[-4:]


def mask(last: str | None) -> str | None:
    return f"••••{last}" if last else None
