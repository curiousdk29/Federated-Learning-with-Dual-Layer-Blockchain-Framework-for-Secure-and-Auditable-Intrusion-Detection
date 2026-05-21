import json
from web3 import Web3

# 1. SETUP
RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
PRIVATE_KEY = "0xf65dec826d6bc9e1cb002bc453b246694618f889f8f00942c3a8a842b6fe5b59"
MY_ADDRESS = "0xbfA514c7C631CA73FE52e1962AA4C9C5D593E1AF"

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# 2. READ FROM FILES (The way you want it)
with open("credentials/contract_abi.json", "r") as f:
    ABI = json.load(f)

with open("credentials/bytecode.txt", "r") as f:
    # We strip() to remove any accidental spaces or newlines
    BYTECODE = f.read().strip()

# 3. INITIALIZE & DEPLOY
contract_factory = w3.eth.contract(abi=ABI, bytecode=BYTECODE)

print("🛰️ Deploying from file data...")
nonce = w3.eth.get_transaction_count(MY_ADDRESS)

deploy_tx = contract_factory.constructor().build_transaction({
    'from': MY_ADDRESS,
    'nonce': nonce,
    'gas': 2000000,
    'gasPrice': w3.eth.gas_price,
    'chainId': 11155111
})

signed_tx = w3.eth.account.sign_transaction(deploy_tx, private_key=PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

print(f"⏳ Waiting... Hash: {tx_hash.hex()}")
# The correct way for Web3.py v6+
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

print(f"✅ DEPLOYED! Address: {tx_receipt.contractAddress}")

# Save the address for your other scripts to find
with open("credentials/deployed_address.txt", "w") as f:
    f.write(tx_receipt.contractAddress)
