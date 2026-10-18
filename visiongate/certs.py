"""Самоподписанный сертификат для HTTPS в локальной сети (камера в мобильном браузере требует HTTPS)."""
import datetime
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _local_ips() -> set[str]:
    ips = {"127.0.0.1"}
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    try:  # IP основного сетевого интерфейса (пакеты никуда не отправляются)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    return ips


def ensure_cert(folder: Path) -> tuple[Path, Path]:
    cert, key = folder / "cert.pem", folder / "key.pem"
    ips = _local_ips()
    if cert.exists() and key.exists():
        try:  # пересоздаём, если сменился IP ноутбука
            c = x509.load_pem_x509_certificate(cert.read_bytes())
            have = {str(i) for i in c.extensions.get_extension_for_class(x509.SubjectAlternativeName)
                    .value.get_values_for_type(x509.IPAddress)}
            if ips <= have and c.not_valid_after_utc > datetime.datetime.now(datetime.timezone.utc):
                return cert, key
        except Exception:
            pass
    folder.mkdir(parents=True, exist_ok=True)
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "VisionGate local")])
    now = datetime.datetime.now(datetime.timezone.utc)
    san = [x509.DNSName("localhost"), x509.DNSName(socket.gethostname())] + \
          [x509.IPAddress(ipaddress.ip_address(i)) for i in sorted(ips)]
    c = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
         .not_valid_after(now + datetime.timedelta(days=825))
         .add_extension(x509.SubjectAlternativeName(san), critical=False)
         .sign(k, hashes.SHA256()))
    key.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                    serialization.NoEncryption()))
    cert.write_bytes(c.public_bytes(serialization.Encoding.PEM))
    # консольные сообщения — по-английски: консоль Windows PowerShell 5.1 искажает кириллицу
    print("HTTPS: self-signed certificate created for", ", ".join(sorted(ips)))
    return cert, key
