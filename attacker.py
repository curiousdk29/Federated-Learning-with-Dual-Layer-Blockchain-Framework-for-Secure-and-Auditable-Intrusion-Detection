import json
import requests
import time
import statistics
import random

# --- 1. SETTINGS ---
# Ensure this matches the IP of the laptop running the Flask server (Laptop A)
DEFENDER_IP = "localhost"   
PORT = 5001

# IMPORTANT: Using /push_sample so the Dashboard can intercept and display them
FLASK_URL = f"http://{DEFENDER_IP}:{PORT}/push_sample"
TEST_JSON_FILE = "filtered_dataset_new.json"

def run_json_evaluation():
    # Load test cases
    try:
        with open(TEST_JSON_FILE, "r") as f:
            all_test_cases = json.load(f)
        print(f"📂 Total available samples in dataset: {len(all_test_cases)}")
    except FileNotFoundError:
        print(f"❌ Error: {TEST_JSON_FILE} not found. Ensure the JSON file is in the same directory.")
        return

    # =========================================================
    # --- USER CONFIGURATION ---
    # =========================================================
    print("\n" + "="*30)
    print("   TEST CONFIGURATION")
    print("="*30)
    print("Select Sample Mode:")
    print("1. Mixed (50% Attack / 50% Benign)")
    print("2. Attacks Only")
    print("3. Benign Only")
    
    mode = input("\nChoose mode (1/2/3): ").strip()
    
    try:
        max_allowed = len(all_test_cases)
        requested_count = int(input(f"How many samples to send? (max {max_allowed}): "))
        requested_count = min(requested_count, max_allowed)
    except ValueError:
        print("⚠️ Invalid input. Defaulting to 10 samples.")
        requested_count = 10

    # Separate data for filtering
    attacks = [s for s in all_test_cases if s['attack_name'].upper() != 'BENIGN']
    benign = [s for s in all_test_cases if s['attack_name'].upper() == 'BENIGN']

    # Apply Filtering Logic
    if mode == "2":
        test_cases = random.sample(attacks, min(len(attacks), requested_count))
        print(f"🚀 Selected {len(test_cases)} ATTACK samples.")
    elif mode == "3":
        test_cases = random.sample(benign, min(len(benign), requested_count))
        print(f"🚀 Selected {len(test_cases)} BENIGN samples.")
    else:
        # Mixed Mode (50/50 split)
        half = requested_count // 2
        sel_attacks = random.sample(attacks, min(len(attacks), half))
        sel_benign = random.sample(benign, min(len(benign), requested_count - len(sel_attacks)))
        test_cases = sel_attacks + sel_benign
        random.shuffle(test_cases) # Shuffle so it's not all attacks first
        print(f"🚀 Mixed Mode: {len(sel_attacks)} Attacks, {len(sel_benign)} Benign.")

    if not test_cases:
        print("❌ No samples matched your selection criteria.")
        return

    # --- Tracking variables ---
    results_map = {}
    inference_latencies = []
    total_processed = 0

    print(f"\n🧪 Starting Stress Test against: {FLASK_URL}...")
    print("-" * 60)

    for i, entry in enumerate(test_cases):
        features = entry['features']
        actual_attack_name = entry['attack_name']

        try:
            # --- Measure request latency ---
            start_time = time.perf_counter()
            
            # Sending to /push_sample
            resp = requests.post(
                FLASK_URL, 
                json={"features": features, "attack_name": actual_attack_name}, 
                timeout=10
            )
            
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            inference_latencies.append(latency_ms)

            if resp.status_code == 200 or resp.status_code == 201:
                # Per-category tracking
                if actual_attack_name not in results_map:
                    results_map[actual_attack_name] = 0
                results_map[actual_attack_name] += 1
                total_processed += 1
            else:
                print(f"⚠️ Server Error at sample {i}: {resp.text}")

            if (i + 1) % 5 == 0:
                print(f"✅ Queued {i + 1}/{len(test_cases)} samples...")

            # Small sleep to avoid overwhelming the dashboard UI
            time.sleep(0.1)

        except Exception as e:
            print(f"❌ Connection Error at sample {i}: {e}")

    # =========================================================
    # --- FINAL SUMMARY ---
    # =========================================================
    print("\n" + "=" * 55)
    print("  STRESS TEST COMPLETE — SAMPLES QUEUED")
    print("=" * 55)
    print(f"{'Attack Category':<30} | {'Sent Count':>10}")
    print("-" * 55)

    for label, count in sorted(results_map.items()):
        print(f"{label[:30]:<30} | {count:>10}")

    print("-" * 55)
    print(f"{'TOTAL SAMPLES SENT':<30} | {total_processed:>10}")
    
    if inference_latencies:
        avg_lat = statistics.mean(inference_latencies)
        print(f"{'AVG NETWORK LATENCY':<30} | {avg_lat:>7.2f} ms")
    
    print("=" * 55)
    print("👉 Check the IDS Dashboard on Laptop A to see real-time processing.")

if __name__ == "__main__":
    run_json_evaluation()
