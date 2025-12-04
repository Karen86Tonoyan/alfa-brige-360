# ═══════════════════════════════════════════════════════════════════════════
# PQXHYBRID - Post-Quantum Cryptography Module
# ═══════════════════════════════════════════════════════════════════════════
"""
Pluggable helpers for hybrid post-quantum signatures.

Supports:
- Falcon (lattice-based)
- SPHINCS+ (hash-based)
- Dilithium (lattice-based)

The module provides placeholder implementations that can be swapped
for real OQS (Open Quantum Safe) providers when available.
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
import secrets
from typing import Dict, Iterable, Optional, Protocol, Tuple

__all__ = [
    "AlgorithmSpec",
    "PQKeyPair",
    "UnsupportedSchemeError",
    "InvalidSignatureError",
    "FrameFormatError",
    "generate_keypair",
    "sign_message",
    "verify_message",
    "sign_frame",
    "verify_frame",
    "available_schemes",
    "register_provider",
    "unregister_provider",
]


class UnsupportedSchemeError(ValueError):
    """Raised when an unsupported signature scheme is requested."""


class InvalidSignatureError(ValueError):
    """Raised when signature verification fails."""


class FrameFormatError(ValueError):
    """Raised when a serialized frame cannot be decoded."""


@dataclass(frozen=True)
class AlgorithmSpec:
    """Algorithm-specific constants."""
    name: str
    secret_size: int
    public_size: int
    signature_size: int
    personalization: bytes


@dataclass(frozen=True)
class PQKeyPair:
    """Post-quantum key pair."""
    scheme: str
    public_key: bytes
    secret_key: bytes

    def encode(self) -> Tuple[str, str, str]:
        """Return tuple with scheme and base64-encoded keys."""
        return (
            self.scheme,
            base64.b64encode(self.public_key).decode("ascii"),
            base64.b64encode(self.secret_key).decode("ascii"),
        )
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        scheme, pub, sec = self.encode()
        return {"scheme": scheme, "public_key": pub, "secret_key": sec}


class SignatureProvider(Protocol):
    """Interface for signature providers."""
    spec: AlgorithmSpec

    def generate_keypair(self, seed: Optional[bytes]) -> PQKeyPair:
        """Create a new key pair."""

    def sign(self, message: bytes, keypair: PQKeyPair) -> bytes:
        """Return a signature for message."""

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Return True when signature is valid."""


_PROVIDERS: Dict[str, SignatureProvider] = {}


def _shake(data: Iterable[bytes], length: int) -> bytes:
    """SHAKE256 hash."""
    digest = hashlib.shake_256()
    for chunk in data:
        digest.update(chunk)
    return digest.digest(length)


def _get_provider(scheme: str) -> SignatureProvider:
    try:
        return _PROVIDERS[scheme.lower()]
    except KeyError as exc:
        raise UnsupportedSchemeError(f"Unsupported scheme: {scheme}") from exc


def available_schemes() -> Tuple[str, ...]:
    """Return registered scheme identifiers."""
    return tuple(_PROVIDERS.keys())


def register_provider(scheme: str, provider: SignatureProvider, *, override: bool = False) -> None:
    """Register a signature provider."""
    key = scheme.lower()
    if key in _PROVIDERS and not override:
        raise ValueError(f"Provider already registered for {scheme}")
    _PROVIDERS[key] = provider


def unregister_provider(scheme: str) -> None:
    """Remove a provider."""
    try:
        del _PROVIDERS[scheme.lower()]
    except KeyError as exc:
        raise UnsupportedSchemeError(f"Unsupported scheme: {scheme}") from exc


class PlaceholderProvider:
    """Deterministic provider for testing (NOT SECURE)."""

    def __init__(self, spec: AlgorithmSpec):
        self.spec = spec

    def _derive_public_key(self, secret_key: bytes) -> bytes:
        return _shake((secret_key, self.spec.personalization, b"pk"), self.spec.public_size)

    def generate_keypair(self, seed: Optional[bytes]) -> PQKeyPair:
        if seed is None:
            seed = secrets.token_bytes(self.spec.secret_size)
        secret_key = _shake((seed, self.spec.personalization, b"sk"), self.spec.secret_size)
        public_key = self._derive_public_key(secret_key)
        return PQKeyPair(scheme=self.spec.name, public_key=public_key, secret_key=secret_key)

    def sign(self, message: bytes, keypair: PQKeyPair) -> bytes:
        if keypair.scheme.lower() != self.spec.name:
            raise InvalidSignatureError(f"Scheme mismatch: expected {self.spec.name}")
        derived_public = self._derive_public_key(keypair.secret_key)
        if derived_public != keypair.public_key:
            raise InvalidSignatureError("Key pair mismatch")
        return _shake(
            (self.spec.personalization, keypair.public_key, message, b"sig"),
            self.spec.signature_size,
        )

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        expected = _shake(
            (self.spec.personalization, public_key, message, b"sig"),
            self.spec.signature_size,
        )
        return secrets.compare_digest(signature, expected)


