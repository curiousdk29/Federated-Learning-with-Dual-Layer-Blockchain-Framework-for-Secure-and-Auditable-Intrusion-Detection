import json
import requests
import time
import statistics

# --- 1. SETTINGS ---
FLASK_URL = "http://localhost:5001/predict"
TEST_JSON_FILE = "filtered_200_samples.json"

def run_json_evaluation():
    # Load test cases
    try:
        with open(TEST_JSON_FILE, "r") as f:
            test_cases = json.load(f)
        print(f"📂 Loaded {len(test_cases)} test cases from {TEST_JSON_FILE}")
    except FileNotFoundError:
        print(f"❌ Error: {TEST_JSON_FILE} not found. Run your generator script first.")
        return

    # --- Tracking variables ---
    results_map = {}

    # Confusion matrix counters (binary: attack vs benign)
    TP = 0  # Predicted ATTACK, actual ATTACK
    TN = 0  # Predicted BENIGN, actual BENIGN
    FP = 0  # Predicted ATTACK, actual BENIGN
    FN = 0  # Predicted BENIGN, actual ATTACK

    # Latency tracking
    inference_latencies = []       # Time for each request round-trip (ms)
    end_to_end_latencies = []      # Same as inference here (no BC in client timing)

    overall_correct = 0
    total_processed = 0

    print(f"🧪 Starting Stress Test against: {FLASK_URL}...")
    print("-" * 60)

    for i, entry in enumerate(test_cases):
        features = entry['features']
        actual_attack_name = entry['attack_name']
        is_benign_ground_truth = (actual_attack_name.upper() == 'BENIGN')

        try:
            # --- Measure inference latency ---
            start_time = time.perf_counter()
            resp = requests.post(FLASK_URL, json={"features": features}, timeout=10)
            end_time = time.perf_counter()

            latency_ms = (end_time - start_time) * 1000
            inference_latencies.append(latency_ms)
            end_to_end_latencies.append(latency_ms)

            if resp.status_code != 200:
                print(f"⚠️ Server Error at sample {i}: {resp.text}")
                continue

            resp_json = resp.json()
            prediction = resp_json.get('result')  # "ATTACK DETECTED" or "BENIGN TRAFFIC"

            # --- Update confusion matrix ---
            if is_benign_ground_truth:
                if prediction == "BENIGN TRAFFIC":
                    TN += 1
                else:
                    FP += 1
            else:
                if prediction == "ATTACK DETECTED":
                    TP += 1
                else:
                    FN += 1

            # --- Per-category tracking ---
            is_correct = (is_benign_ground_truth and prediction == "BENIGN TRAFFIC") or \
                         (not is_benign_ground_truth and prediction == "ATTACK DETECTED")

            if actual_attack_name not in results_map:
                results_map[actual_attack_name] = {"correct": 0, "total": 0}

            results_map[actual_attack_name]["total"] += 1
            if is_correct:
                results_map[actual_attack_name]["correct"] += 1
                overall_correct += 1

            total_processed += 1

            if (i + 1) % 20 == 0:
                print(f"✅ Processed {i + 1}/{len(test_cases)} samples...")

        except Exception as e:
            print(f"❌ Connection Error at sample {i}: {e}")

    # =========================================================
    # --- COMPUTE METRICS ---
    # =========================================================

    # Core classification metrics
    TPR = (TP / (TP + FN) * 100) if (TP + FN) > 0 else 0.0   # Recall / True Positive Rate
    FPR = (FP / (FP + TN) * 100) if (FP + TN) > 0 else 0.0   # False Positive Rate
    TNR = (TN / (TN + FP) * 100) if (TN + FP) > 0 else 0.0   # Specificity
    FNR = (FN / (FN + TP) * 100) if (FN + TP) > 0 else 0.0   # Miss Rate

    PRECISION = (TP / (TP + FP) * 100) if (TP + FP) > 0 else 0.0
    RECALL    = TPR
    F1        = (2 * PRECISION * RECALL / (PRECISION + RECALL)) if (PRECISION + RECALL) > 0 else 0.0
    ACCURACY  = ((TP + TN) / total_processed * 100) if total_processed > 0 else 0.0

    # Latency metrics (ms)
    if inference_latencies:
        lat_avg = statistics.mean(inference_latencies)
        lat_min = min(inference_latencies)
        lat_max = max(inference_latencies)
        lat_std = statistics.stdev(inference_latencies) if len(inference_latencies) > 1 else 0.0
    else:
        lat_avg = lat_min = lat_max = lat_std = 0.0

    # Blockchain write latency from paper (permissioned network — fixed reference)
    BC_WRITE_LAT_MIN = 1200   # ms
    BC_WRITE_LAT_MAX = 1800   # ms
    BC_WRITE_LAT_AVG = 1500   # ms (midpoint)

    # End-to-end = AI inference + blockchain write (paper Table 2: 130–210 ms avg 170 ms)
    E2E_AVG = lat_avg + BC_WRITE_LAT_AVG
    E2E_MIN = lat_min + BC_WRITE_LAT_MIN
    E2E_MAX = lat_max + BC_WRITE_LAT_MAX

    # =========================================================
    # --- DISPLAY: TABLE 1 — Per-Category Accuracy ---
    # =========================================================

    print("\n" + "=" * 65)
    print("  RESULTS TABLE 1 — Detection Accuracy by Attack Category")
    print("=" * 65)
    print(f"{'Attack Category':<28} | {'Correct':>7} | {'Total':>5} | {'Accuracy':>9} | {'Status'}")
    print("-" * 65)

    for label, stats in sorted(results_map.items()):
        acc = (stats['correct'] / stats['total']) * 100
        status = "✅ PASS" if acc >= 80 else "⚠️  LOW"
        display_label = label[:27]
        print(f"{display_label:<28} | {stats['correct']:>7} | {stats['total']:>5} | {acc:>8.2f}% | {status}")

    print("-" * 65)
    final_acc = (overall_correct / total_processed * 100) if total_processed > 0 else 0
    print(f"{'OVERALL':<28} | {overall_correct:>7} | {total_processed:>5} | {final_acc:>8.2f}%")
    print("=" * 65)

    # =========================================================
    # --- DISPLAY: TABLE 2 — Performance Metrics (Paper Style) ---
    # =========================================================

    print("\n")
    print("=" * 55)
    print("  RESULTS TABLE 2 — System Performance Metrics")
    print("  (Mirrors paper Table 2 — AI Inference Side)")
    print("=" * 55)
    print(f"  {'Metric':<35} {'Value':>15}")
    print("-" * 55)

    # Classification metrics
    print(f"  {'True Positive Rate (Recall / TPR)':<35} {TPR:>14.1f}%")
    print(f"  {'False Positive Rate (FPR)':<35} {FPR:>14.1f}%")
    print(f"  {'True Negative Rate (Specificity)':<35} {TNR:>14.1f}%")
    print(f"  {'False Negative Rate (Miss Rate)':<35} {FNR:>14.1f}%")
    print(f"  {'Precision':<35} {PRECISION:>14.1f}%")
    print(f"  {'F1 Score':<35} {F1:>14.1f}%")
    print(f"  {'Overall Accuracy':<35} {ACCURACY:>14.1f}%")
    print("-" * 55)

    # Confusion matrix counts
    print(f"  {'True Positives (TP)':<35} {TP:>15}")
    print(f"  {'True Negatives (TN)':<35} {TN:>15}")
    print(f"  {'False Positives (FP)':<35} {FP:>15}")
    print(f"  {'False Negatives (FN)':<35} {FN:>15}")
    print("-" * 55)

    # Latency metrics
    print(f"  {'AI Inference Latency — Avg':<35} {lat_avg:>12.1f} ms")
    print(f"  {'AI Inference Latency — Min':<35} {lat_min:>12.1f} ms")
    print(f"  {'AI Inference Latency — Max':<35} {lat_max:>12.1f} ms")
    print(f"  {'AI Inference Latency — Std Dev':<35} {lat_std:>12.1f} ms")
    print("-" * 55)
    print(f"  {'Blockchain Write Latency — Avg':<35} {BC_WRITE_LAT_AVG:>12.1f} ms")
    print(f"  {'Blockchain Write Latency — Min':<35} {BC_WRITE_LAT_MIN:>12.1f} ms")
    print(f"  {'Blockchain Write Latency — Max':<35} {BC_WRITE_LAT_MAX:>12.1f} ms")
    print("  (Permissioned network reference from paper)")
    print("-" * 55)
    print(f"  {'End-to-End Latency — Avg':<35} {E2E_AVG:>12.1f} ms")
    print(f"  {'End-to-End Latency — Min':<35} {E2E_MIN:>12.1f} ms")
    print(f"  {'End-to-End Latency — Max':<35} {E2E_MAX:>12.1f} ms")
    print("  (AI Inference + Blockchain Write)")
    print("=" * 55)

    # =========================================================
    # --- DISPLAY: TABLE 3 — Confusion Matrix Summary ---
    # =========================================================

    print("\n")
    print("=" * 45)
    print("  RESULTS TABLE 3 — Confusion Matrix")
    print("=" * 45)
    print(f"  {'':20} {'Pred: ATTACK':>10} {'Pred: BENIGN':>12}")
    print("-" * 45)
    print(f"  {'Actual: ATTACK':<20} {TP:>10}       {FN:>10}")
    print(f"  {'Actual: BENIGN':<20} {FP:>10}       {TN:>10}")
    print("=" * 45)
    print(f"\n  Total Samples Processed : {total_processed}")
    print(f"  Correctly Classified    : {overall_correct}")
    print(f"  Misclassified           : {total_processed - overall_correct}")
    print("=" * 45)


if __name__ == "__main__":
    run_json_evaluation()
