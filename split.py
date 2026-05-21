"""
Non-IID Data Splitting for Federated Learning (CICIDS2017)
===========================================================
Method: Dirichlet Distribution-based splitting (alpha=0.5)
- Standard approach used in FL literature (FedProx, SCAFFOLD papers)
- Each node gets skewed class distributions mimicking real organizations:
    Node 1 → University-like: heavy PortScan, Web Attacks
    Node 2 → Hospital-like:   heavy Infiltration, Bot, DoS variants
    Node 3 → Bank-like:       heavy DDoS, FTP/SSH-Patator
- Global test set is kept STRATIFIED (IID) for fair evaluation
- Each node also has a local test set for per-node validation

Alpha guide:
    0.1  → Very Non-IID (extreme skew, harder FL problem)
    0.5  → Moderately Non-IID (recommended, used in FedProx paper)
    1.0  → Mild skew
    100  → Near IID
"""

import pandas as pd
import numpy as np
import glob
import os
from sklearn.model_selection import train_test_split
from collections import Counter
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # non-interactive backend for saving figures

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
DATA_FOLDER        = "dataset"   # folder containing CICIDS2017 CSV files
NODE_COUNT         = 3
ALPHA              = 0.5         # Dirichlet concentration parameter
GLOBAL_TEST_RATIO  = 0.10        # 10% held out as global test set (IID)
LOCAL_TEST_RATIO   = 0.20        # 20% of each node's data as local test
RANDOM_SEED        = 42
MIN_SAMPLES_PER_CLASS = 2        # safety floor per class per node


