import json
import requests
import numpy as np
import io
import hashlib
from web3 import Web3
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet

# --- 1. CONFIGURATION ---
PINATA_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySW5mb3JtYXRpb24iOnsiaWQiOiJkNTU4ZjE0My01YTc2LTRjNGYtOGUwYi03YzMyMTIxMTFmOTciLCJlbWFpbCI6ImFkaXRoeWEyOTA2QGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJwaW5fcG9saWN5Ijp7InJlZ2lvbnMiOlt7ImRlc2lyZWRSZXBsaWNhdGlvbkNvdW50IjoxLCJpZCI6IkZSQTEifSx7ImRlc2lyZWRSZXBsaWNhdGlvbkNvdW50IjoxLCJpZCI6Ik5ZQzEifV0sInZlcnNpb24iOjF9LCJtZmFfZW5hYmxlZCI6ZmFsc2UsInN0YXR1cyI6IkFDVElWRSJ9LCJhdXRoZW50aWNhdGlvblR5cGUiOiJzY29wZWRLZXkiLCJzY29wZWRLZXlLZXkiOiI0YTI4MmZkZWFlZmFlOTU4MjA4MCIsInNjb3BlZEtleVNlY3JldCI6ImQ4ZThjMGI5MjlhNjU5ZDhiNjRhMjhiYTlkOTYwOTA2MzQ1OGI1OGQ5OGMxNzk2ZGQ2YjNjNmQxYjM0YjhiOWIiLCJleHAiOjE4MDI0MDk2MzN9.e9s4cNtR3PmkPc0dbJI6IN2n9TVhIzqhUwvEGmULBQM"
RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
PRIVATE_KEY = "0xf65dec826d6bc9e1cb002bc453b246694618f889f8f00942c3a8a842b6fe5b59"
MY_ADDRESS = "0xbfA514c7C631CA73FE52e1962AA4C9C5D593E1AF"
PUBLIC_KEY_PATH = "credentials/aggregator_public.pem"
PRIVATE_KEY_PATH = "credentials/aggregator_private.pem"

# Blockchain Setup
w3 = Web3(Web3.HTTPProvider(RPC_URL))
with open("credentials/deployed_address.txt", "r") as f:
    CONTRACT_ADDRESS = f.read().strip()
with open("credentials/contract_abi.json", "r") as f:
    ABI = json.load(f)

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

# Sample Counts (Node 3 is the majority contributor)
NODE_SAMPLES = {1: 295485, 2: 138233, 3: 1830876}
TOTAL_SAMPLES = sum(NODE_SAMPLES.values())

# --- 2. SECURITY HELPERS ---
def decrypt_node_data(encrypted_data):
    with open(PRIVATE_KEY_PATH, "rb") as kf:
        private_key = serialization.load_pem_private_key(kf.read(), password=None)

    key_len = int.from_bytes(encrypted_data[:4], byteorder='big')
    enc_aes_key = encrypted_data[4 : 4 + key_len]
    enc_weights = encrypted_data[4 + key_len :]

    aes_key = private_key.decrypt(
        enc_aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    cipher_suite = Fernet(aes_key)
    decrypted_bytes = cipher_suite.decrypt(enc_weights)
    return np.load(io.BytesIO(decrypted_bytes), allow_pickle=True)

def encrypt_global_model(weights_list):
    buffer = io.BytesIO()
    np.save(buffer, np.array(weights_list, dtype=object))
    weight_bytes = buffer.getvalue()

    aes_key = Fernet.generate_key()
    cipher_suite = Fernet(aes_key)
    encrypted_weights = cipher_suite.encrypt(weight_bytes)

    with open(PUBLIC_KEY_PATH, "rb") as kf:
        public_key = serialization.load_pem_public_key(kf.read())

    enc_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    return len(enc_aes_key).to_bytes(4, byteorder='big') + enc_aes_key + encrypted_weights

# --- 3. MASTER CYCLE ---
def run_full_aggregator_cycle():
    current_round = contract.functions.currentRound().call()
    update_count = contract.functions.getUpdateCount(current_round).call()

    print(f"🌐 Aggregator: Processing Round {current_round} | Updates: {update_count}/3")

    if update_count < 3:
        print("🛑 Waiting for more node updates...")
        return

    # A. PULL & DECRYPT UPDATES
    all_node_weights = []
    for i in range(update_count):
        update = contract.functions.roundHistory(current_round, i).call()
        meta = json.loads(update[1])
        
        print(f"📥 Downloading Node {meta['node_id']}...")
        res = requests.get(f"https://gateway.pinata.cloud/ipfs/{meta['ipfs_cid']}")
        
        # Integrity Check
        if hashlib.sha256(res.content).hexdigest() != meta['sha256_hash']:
            print(f"❌ Hash Mismatch for Node {meta['node_id']}!")
            continue
            
        weights = decrypt_node_data(res.content)
        all_node_weights.append((meta['node_id'], weights))

    # B. WEIGHTED AVERAGING (FedProx Logic)
    print("🧮 Calculating Weighted Global Model...")
    new_global_weights = []
    num_layers = len(all_node_weights[0][1])

    for layer_idx in range(num_layers):
        layer_weighted_sum = sum(
            node_w[layer_idx] * (NODE_SAMPLES[node_id] / TOTAL_SAMPLES)
            for node_id, node_w in all_node_weights
        )
        new_global_weights.append(layer_weighted_sum)

    # C. ENCRYPT & UPLOAD
    # C. ENCRYPT & UPLOAD (Updated with Debugging)
    print("🔐 Encrypting and Uploading Global Model...")
    encrypted_global = encrypt_global_model(new_global_weights)
    
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {'Authorization': f'Bearer {PINATA_JWT}'}
    
    # We use a proper filename to help Pinata process the multipart/form-data
    files = {'file': (f"global_model_r{current_round}.bin", encrypted_global)}
    
    response = requests.post(url, files=files, headers=headers)
    
    # CHECK IF SUCCESSFUL
    if response.status_code != 200:
        print(f"❌ PINATA ERROR (Status {response.status_code}):")
        print(response.text) # This will tell you exactly what's wrong (e.g., "Unauthorized")
        return

    # If successful, parse the CID
    response_data = response.json()
    new_cid = response_data['IpfsHash']
    print(f"✅ Global Model IPFS CID: {new_cid}")

    # D. BLOCKCHAIN BROADCAST
    print("⛓️ Broadcasting to Sepolia...")
    nonce = w3.eth.get_transaction_count(MY_ADDRESS)
    gas_price = int(w3.eth.gas_price * 1.2) # 20% tip for speed

    tx = contract.functions.setGlobalModel(new_cid).build_transaction({
        'from': MY_ADDRESS,
        'nonce': nonce,
        'gas': 400000,
        'gasPrice': gas_price,
        'chainId': 11155111
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    print(f"⏳ Finalizing Round {current_round}... Hash: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    
    print(f"🏁 ROUND {current_round} COMPLETE. Round {current_round + 1} is now open for nodes!")

if __name__ == "__main__":
    run_full_aggregator_cycle()
