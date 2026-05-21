from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

def generate_keys():
    print("🔑 Generating RSA 2048-bit key pair...")
    
    # Generate Private Key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Serialize Private Key to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Serialize Public Key to PEM
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Save to files
    with open('credentials/aggregator_private.pem', 'wb') as f:
        f.write(private_pem)
    
    with open('credentials/aggregator_public.pem', 'wb') as f:
        f.write(public_pem)

    print("✅ aggregator_private.pem and aggregator_public.pem have been created.")

if __name__ == "__main__":
    generate_keys()