def load_and_merge(data_folder):
    """Load all CSVs from folder and merge into one DataFrame."""
    csv_files = glob.glob(os.path.join(data_folder, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in '{data_folder}'")

    print(f"📂 Found {len(csv_files)} CSV file(s). Merging...")
    df_list = []
    for f in csv_files:
        tmp = pd.read_csv(f, low_memory=False)
        tmp.columns = tmp.columns.str.strip()
        df_list.append(tmp)

    df = pd.concat(df_list, ignore_index=True)
    df.fillna(0, inplace=True)
    df['Label'] = df['Label'].str.strip()

    print(f"✅ Total samples after merge : {len(df):,}")
    print(f"   Classes found            : {df['Label'].nunique()}")
    return df


def dirichlet_split(X, y, n_clients, alpha, seed=42):
    """
    Split data across n_clients using Dirichlet distribution.

    For each class, sample proportions are drawn from Dir(alpha).
    Low alpha produces high skew (Non-IID); high alpha approaches IID.

    Returns
    -------
    List of (X_client, y_client) DataFrames, one per client.
    """
    np.random.seed(seed)
    classes = np.unique(y)
    client_indices = [[] for _ in range(n_clients)]

    for cls in classes:
        cls_indices = np.where(y.values == cls)[0]
        np.random.shuffle(cls_indices)
        n_cls = len(cls_indices)

        # Safety: too few samples → round-robin to guarantee every node gets some
        if n_cls < n_clients * MIN_SAMPLES_PER_CLASS:
            for i, idx in enumerate(cls_indices):
                client_indices[i % n_clients].append(idx)
            continue

        # Draw proportions from Dirichlet and convert to counts
        proportions = np.random.dirichlet(np.repeat(alpha, n_clients))
        counts = (proportions * n_cls).astype(int)

        # Fix rounding error — assign remainder to the node with highest proportion
        remainder = n_cls - counts.sum()
        counts[np.argmax(proportions)] += remainder

        # Assign slices
        start = 0
        for i, count in enumerate(counts):
            client_indices[i].extend(cls_indices[start : start + count].tolist())
            start += count

    # Build DataFrames
    clients = []
    for indices in client_indices:
        indices = np.array(indices)
        np.random.shuffle(indices)
        clients.append(
            (
                X.iloc[indices].reset_index(drop=True),
                y.iloc[indices].reset_index(drop=True),
            )
        )
    return clients


def print_distribution(name, y_series):
    """Pretty-print class distribution."""
    counts = Counter(y_series)
    total  = len(y_series)
    print(f"\n  📊 {name}  (total: {total:,})")
    print(f"  {'Label':<45} {'Count':>8}  {'%':>6}")
    print("  " + "-" * 63)
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {label:<45} {count:>8,}  {count / total * 100:>5.2f}%")


def plot_distributions(node_labels_list, save_path="node_distributions.png"):
    """
    Bar chart comparing class distributions across all nodes.
    Visually confirms the Non-IID skew for your report.
    """
    all_labels = sorted(
        set(label for y in node_labels_list for label in y.unique())
    )
    n_nodes  = len(node_labels_list)
    n_labels = len(all_labels)
    x        = np.arange(n_labels)
    width    = 0.25

    fig, ax = plt.subplots(figsize=(20, 7))
    colors  = ["#4C72B0", "#DD8452", "#55A868"]

    for i, y in enumerate(node_labels_list):
        counts = [Counter(y).get(lbl, 0) for lbl in all_labels]
        ax.bar(x + i * width, counts, width,
               label=f"Node {i + 1}", color=colors[i], alpha=0.85)

    ax.set_xticks(x + width)
    ax.set_xticklabels(all_labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Sample Count (Training Set)")
    ax.set_title(
        f"Non-IID Class Distribution Across Nodes  "
        f"(Dirichlet α = {ALPHA})",
        fontsize=13,
    )
    ax.legend(fontsize=11)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    print(f"\n📈 Distribution plot saved → {save_path}")


def compute_heterogeneity(node_labels_list):
    """
    Print Earth Mover's Distance proxy (std of class proportions across nodes).
    Gives a quantitative measure of Non-IID-ness for your report.
    """
    all_labels = sorted(
        set(label for y in node_labels_list for label in y.unique())
    )
    print("\n  Non-IID Heterogeneity Measure")
    print(f"  {'Label':<45} {'Std of proportions':>20}")
    print("  " + "-" * 67)
    for lbl in all_labels:
        props = []
        for y in node_labels_list:
            total = len(y)
            props.append(Counter(y).get(lbl, 0) / total)
        print(f"  {lbl:<45} {np.std(props):>20.4f}")
    print(
        "\n  Higher std → more skewed (Non-IID) distribution for that class."
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def prepare_noniid_nodes(
    data_folder=DATA_FOLDER,
    node_count=NODE_COUNT,
    alpha=ALPHA,
):
    # 1. Load ─────────────────────────────────────────────────────────────────
    df = load_and_merge(data_folder)
    X  = df.drop("Label", axis=1)
    y  = df["Label"]

    # 2. Global hold-out test set (STRATIFIED for fair evaluation) ────────────
    print(f"\n🌟 Carving out global test set ({GLOBAL_TEST_RATIO*100:.0f}% stratified)...")
    (
        X_train_pool, X_global_test,
        y_train_pool, y_global_test,
    ) = train_test_split(
        X, y,
        test_size=GLOBAL_TEST_RATIO,
        stratify=y,
        random_state=RANDOM_SEED,
    )

    global_df = pd.concat([X_global_test, y_global_test], axis=1)
    global_df.to_csv("global_test.csv", index=False)
    print(f"💾 global_test.csv saved  ({len(global_df):,} samples, IID/stratified)")
    print_distribution("Global Test Set", y_global_test)

    # 3. Dirichlet Non-IID split ──────────────────────────────────────────────
    print(
        f"\n⚖️  Applying Dirichlet split (α={alpha}) across {node_count} nodes..."
    )
    print(
        f"   Non-IID level: "
        f"{'High' if alpha <= 0.1 else 'Moderate' if alpha <= 0.5 else 'Low'}"
    )
    node_splits = dirichlet_split(
        X_train_pool, y_train_pool,
        n_clients=node_count,
        alpha=alpha,
        seed=RANDOM_SEED,
    )

    # 4. Save node datasets ───────────────────────────────────────────────────
    print("\n💾 Saving node datasets...")
    node_train_labels = []

    for i, (X_node, y_node) in enumerate(node_splits, start=1):
        node_folder = f"Node_{i}"
        os.makedirs(node_folder, exist_ok=True)

        node_df = pd.concat([X_node, y_node], axis=1)

        # Local train / local test split
        try:
            train_df, test_df = train_test_split(
                node_df,
                test_size=LOCAL_TEST_RATIO,
                stratify=node_df["Label"],
                random_state=RANDOM_SEED,
            )
        except ValueError:
            # Fallback if a class has only 1 sample in this node
            print(
                f"  ⚠️  Node {i}: stratify failed for local split "
                f"(some classes have 1 sample). Using random split."
            )
            train_df, test_df = train_test_split(
                node_df,
                test_size=LOCAL_TEST_RATIO,
                random_state=RANDOM_SEED,
            )

        train_df.to_csv(f"{node_folder}/train.csv", index=False)
        test_df.to_csv(f"{node_folder}/test.csv",   index=False)

        print(f"\n✅ Node {i} → {node_folder}/")
        print(f"   Train: {len(train_df):,}   Local Test: {len(test_df):,}")
        print_distribution(f"Node {i} Training Distribution", train_df["Label"])

        node_train_labels.append(train_df["Label"])

    # 5. Heterogeneity measure ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    compute_heterogeneity(node_train_labels)

    # 6. Plot ─────────────────────────────────────────────────────────────────
    plot_distributions(node_train_labels, save_path="node_distributions.png")

    # 7. Final summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SPLIT SUMMARY")
    print("=" * 60)
    print(f"  Dirichlet alpha          : {alpha}")
    print(
        f"  Non-IID level            : "
        f"{'High' if alpha <= 0.1 else 'Moderate' if alpha <= 0.5 else 'Low'}"
    )
    print(f"  Global test set (IID)    : {len(global_df):,} samples")
    for i in range(1, node_count + 1):
        t = f"Node_{i}/train.csv"
        v = f"Node_{i}/test.csv"
        if os.path.exists(t) and os.path.exists(v):
            print(
                f"  Node {i} train / local-test: "
                f"{len(pd.read_csv(t)):,} / {len(pd.read_csv(v)):,}"
            )
    print("=" * 60)
    print("\n✅ All files created:")
    print("   global_test.csv          ← use for final FL model evaluation")
    for i in range(1, node_count + 1):
        print(f"   Node_{i}/train.csv       ← local Non-IID training data")
        print(f"   Node_{i}/test.csv        ← local validation data")
    print("   node_distributions.png   ← include in your report")


if __name__ == "__main__":
    prepare_noniid_nodes(
        data_folder=DATA_FOLDER,
        node_count=NODE_COUNT,
        alpha=ALPHA,
    )