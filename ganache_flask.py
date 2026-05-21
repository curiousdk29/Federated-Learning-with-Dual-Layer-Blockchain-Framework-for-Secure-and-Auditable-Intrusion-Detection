import io
import time
import json
import requests
import numpy as np
import tensorflow as tf
from flask import Flask, request, jsonify
from web3 import Web3
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet
from collections import deque
import threading



app = Flask(__name__)
from flask_cors import CORS
CORS(app)

_sample_queue = deque()
_queue_lock = threading.Lock()
# --- 1. CONFIGURATION ---
PRIVATE_KEY_PATH = "credentials/aggregator_private.pem"
GLOBAL_MODEL_CID = "0x5b1869D9A4C187F2EAa108f3062412ecf0526b24"
G_MIN, G_MAX = 0.0, 1000000.0

# --- 2. BLOCKCHAIN CONFIGURATION (GANACHE) ---
GANACHE_URL = "http://127.0.0.1:8545" 
# REPLACE THIS with the address you get after deploying in Remix/Truffle
CONTRACT_ADDRESS = "0xe78A0F7E598Cc8b0Bb87894B0F60dD2a88d6a8Ab"
CONTRACT_ABI = [
	{
		"inputs": [],
		"stateMutability": "nonpayable",
		"type": "constructor"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": False,
				"internalType": "string",
				"name": "id",
				"type": "string"
			},
			{
				"indexed": False,
				"internalType": "string",
				"name": "severity",
				"type": "string"
			}
		],
		"name": "AlertLogged",
		"type": "event"
	},
	{
		"inputs": [
			{
				"internalType": "string",
				"name": "_id",
				"type": "string"
			},
			{
				"internalType": "string",
				"name": "_model",
				"type": "string"
			},
			{
				"internalType": "string",
				"name": "_severity",
				"type": "string"
			},
			{
				"internalType": "uint256",
				"name": "_timestamp",
				"type": "uint256"
			},
			{
				"internalType": "string",
				"name": "_metadata",
				"type": "string"
			}
		],
		"name": "logAlert",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "uint256",
				"name": "targetIndex",
				"type": "uint256"
			}
		],
		"name": "modifyAlert",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": False,
				"internalType": "address",
				"name": "attacker",
				"type": "address"
			},
			{
				"indexed": False,
				"internalType": "uint256",
				"name": "targetIndex",
				"type": "uint256"
			},
			{
				"indexed": False,
				"internalType": "uint256",
				"name": "attemptTime",
				"type": "uint256"
			}
		],
		"name": "TamperAttemptRejected",
		"type": "event"
	},
	{
		"inputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"name": "alerts",
		"outputs": [
			{
				"internalType": "string",
				"name": "id",
				"type": "string"
			},
			{
				"internalType": "string",
				"name": "model",
				"type": "string"
			},
			{
				"internalType": "string",
				"name": "severity",
				"type": "string"
			},
			{
				"internalType": "uint256",
				"name": "timestamp",
				"type": "uint256"
			},
			{
				"internalType": "string",
				"name": "metadata",
				"type": "string"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "getAlertCount",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "owner",
		"outputs": [
			{
				"internalType": "address",
				"name": "",
				"type": "address"
			}
		],
		"stateMutability": "view",
		"type": "function"
	}
]

# Initialize Web3 & Contract
w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

if w3.is_connected():
    print(f"🔗 Connected to Ganache at {GANACHE_URL}")
    print(f"💰 Account 0 Balance: {w3.from_wei(w3.eth.get_balance(w3.eth.accounts[0]), 'ether')} ETH")
else:
    print("❌ Failed to connect to Ganache!")

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
print(f"📜 Smart Contract bound at {CONTRACT_ADDRESS}")
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)


# Add this mapping near the top of your file, after G_MIN, G_MAX
SEVERITY_MAP = {
    "DDOS":                      "CRITICAL",
    "DOS HULK":                  "CRITICAL",
    "DOS GOLDENEYE":             "HIGH",
    "DOS SLOWLORIS":             "HIGH",
    "DOS SLOWHTTPTEST":          "HIGH",
    "BOT":                       "CRITICAL",
    "INFILTRATION":              "CRITICAL",
    "HEARTBLEED":                "CRITICAL",
    "FTP-PATATOR":               "MEDIUM",
    "SSH-PATATOR":               "MEDIUM",
    "PORTSCAN":                  "LOW",
    "WEB ATTACK - BRUTE FORCE":  "MEDIUM",
    "WEB ATTACK - SQL INJECTION":"HIGH",
    "WEB ATTACK - XSS":          "MEDIUM",
}
'''
# --- 3. DECRYPTION & LOADING ---
def load_encrypted_model(cid):
    print(f"📥 Fetching Global Model from IPFS: {cid}")
    res = requests.get(f"https://gateway.pinata.cloud/ipfs/{cid}")
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
    weights_bytes = cipher_suite.decrypt(enc_weights)
    weights = np.load(io.BytesIO(weights_bytes), allow_pickle=True)

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
    model.set_weights(weights)
    return model
'''
print("🚀 Initializing IDS Server...")
ids_model = tf.keras.models.load_model("final_ids_model_2.h5")

