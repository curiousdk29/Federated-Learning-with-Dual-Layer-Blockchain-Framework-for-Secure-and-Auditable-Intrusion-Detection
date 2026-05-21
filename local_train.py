import tensorflow as tf
import pandas as pd
import numpy as np
import os
import json
import hashlib
import requests
import io
from web3 import Web3
from sklearn.metrics import classification_report, accuracy_score
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet

os.environ["CUDA_VISIBLE_DEVICES"] = "1"

# --- 1. GLOBAL CONFIG ---
G_MIN, G_MAX = 0.0, 1000000.0 
NOISE_COLUMNS = ['Flow ID', 'Source IP', 'Source Port', 'Destination IP', 'Timestamp']
PUBLIC_KEY_PATH = "credentials/aggregator_public.pem"
PRIVATE_KEY_PATH = "credentials/aggregator_private.pem"

# Blockchain Config
RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

with open("credentials/deployed_address.txt", "r") as f:
    CONTRACT_ADDRESS = f.read().strip()
with open("credentials/contract_abi.json", "r") as f:
    ABI = json.load(f)

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

# --- 2. ARCHITECTURE & HELPERS ---
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
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def decrypt_weights_from_ipfs(cid):
    print(f"📥 Downloading and Decrypting Global Anchor: {cid}")
    response = requests.get(f"https://gateway.pinata.cloud/ipfs/{cid}")
    data = response.content

    with open(PRIVATE_KEY_PATH, "rb") as kf:
        private_key = serialization.load_pem_private_key(kf.read(), password=None)

    key_len = int.from_bytes(data[:4], byteorder='big')
    enc_aes_key = data[4 : 4 + key_len]
    enc_weights = data[4 + key_len :]

    aes_key = private_key.decrypt(
        enc_aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )

    cipher_suite = Fernet(aes_key)
    decrypted_bytes = cipher_suite.decrypt(enc_weights)
    return np.load(io.BytesIO(decrypted_bytes), allow_pickle=True)

def encrypt_local_weights(weights_npy, public_key_path):
    aes_key = Fernet.generate_key()
    cipher_suite = Fernet(aes_key)
    encrypted_weights = cipher_suite.encrypt(weights_npy)

    with open(public_key_path, "rb") as kf:
        public_key = serialization.load_pem_public_key(kf.read())

    enc_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    return len(enc_aes_key).to_bytes(4, byteorder='big') + enc_aes_key + encrypted_weights

def proximal_loss(y_true, y_pred, model, global_trainable_weights, mu=0.01):
    y_true = tf.cast(tf.reshape(y_true, tf.shape(y_pred)), dtype=tf.float32)
    bce = tf.keras.losses.BinaryCrossentropy()
    standard_loss = bce(y_true, y_pred)
    proximal_term = sum(tf.reduce_sum(tf.square(lw - gw)) for lw, gw in zip(model.trainable_weights, global_trainable_weights))
    return standard_loss + (mu / 2) * proximal_term

def preprocess_data(file_path):
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    df = df.drop(columns=[c for c in NOISE_COLUMNS if c in df.columns], errors='ignore')
    X_df = df.select_dtypes(include=[np.number]).drop(columns=['Label'], errors='ignore')
    X_raw = X_df.values[:, :72] if X_df.shape[1] >= 72 else np.pad(X_df.values, ((0,0), (0, 72 - X_df.shape[1])))
    X = (X_raw - G_MIN) / (G_MAX - G_MIN + 1e-7)
    X = np.clip(X, 0, 1).reshape(-1, 9, 8, 1).astype('float32')
    y = df['Label'].apply(lambda x: 0 if str(x).upper() == 'BENIGN' else 1).values.astype('float32')
    return X, y

# --- 3. MAIN TRAINING FUNCTION ---
def run_blockchain_local_training(node_id, mu=0.01):
    # Fetch current round state
    current_round_on_chain = contract.functions.currentRound().call()
    
    # ADJUSTMENT: Pull the model from the PREVIOUS round index
    anchor_round = current_round_on_chain - 1
    if anchor_round < 1: anchor_round = 1 

    print(f"\n--- ⛓️ NODE {node_id} | TRAINING FOR ROUND {current_round_on_chain} ---")
    print(f"📡 Requesting Anchor from Round {anchor_round}...")
    
    # FETCH GLOBAL ANCHOR CID
    anchor_cid = contract.functions.globalModels(anchor_round).call()
    
    if not anchor_cid:
        print(f"❌ Error: No CID found for Round {anchor_round} on blockchain!")
        return

    global_weights = decrypt_weights_from_ipfs(anchor_cid)

    # 4. PREP MODEL & DATA
    X_train, y_train = preprocess_data(f"Node_{node_id}/train.csv")
    X_test, y_test = preprocess_data(f"Node_{node_id}/test.csv")
    
    model = build_global_model()
    model.set_weights(global_weights)
    global_trainable_weights = [tf.constant(w) for w in model.trainable_weights]

    # 5. TRAINING LOOP
    train_dataset = tf.data.Dataset.from_tensor_slices((X_train, y_train)).shuffle(5000).batch(64)
    optimizer = tf.keras.optimizers.Adam(learning_rate=0.0001)

    @tf.function
    def train_step(x_batch, y_batch):
        with tf.GradientTape() as tape:
            predictions = model(x_batch, training=True)
            loss_value = proximal_loss(y_batch, predictions, model, global_trainable_weights, mu)
        grads = tape.gradient(loss_value, model.trainable_weights)
        optimizer.apply_gradients(zip(grads, model.trainable_weights))
        return loss_value

    for epoch in range(5):
        epoch_loss = 0.0
        for x_batch, y_batch in train_dataset:
            epoch_loss += train_step(x_batch, y_batch)
        print(f"Epoch {epoch+1}/5 - Loss: {epoch_loss/len(train_dataset):.4f}")

    # 6. RESULTS & REPORTING
    y_pred_prob = model.predict(X_test, verbose=0)
    y_pred = (y_pred_prob > 0.5).astype(int).flatten()
    acc = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, target_names=['Benign', 'Attack'])
    
    print(report)
    with open(f"Node_{node_id}/round_{current_round_on_chain}_report.txt", "w") as f:
        f.write(report)

    # 7. SECURE FOR BLOCKCHAIN
    local_weights = np.array(model.get_weights(), dtype=object)
    
    buffer = io.BytesIO()
    np.save(buffer, local_weights)
    encrypted_data = encrypt_local_weights(buffer.getvalue(), PUBLIC_KEY_PATH)
    
    file_hash = hashlib.sha256(encrypted_data).hexdigest()
    
    with open(f"Node_{node_id}/local_update_secure.bin", "wb") as f:
        f.write(encrypted_data)

    metadata = {
        "node_id": node_id,
        "round": current_round_on_chain,
        "accuracy": round(acc, 4),
        "sha256_hash": file_hash,
        "sample_count": len(X_train)
    }
    with open(f"Node_{node_id}/blockchain_metadata.json", "w") as f:
        json.dump(metadata, f, indent=4)

    print(f"🏆 Node {node_id} complete. Hash: {file_hash[:10]}")

if __name__ == "__main__":
    for nid in [1]:
        run_blockchain_local_training(nid)
