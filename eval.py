import tensorflow as tf
import pandas as pd
import numpy as np
import os
import requests
import io
import json
import sys
from web3 import Web3
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

# --- 1. CONFIGURATION ---
G_MIN, G_MAX = 0.0, 1000000.0 
NOISE_COLUMNS = ['Flow ID', 'Source IP', 'Source Port', 'Destination IP', 'Timestamp']
PRIVATE_KEY_PATH = "credentials/aggregator_private.pem"

# Blockchain Setup
RPC_URL = os.getenv("RPC_URL")
w3 = Web3(Web3.HTTPProvider(RPC_URL))
with open("credentials/deployed_address.txt", "r") as f:
    CONTRACT_ADDRESS = f.read().strip()
with open("credentials/contract_abi.json", "r") as f:
    ABI = json.load(f)
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

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

def decrypt_model_from_ipfs(cid):
    print(f"📥 Pulling Model from IPFS CID: {cid}")
    res = requests.get(f"https://gateway.pinata.cloud/ipfs/{cid}")
    if res.status_code != 200:
        raise Exception(f"Failed to download from IPFS. Status: {res.status_code}")
    data = res.content

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

def preprocess_test_data(file_path):
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    df = df.drop(columns=[c for c in NOISE_COLUMNS if c in df.columns], errors='ignore')
    X_df = df.select_dtypes(include=[np.number]).drop(columns=['Label'], errors='ignore')
    X_raw = X_df.values[:, :72] if X_df.shape[1] >= 72 else np.pad(X_df.values, ((0,0), (0, 72-X_df.shape[1])))
    X = (X_raw - G_MIN) / (G_MAX - G_MIN + 1e-7)
    X = np.clip(X, 0, 1).reshape(-1, 9, 8, 1).astype('float32')
    y = df['Label'].apply(lambda x: 0 if str(x).upper() == 'BENIGN' else 1).values.astype('float32')
    return X, y

def run_evaluation(round_num):
    print(f"\n🚀 --- EVALUATING GLOBAL MODEL FOR ROUND {round_num} ---")
    
    # 1. Fetch CID from Blockchain
    try:
        model_cid = contract.functions.globalModels(round_num).call()
        if not model_cid:
            print(f"⚠️ No model found on blockchain for Round {round_num}.")
            return
    except Exception as e:
        print(f"❌ Blockchain Error: {e}")
        return

    # 2. Download and Decrypt
    weights = decrypt_model_from_ipfs(model_cid)
    
    # 3. Load Data
    X_test, y_test = preprocess_test_data("global_test.csv")
    
    # 4. Build Model & Evaluate
    model = build_global_model()
    model.set_weights(weights)
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    
    print(f"🧪 Running inference on Round {round_num} weights...")
    loss, accuracy = model.evaluate(X_test, y_test, verbose=0)
    
    # Predictions for CM and Report
    y_pred_prob = model.predict(X_test, verbose=0)
    y_pred = (y_pred_prob > 0.5).astype(int).flatten()

    # 5. Confusion Matrix Calculation
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

    # --- PRINTING RESULTS ---
    print("\n" + "="*40)
    print(f"📊 PERFORMANCE REPORT: ROUND {round_num}")
    print("="*40)
    print(f"🔹 LOSS:     {loss:.6f}")
    print(f"🔹 ACCURACY: {accuracy*100:.2f}%")
    print("-" * 40)
    print("📝 CLASSIFICATION REPORT:")
    print(classification_report(y_test, y_pred, target_names=['Benign', 'Attack']))
    print("-" * 40)
    print("📉 CONFUSION MATRIX DETAILS:")
    print(f"✅ True Negatives (TN) [Benign correctly ID'd]: {tn}")
    print(f"❌ False Positives (FP) [Benign mistaken for Attack]: {fp}")
    print(f"❌ False Negatives (FN) [Attack missed]: {fn}")
    print(f"✅ True Positives (TP) [Attack correctly ID'd]: {tp}")
    print("="*40)

    # 6. Save to file
    output_file = f"eval_round_{round_num}_results.txt"
    with open(output_file, "w") as f:
        f.write(f"Round: {round_num}\nCID: {model_cid}\n")
        f.write(f"Loss: {loss:.6f}\nAccuracy: {accuracy*100:.4f}%\n\n")
        f.write("Confusion Matrix:\n")
        f.write(f"TN: {tn}, FP: {fp}, FN: {fn}, TP: {tp}\n\n")
        f.write(classification_report(y_test, y_pred, target_names=['Benign', 'Attack']))
    print(f"💾 Results saved to {output_file}")

if __name__ == "__main__":
    # You can change the round number here or pass it via terminal
    target_round = 5 # Set this to 1 for Genesis, 2 for first aggregation, etc.
    
    if len(sys.argv) > 1:
        target_round = int(sys.argv[1])
        
    run_evaluation(target_round)