def _register_default_placeholders() -> None:
    """Register placeholder providers for all schemes."""
    register_provider(
        "falcon",
        PlaceholderProvider(
            AlgorithmSpec(
                name="falcon",
                secret_size=48,
                public_size=48,
                signature_size=56,
                personalization=b"falcon-cerber-v7",
            )
        ),
    )
    register_provider(
        "sphincs",
        PlaceholderProvider(
            AlgorithmSpec(
                name="sphincs",
                secret_size=64,
                public_size=64,
                signature_size=64,
                personalization=b"sphincs-cerber-v7",
            )
        ),
    )
    register_provider(
        "dilithium",
        PlaceholderProvider(
            AlgorithmSpec(
                name="dilithium",
                secret_size=64,
                public_size=48,
                signature_size=48,
                personalization=b"dilithium-cerber-v7",
            )
        ),
    )


def _register_oqs_providers() -> None:
    """Try to register real OQS providers if available."""
    try:
        import oqs

        class OQSProvider:
            def __init__(self, scheme: str, algorithm: str):
                self.scheme = scheme
                self.algorithm = algorithm
                with oqs.Signature(algorithm) as sig:
                    details = sig.details
                    self.spec = AlgorithmSpec(
                        name=scheme,
                        secret_size=details.length_secret_key,
                        public_size=details.length_public_key,
                        signature_size=details.length_signature,
                        personalization=algorithm.encode("ascii", "ignore"),
                    )

            def generate_keypair(self, seed: Optional[bytes]) -> PQKeyPair:
                if seed is not None:
                    raise ValueError("Deterministic keygen not supported by OQS")
                with oqs.Signature(self.algorithm) as sig:
                    public_key, secret_key = sig.generate_keypair()
                return PQKeyPair(scheme=self.scheme, public_key=public_key, secret_key=secret_key)

            def sign(self, message: bytes, keypair: PQKeyPair) -> bytes:
                with oqs.Signature(self.algorithm) as sig:
                    return sig.sign(message, keypair.secret_key)

            def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
                with oqs.Signature(self.algorithm) as sig:
                    return sig.verify(message, signature, public_key)

        oqs_algorithms = {
            "falcon": "Falcon-1024",
            "sphincs": "SPHINCS+-SHA2-128s-simple",
            "dilithium": "Dilithium3",
        }
        for scheme, algorithm in oqs_algorithms.items():
            try:
                register_provider(scheme, OQSProvider(scheme, algorithm), override=True)
            except Exception:
                continue
    except ImportError:
        pass


# Initialize providers
_register_default_placeholders()
_register_oqs_providers()


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def generate_keypair(scheme: str, seed: Optional[bytes] = None) -> PQKeyPair:
    """Generate a key pair for the specified scheme."""
    provider = _get_provider(scheme)
    try:
        return provider.generate_keypair(seed)
    except ValueError as exc:
        raise InvalidSignatureError(str(exc)) from exc


def sign_message(message: bytes, keypair: PQKeyPair) -> bytes:
    """Sign a message with the keypair."""
    provider = _get_provider(keypair.scheme)
    return provider.sign(message, keypair)


def verify_message(message: bytes, signature: bytes, scheme: str, public_key: bytes) -> bool:
    """Verify a signature."""
    provider = _get_provider(scheme)
    return provider.verify(message, signature, public_key)


def sign_frame(payload: bytes, keypair: PQKeyPair) -> bytes:
    """Create a signed JSON frame."""
    signature = sign_message(payload, keypair)
    frame = {
        "scheme": keypair.scheme,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signature": base64.b64encode(signature).decode("ascii"),
        "version": "cerber-v7",
    }
    return json.dumps(frame, separators=(",", ":")).encode("utf-8")


def verify_frame(frame: bytes, public_key: bytes) -> Tuple[bytes, str]:
    """Verify a signed frame and return (payload, scheme)."""
    try:
        document = json.loads(frame.decode("utf-8"))
        scheme = document["scheme"]
        payload_b64 = document["payload"]
        signature_b64 = document["signature"]
    except (UnicodeDecodeError, KeyError, json.JSONDecodeError) as exc:
        raise FrameFormatError("Could not decode signature frame") from exc

    payload = base64.b64decode(payload_b64)
    signature = base64.b64decode(signature_b64)
    if not verify_message(payload, signature, scheme=scheme, public_key=public_key):
        raise InvalidSignatureError("Signature check failed")
    return payload, scheme
