import tensorflow as tf
import numpy as np
import io
import os
import requests
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet

from dotenv import load_dotenv

load_dotenv()

os.environ["CUDA_VISIBLE_DEVICES"] = "1"
# --- 1. CONFIGURATION ---
# Use the JWT from your Pinata account
PINATA_JWT = os.getenv("PINATA_JWT")
PUBLIC_KEY_PATH = "credentials/aggregator_public.pem"

# --- 2. ARCHITECTURE ---
def build_global_model():
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(9, 8, 1)),
        tf.keras.layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
        tf.keras.layers.BatchNormalization(), 
        tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])
    return model

# --- 3. ENCRYPTION & UPLOAD ---
def encrypt_and_upload_genesis():
    model = build_global_model()
    weights = model.get_weights()
    
    # Convert weights to bytes
    buffer = io.BytesIO()
    np.save(buffer, np.array(weights, dtype=object))
    weight_bytes = buffer.getvalue()

    # Generate AES key and encrypt
    aes_key = Fernet.generate_key()
    cipher_suite = Fernet(aes_key)
    encrypted_weights = cipher_suite.encrypt(weight_bytes)

    # Encrypt AES key with RSA Public Key
    with open(PUBLIC_KEY_PATH, "rb") as kf:
        public_key = serialization.load_pem_public_key(kf.read())

    encrypted_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    # Package: [4-byte key length | Encrypted Key | Encrypted Weights]
    final_data = len(encrypted_aes_key).to_bytes(4, byteorder='big') + encrypted_aes_key + encrypted_weights
    
    # Upload to Pinata
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {'Authorization': f'Bearer {PINATA_JWT}'}
    files = {'file': ('genesis_model_r0.bin', final_data)}
    
    print("📤 Sending encrypted genesis to IPFS...")
    response = requests.post(url, files=files, headers=headers)
    
    if response.status_code == 200:
        cid = response.json()['IpfsHash']
        print(f"\n🌟 SUCCESS! Genesis CID: {cid}")
        return cid
    else:
        print(f"❌ Upload Failed: {response.text}")
        return None

if __name__ == "__main__":
    encrypt_and_upload_genesis()
