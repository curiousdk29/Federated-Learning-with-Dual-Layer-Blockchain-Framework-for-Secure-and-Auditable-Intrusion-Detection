import io
import numpy as np
import tensorflow as tf
from web3 import Web3
import requests
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet
import json
from dotenv import load_dotenv

load_dotenv()
# --- CONFIGURATION (Match your Aggregator/Node settings) ---
RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY_PATH = "credentials/aggregator_private.pem"
# Path to your CID or fetch it from blockchain
WITH_BLOCKCHAIN = True 

# 1. Reconstruct the Architecture (Must match exactly)
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

def get_latest_model_h5():
    # 2. Get the CID
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    with open("credentials/deployed_address.txt", "r") as f:
        addr = f.read().strip()
    with open("credentials/contract_abi.json", "r") as f:
        abi = json.load(f) # Using standard json works too
    
    contract = w3.eth.contract(address=addr, abi=abi)
    current_round = contract.functions.currentRound().call()
    # We want the completed model from the previous round
    target_round = current_round - 1
    cid = contract.functions.globalModels(target_round).call()
    
    print(f"🌐 Fetching Model from Round {target_round}: {cid}")

    # 3. Download and Decrypt
    response = requests.get(f"https://gateway.pinata.cloud/ipfs/{cid}")
    data = response.content

    with open(PRIVATE_KEY_PATH, "rb") as kf:
        private_key = serialization.load_pem_private_key(kf.read(), password=None)

    key_len = int.from_bytes(data[:4], byteorder='big')
    enc_aes_key = data[4 : 4 + key_len]
    enc_weights_blob = data[4 + key_len :]

    aes_key = private_key.decrypt(
        enc_aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )

    cipher_suite = Fernet(aes_key)
    decrypted_bytes = cipher_suite.decrypt(enc_weights_blob)
    weights = np.load(io.BytesIO(decrypted_bytes), allow_pickle=True)

    # 4. Load into Keras and Save
    model = build_global_model()
    model.set_weights(weights)
    
    # Save as .h5 for your Flask App
    model.save("final_ids_model.h5")
    print("✅ Success! Model saved as 'final_ids_model.h5'")

if __name__ == "__main__":
    get_latest_model_h5()
