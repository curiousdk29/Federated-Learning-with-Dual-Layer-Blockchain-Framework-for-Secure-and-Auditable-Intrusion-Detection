import os
import json
import requests
from web3 import Web3

# --- 1. CONFIGURATION ---
PINATA_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySW5mb3JtYXRpb24iOnsiaWQiOiJkNTU4ZjE0My01YTc2LTRjNGYtOGUwYi03YzMyMTIxMTFmOTciLCJlbWFpbCI6ImFkaXRoeWEyOTA2QGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJwaW5fcG9saWN5Ijp7InJlZ2lvbnMiOlt7ImRlc2lyZWRSZXBsaWNhdGlvbkNvdW50IjoxLCJpZCI6IkZSQTEifSx7ImRlc2lyZWRSZXBsaWNhdGlvbkNvdW50IjoxLCJpZCI6Ik5ZQzEifV0sInZlcnNpb24iOjF9LCJtZmFfZW5hYmxlZCI6ZmFsc2UsInN0YXR1cyI6IkFDVElWRSJ9LCJhdXRoZW50aWNhdGlvblR5cGUiOiJzY29wZWRLZXkiLCJzY29wZWRLZXlLZXkiOiI0YTI4MmZkZWFlZmFlOTU4MjA4MCIsInNjb3BlZEtleVNlY3JldCI6ImQ4ZThjMGI5MjlhNjU5ZDhiNjRhMjhiYTlkOTYwOTA2MzQ1OGI1OGQ5OGMxNzk2ZGQ2YjNjNmQxYjM0YjhiOWIiLCJleHAiOjE4MDI0MDk2MzN9.e9s4cNtR3PmkPc0dbJI6IN2n9TVhIzqhUwvEGmULBQM"
RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
PRIVATE_KEY = "0xf65dec826d6bc9e1cb002bc453b246694618f889f8f00942c3a8a842b6fe5b59"
MY_ADDRESS = "0xbfA514c7C631CA73FE52e1962AA4C9C5D593E1AF"

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