# --- 4. DETECTION ENDPOINT ---
@app.route('/predict', methods=['POST'])
def predict():
    attack_name = request.json.get('attack_name', 'UNKNOWN').upper()
    severity = SEVERITY_MAP.get(attack_name, 'HIGH')
    try:
        data = request.json['features'] # Expecting a list of 72 features

        # Preprocessing (Scale & Reshape)
        X = np.array(data).astype('float32')
        X = (X - G_MIN) / (G_MAX - G_MIN + 1e-7)
        X = np.clip(X, 0, 1).reshape(-1, 9, 8, 1)

        # Inference
        prediction = ids_model(X,training=False)
        prob = float(prediction[0][0])
        is_attack = prob > 0.5
        confidence = prob if is_attack else 1 - prob

        blockchain_tx = None

        # --- BLOCKCHAIN LOGGING ---
        if is_attack:
            try:
                # Log metadata to Ganache
                tx_hash = contract.functions.logAlert(
                    f"ID-{int(time.time())}", 
                    "CNN-v2.19", 
                    severity, 
                    int(time.time()), 
                    f"Prob: {prob:.4f} | {attack_name}"
                ).transact({'from': w3.eth.accounts[0]})

                # Wait for confirmation
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                blockchain_tx = receipt.transactionHash.hex()
            except Exception as bce:
                print(f"⚠️ Blockchain Logging Failed: {bce}")

        return jsonify({
            "status": "success",
            "result": "ATTACK DETECTED" if is_attack else "BENIGN TRAFFIC",
            "confidence": f"{confidence:.2%}",
            "severity": severity if is_attack else "NONE",
            "threat_score": prob,
            "blockchain_ref": blockchain_tx
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# Add these routes to your ganache_flask.py
# Also add: from flask import Flask, request, jsonify (already imported)

@app.route('/get_alert/<int:index>', methods=['GET'])
def get_alert(index):
    """Fetch a logged alert directly from blockchain by index"""
    try:
        count = contract.functions.getAlertCount().call()
        if index >= count:
            return jsonify({"status": "error", "message": f"Index {index} out of range. Only {count} alerts exist."}), 404

        alert = contract.functions.alerts(index).call()
        tx_filter = w3.eth.filter({
            'address': CONTRACT_ADDRESS,
            'fromBlock': 0,
            'toBlock': 'latest'
        })
        
        # Get block info for this alert to show block hash
        logs = w3.eth.get_logs({
            'address': CONTRACT_ADDRESS,
            'fromBlock': 0,
            'toBlock': 'latest'
        })
        
        block_hash = None
        block_number = None
        if index < len(logs):
            block_number = logs[index]['blockNumber']
            block = w3.eth.get_block(block_number)
            block_hash = block['hash'].hex()

        return jsonify({
            "status": "success",
            "index": index,
            "alert": {
                "id": alert[0],
                "model": alert[1],
                "severity": alert[2],
                "timestamp": alert[3],
                "metadata": alert[4]
            },
            "block_number": block_number,
            "block_hash": block_hash,
            "total_alerts": count
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/tamper_attempt', methods=['POST'])
def tamper_attempt():
    """
    Simulates a real attacker trying to overwrite a logged alert.
    - Uses accounts[1] (unauthorized) to call logAlert → gets REVERTED by onlyOwner
    - Captures raw Web3 revert reason (straight from Ganache EVM)
    - Fetches failed tx receipt to show status=0 (Ganache's own failure flag)
    - Verifies original record is byte-identical and alert count is unchanged
    """
    try:
        data = request.json
        target_index  = data.get('target_index', 0)
        tampered_id   = data.get('tampered_id', 'TAMPERED')
        tampered_sev  = data.get('tampered_severity', 'LOW')
        tampered_meta = data.get('tampered_metadata', 'MODIFIED DATA')

        # ── Authorized deployer vs attacker ──────────────────────────────────
        authorized_account = w3.eth.accounts[0]   # Flask IDS backend
        attacker_account   = w3.eth.accounts[1]   # Simulated attacker

        # ── Step 1: Snapshot state BEFORE tamper attempt ─────────────────────
        count_before = contract.functions.getAlertCount().call()

        if target_index >= count_before:
            return jsonify({
                "status": "error",
                "message": f"Index {target_index} does not exist. Only {count_before} alerts on chain."
            }), 404

        orig = contract.functions.alerts(target_index).call()
        original_data = {
            "id":        orig[0],
            "model":     orig[1],
            "severity":  orig[2],
            "timestamp": orig[3],
            "metadata":  orig[4]
        }

        # ── Step 2: Attacker tries logAlert → hits onlyOwner → REVERT ────────
        tamper_rejected   = False
        raw_revert_reason = None
        failed_tx_hash    = None
        failed_tx_receipt = None

        try:
            # Estimate gas first — this triggers the revert check before broadcast
            contract.functions.logAlert(
                tampered_id,
                "TAMPER-ATTEMPT",
                tampered_sev,
                int(time.time()),
                tampered_meta
            ).call({'from': attacker_account})   # .call() lets us capture revert msg cleanly

        except Exception as call_err:
            raw_revert_reason = str(call_err)
            tamper_rejected   = True

        # If .call() didn't revert (shouldn't happen after onlyOwner fix),
        # try actual transact so we still get a receipt with status=0
        if not tamper_rejected:
            try:
                tx_hash = contract.functions.logAlert(
                    tampered_id, "TAMPER-ATTEMPT", tampered_sev,
                    int(time.time()), tampered_meta
                ).transact({'from': attacker_account})
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
                failed_tx_hash = tx_hash.hex()
                failed_tx_receipt = {
                    "transaction_hash": failed_tx_hash,
                    "status":           receipt['status'],       # 0 = FAILED by Ganache
                    "block_number":     receipt['blockNumber'],
                    "block_hash":       receipt['blockHash'].hex(),
                    "gas_used":         receipt['gasUsed'],
                    "from":             receipt['from'],
                    "to":               receipt['to'],
                }
                if receipt['status'] == 0:
                    tamper_rejected   = True
                    raw_revert_reason = "Transaction mined but EVM status=0 (reverted)"
            except Exception as tx_err:
                raw_revert_reason = str(tx_err)
                tamper_rejected   = True

        # ── Step 3: Snapshot state AFTER tamper attempt ──────────────────────
        count_after = contract.functions.getAlertCount().call()
        post = contract.functions.alerts(target_index).call()
        post_tamper_data = {
            "id":        post[0],
            "model":     post[1],
            "severity":  post[2],
            "timestamp": post[3],
            "metadata":  post[4]
        }

        # ── Step 4: Integrity checks ──────────────────────────────────────────
        is_immutable    = (original_data == post_tamper_data)
        count_unchanged = (count_before  == count_after)

        # Clean up revert reason — strip web3 noise, keep just the core message
        clean_revert = raw_revert_reason or ""
        for prefix in ["execution reverted: ", "ContractLogicError: ", "({'message': '"]:
            if prefix in clean_revert:
                clean_revert = clean_revert.split(prefix, 1)[-1].strip("'}) ")
                break

        # Determine overall verdict
        if tamper_rejected and is_immutable and count_unchanged:
            verdict = "IMMUTABILITY VERIFIED — Tamper transaction reverted on-chain. Original record unchanged."
        elif is_immutable and count_unchanged:
            verdict = "APPEND-ONLY VERIFIED — Original record untouched (no onlyOwner guard active)."
        else:
            verdict = "WARNING: Unexpected state change detected. Review contract permissions."

        return jsonify({
            "status":               "success",

            # Who did what
            "authorized_account":   authorized_account,
            "attacker_account":     attacker_account,

            # Tamper outcome
            "tamper_rejected":      tamper_rejected,
            "raw_revert_reason":    raw_revert_reason,     # Full Web3/EVM string
            "clean_revert_reason":  clean_revert,          # Human-readable core message
            "failed_tx_receipt":    failed_tx_receipt,     # None if .call() caught it

            # Data comparison
            "target_index":         target_index,
            "original_data":        original_data,
            "post_tamper_data":     post_tamper_data,
            "is_immutable":         is_immutable,

            # Count comparison (proves nothing was appended)
            "count_before":         count_before,
            "count_after":          count_after,
            "count_unchanged":      count_unchanged,

            "verdict":              verdict,
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/get_all_alerts', methods=['GET'])
def get_all_alerts():
    """Return all logged alerts from blockchain"""
    try:
        count = contract.functions.getAlertCount().call()
        alerts = []
        for i in range(count):
            a = contract.functions.alerts(i).call()
            alerts.append({
                "index": i,
                "id": a[0],
                "model": a[1],
                "severity": a[2],
                "timestamp": a[3],
                "metadata": a[4]
            })
        return jsonify({"status": "success", "count": count, "alerts": alerts})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/push_sample', methods=['POST'])
def push_sample():
    """
    Called by the remote device (other laptop) to send a sample to this server.
    Expected JSON body:
        { "features": [<72 floats>], "attack_name": "DDOS" }
    """
    try:
        data = request.json
        if not data or 'features' not in data:
            return jsonify({"status": "error", "message": "Missing 'features' field"}), 400
        if len(data['features']) != 72:
            return jsonify({"status": "error", "message": f"Expected 72 features, got {len(data['features'])}"}), 400

        sample = {
            "features":    data['features'],
            "attack_name": data.get('attack_name') or data.get('true_label') or 'UNKNOWN'
        }
        with _queue_lock:
            _sample_queue.append(sample)

        return jsonify({"status": "queued", "queue_depth": len(_sample_queue)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/get_pending_samples', methods=['GET'])
def get_pending_samples():
    """
    Polled by the dashboard to drain the queue of samples pushed by the remote device.
    Returns all queued samples and clears the queue atomically.
    """
    with _queue_lock:
        batch = list(_sample_queue)
        _sample_queue.clear()

    return jsonify({"status": "success", "count": len(batch), "samples": batch})

if __name__ == '__main__':
    # Verify Connection before starting
    
       app.run(host='0.0.0.0', port=5001)
