from eth_account import Account
import secrets

def create_wallet():
    # 1. Generate a random 32-byte private key
    priv = secrets.token_hex(32)
    private_key = "0x" + priv
    
    # 2. Derive the public address from that private key
    acct = Account.from_key(private_key)
    
    print("⚠️  SAVE BUT DO NOT SHARE THIS PRIVATE KEY:")
    print(f"PRIVATE_KEY: {private_key}")
    print("-" * 50)
    print(f"PUBLIC_ADDRESS: {acct.address}")
    print("-" * 50)
    print("📝 Copy these into your scripts now.")

if __name__ == "__main__":
    create_wallet()
