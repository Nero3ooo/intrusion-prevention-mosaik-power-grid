import datetime
import sys

from cryptography import x509
from cryptography.hazmat._oid import NameOID
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey


def generate_ssl_certificate(monitor_id, path, rootca_cert, rootca_key):
    """
        Script that generates the keypair and a certificate and writes it to the given files. We use the shell command
            ' openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 '
        as a base and rebuild it as a python script
    """
    # filenames that we will put the key and cert in
    cert_file = path + monitor_id + "_cert.pem"
    key_file = path + monitor_id + "_key.pem"

    key = generate_keypair()
    # req = generate_certificate_request(key, monitor_id)
    cert = create_certificate(monitor_id, key, rootca_cert, rootca_key)

    # write the certificate into the file given
    with open(cert_file, 'w+b') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # write the private key into the file given
    with open(key_file, 'w+b') as f:
        f.write(key.private_bytes(encoding=serialization.Encoding.PEM,
                                  format=serialization.PrivateFormat.TraditionalOpenSSL,
                                  encryption_algorithm=serialization.BestAvailableEncryption(b"password")))


def generate_keypair():
    """
    Generate the public/private keypair for the certificate
    """

    # generate the public private keypair
    # we choose RSA encryption with 4096 bits, as it's the safest key we can create
    # The public exponent
    key = rsa.generate_private_key(public_exponent=65537, key_size=4096, backend=default_backend())
    # we choose RSA encryption with 4096 bits, as it's the safest key we can create

    return key


def generate_certificate_request(monitor_id, key):
    """
    Create a certificate request.
    This can be given to a CA, if this is wished for. We do not do that in the development stage, but this is necessary
    for commercial use.
    As we deal with self-signed certificates, we don't need this method right now

    :param monitor_id: The monitors monitor_id that the certificate is for
    :type monitor_id: str
    :param key: The private key to use for the certificate
    :type key: RSAPrivateKey
    """
    # based on the keys, generate a self-signed (or non-signed) certificate
    # define all the attributes needed for the certificate
    subj = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"DE"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"NRW"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Muenster"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"WWU"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u"FB10"),
        x509.NameAttribute(NameOID.COMMON_NAME, monitor_id)
    ])

    request = x509.CertificateSigningRequestBuilder().subject_name(subj).sign(key, hashes.SHA256())

    return request


def create_certificate(monitor_id, cert_key, rootca_cert, rootca_key):
    """
    Create a certificate. Therefore we set all the subject attributes and sign the certificate with our private key.

    :param monitor_id: The monitors monitor_id that the certificate is for
    :type monitor_id: str
    :param key: The private key to use for the certificate
    :type key: RSAPrivateKey
    """

    # define all the attributes needed for the certificate
    subj = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"DE"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"NRW"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Muenster"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"WWU"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u"FB10"),
        x509.NameAttribute(NameOID.COMMON_NAME, monitor_id)
    ])

    # Create the certificate with the help of a CertificateBuilder, set all attributes and sign with our private key
    cert = x509.CertificateBuilder().subject_name(subj) \
        .issuer_name(issuer) \
        .public_key(cert_key.public_key()) \
        .serial_number(x509.random_serial_number()) \
        .not_valid_before(datetime.datetime.utcnow()) \
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(hours=1)) \
        .sign(cert_key, hashes.SHA256(), default_backend())

    return cert


def create_root_key():
    root_key = generate_keypair()
    return root_key


def create_root_ca(root_key):
    # define all the attributes needed for the certificate
    subj = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"DE"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"NRW"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Muenster"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"WWU"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, u"FB10"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"rootCA")
    ])

    # Create the certificate with the help of a CertificateBuilder, set all attributes and sign with our private key
    root_cert = x509.CertificateBuilder().subject_name(subj) \
        .issuer_name(issuer) \
        .public_key(root_key.public_key()) \
        .serial_number(x509.random_serial_number()) \
        .not_valid_before(datetime.datetime.utcnow()) \
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(hours=10)) \
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True) \
        .sign(root_key, hashes.SHA256(), default_backend())

    return root_cert


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) == 2 else './'
    rootca_key = create_root_key()
    rootca_cert = create_root_ca(rootca_key)
    generate_ssl_certificate('c2', path, rootca_cert, rootca_key)
    generate_ssl_certificate('nm', path, rootca_cert, rootca_key)
    generate_ssl_certificate('lm', path, rootca_cert, rootca_key)
