import os
import json
import requests
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()
# --- 1. CONFIGURATION ---
PINATA_JWT = os.getenv("PINATA_JWT")
RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
MY_ADDRESS = os.getenv("MY_ADDRESS")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

with open("credentials/deployed_address.txt", "r") as f:
    CONTRACT_ADDRESS = f.read().strip()
with open("credentials/contract_abi.json", "r") as f:
    ABI = json.load(f)

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

def upload_to_pinata(file_path, node_id, round_num):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {'Authorization': f'Bearer {PINATA_JWT}'}
    
    file_name = f"Node_{node_id}_Round_{round_num}_Update.bin"
    with open(file_path, 'rb') as f:
        files = {'file': (file_name, f)}
        response = requests.post(url, files=files, headers=headers)
        
    if response.status_code == 200:
        cid = response.json()['IpfsHash']
        print(f"✅ Node {node_id} uploaded to IPFS. CID: {cid}")
        return cid
    else:
        print(f"❌ Pinata Upload Failed for Node {node_id}: {response.text}")
        return None

# Replace your transaction building logic with this:
def log_to_blockchain(node_id, metadata):
    nonce = w3.eth.get_transaction_count(MY_ADDRESS)
    metadata_str = json.dumps(metadata)
    
    # 💡 SMART GAS: Get the current market price and add a small 'tip'
    base_fee = w3.eth.gas_price
    priority_tip = w3.to_wei('2', 'gwei') # A small 2 gwei tip makes a huge difference
    total_gas_price = base_fee + priority_tip

    tx = contract.functions.submitUpdate(metadata_str).build_transaction({
        'from': MY_ADDRESS,
        'nonce': nonce,
        'gas': 400000, # Plenty of room
        'gasPrice': total_gas_price,
        'chainId': 11155111
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    # Increase the wait time to 10 minutes to be safe
    print(f"⏳ Waiting for Node {node_id}... Hash: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=600)

def run_submission_loop():
    # Find out what round we are currently in
    current_round = contract.functions.currentRound().call()
    
    for nid in [1]:
        print(f"\n--- 🚀 Submitting Node {nid} ---")
        
        # 1. Paths
        bin_path = f"Node_{nid}/local_update_secure.bin"
        meta_path = f"Node_{nid}/blockchain_metadata.json"
        
        if not os.path.exists(bin_path) or not os.path.exists(meta_path):
            print(f"⚠️ Files missing for Node {nid}. Skipping...")
            continue
            
        # 2. Upload Binary to IPFS
        cid = upload_to_pinata(bin_path, nid, current_round)
        
        if cid:
            # 3. Read existing metadata and add the CID
            with open(meta_path, "r") as f:
                metadata = json.load(f)
            
            metadata["ipfs_cid"] = cid  # Important: Linking the IPFS data to the Blockchain record
            
            # 4. Log the final package to the Blockchain
            log_to_blockchain(nid, metadata)

if __name__ == "__main__":
    run_submission_loop()
