"""
CloudSentinel TLS — self-signed certificate auto-generation.
Creates realistic certificates mimicking target organization on first run.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

logger = structlog.get_logger("cloudsentinel.tls")


def generate_self_signed_cert(
    hostname: str = "usas-prod-srv-01",
    org: str = "Universiti Sultan Azlan Shah",
    org_unit: str = "IT Department",
    country: str = "MY",
    state: str = "Perak",
    city: str = "Kuala Kangsar",
    output_dir: str = "var/lib/cloudsentinel/tls",
) -> tuple[str, str]:
    """Generate a realistic self-signed TLS certificate.

    Returns (cert_path, key_path) — creates files on disk.
    Uses only stdlib + cryptography (already a dependency).
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        logger.warning("cryptography not available — skipping TLS cert generation")
        return "", ""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    cert_path = out / f"{hostname}.crt"
    key_path = out / f"{hostname}.key"

    if cert_path.exists() and key_path.exists():
        logger.info("TLS cert already exists: %s", cert_path)
        return str(cert_path), str(key_path)

    # Generate RSA key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Build certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
        x509.NameAttribute(NameOID.LOCALITY_NAME, city),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, org_unit),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(hostname)]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    # Write key
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)

    # Write cert
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    logger.info("Generated self-signed TLS cert: CN=%s, O=%s", hostname, org)
    return str(cert_path), str(key_path)
