import json
from web3 import Web3

# 1. SETUP
RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
PRIVATE_KEY = "0xf65dec826d6bc9e1cb002bc453b246694618f889f8f00942c3a8a842b6fe5b59"
MY_ADDRESS = "0xbfA514c7C631CA73FE52e1962AA4C9C5D593E1AF"

# 2. LOAD DEPLOYED INFO
with open("credentials/deployed_address.txt", "r") as f:
    CONTRACT_ADDRESS = f.read().strip()

with open("credentials/contract_abi.json", "r") as f:
    ABI = json.load(f)

w3 = Web3(Web3.HTTPProvider(RPC_URL))
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

def initialize_round_1(genesis_cid):
    print(f"📡 Initializing Round 1 on Contract {CONTRACT_ADDRESS}...")
    nonce = w3.eth.get_transaction_count(MY_ADDRESS)
    
    # Call the 'setGlobalModel' function we added to the Solidity code
    tx = contract.functions.setGlobalModel(genesis_cid).build_transaction({
        'from': MY_ADDRESS,
        'nonce': nonce,
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
        'chainId': 11155111 # Sepolia
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    print(f"⏳ Waiting for initialization... Hash: {tx_hash.hex()}")
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"🏁 ROUND 1 IS NOW LIVE! Nodes can now pull CID: {genesis_cid}")

if __name__ == "__main__":
    # Put the CID you got from genesis_secure.py here
    GENESIS_CID = "QmdcoY7rP6v8q9nzcWVXV83ogVvnPtTVJpzDN9R4Kd1Va1" 
    initialize_round_1(GENESIS_CID)
