# Federated Learning with Dual-Layer Blockchain Framework for Secure and Auditable Intrusion Detection

> Adithya D K 


---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Dataset Preparation & Splitting](#dataset-preparation--splitting)
- [Model Training](#model-training)
  - [Baseline CNN (Centralized)](#baseline-cnn-centralized)
  - [Federated Learning with FedProx](#federated-learning-with-fedprox)
- [Blockchain Infrastructure](#blockchain-infrastructure)
  - [Private Chain (Ganache / Hyperledger Besu)](#private-chain-ganache--hyperledger-besu)
  - [Public Chain (Sepolia Testnet)](#public-chain-sepolia-testnet)
- [IPFS Storage via Pinata](#ipfs-storage-via-pinata)
- [Smart Contract Deployment](#smart-contract-deployment)
- [Flask API & Inference Server](#flask-api--inference-server)
- [Monitoring Dashboard (Grafana + Prometheus)](#monitoring-dashboard-grafana--prometheus)
- [Immutability Demo Interface](#immutability-demo-interface)
- [Security Assessment](#security-assessment)
- [Results Summary](#results-summary)
- [Limitations & Future Work](#limitations--future-work)
- [References](#references)

---

## Overview

This project presents a **decentralized cybersecurity framework** that combines **Federated Learning (FL)** and a **dual-layer blockchain architecture** to deliver anomaly-based intrusion detection with full auditability.

Unlike traditional centralized IDS:
- Raw network traffic **never leaves** each organizational silo
- Model weight updates are **AES-256 encrypted** before transmission
- Every training round is **immutably anchored** on a public blockchain (Sepolia)
- Every runtime alert is **logged on a permissioned private blockchain** via Solidity smart contracts
- The system was evaluated against **14 distinct attack types** from the CIC-IDS2017 dataset

**FL Model Performance (after 4 rounds):**

| Metric | Baseline CNN | FL-trained CNN |
|---|---|---|
| Precision | 97.03% | **98.2%** |
| Recall (TPR) | 98.00% | **99.1%** |
| F1-Score | 97.51% | **98.6%** |
| False Positive Rate | 3.00% | **2.0%** |

---

## Architecture

The system is split into two cooperating layers:

### Training Layer (Federated + Blockchain Provenance)

```
CIC-IDS2017 Dataset
        │
  Non-IID Split → 3 Silos (A, B, C)
        │
  Each Silo: Local CNN + FedProx Training
        │
  Hybrid RSA-AES Encryption of local weights
        │
  Upload to IPFS via Pinata (encrypted .bin files)
        │
  CID + SHA-256 hash → Anchored on Sepolia Testnet
        │
  Aggregator verifies hash → FedAvg merge
        │
  Global CNN Model (updated each round)
```

### Inference Layer (Real-time Detection + Private Blockchain)

```
Network Traffic Input (structured 72-feature vector)
        │
  CNN-Based Anomaly Detection (Flask API)
        │
  Anomaly Alert + Metadata generated
        │
  Permissioned Ethereum Blockchain (Ganache / Besu)
        │
  Smart Contract validates + writes immutably
        │
  Grafana Dashboard (real-time monitoring)
```

---

## Key Features

- **Federated Learning (Cross-Silo):** Three independent nodes train locally; only encrypted weight updates are shared — raw data never leaves a silo.
- **FedProx Optimizer:** Proximal regularization (`μ = 0.01`) prevents client drift under Non-IID data, ensuring stable global convergence.
- **Hybrid Cryptographic Pipeline:** AES-256 (Fernet) for bulk weight encryption + RSA-2048 (OAEP-SHA256) for key exchange. A fresh AES key is generated per upload per round.
- **Dual-Layer Blockchain:**
  - *Public (Sepolia):* Immutable training provenance — CIDs, SHA-256 hashes, round metadata
  - *Private (Ganache/Besu QBFT):* Real-time operational alert logging via Solidity smart contracts
- **IPFS Off-Chain Storage:** Large model `.bin` files stored on Pinata-pinned IPFS; only the CID goes on-chain.
- **Smart Contract Governance:** `onlyOwner` modifier enforces write access; EVM `revert` makes tampering cryptographically verifiable.
- **Dockerized Inference:** Flask + TensorFlow server containerized for reproducibility across hardware environments.
- **Observability Stack:** Prometheus metrics + Grafana dashboards for real-time latency, throughput, and memory monitoring.

---

## Tech Stack

| Layer | Technology |
|---|---|
| ML Framework | TensorFlow / Keras |
| FL Optimizer | FedProx (custom proximal loss) |
| Dataset | CIC-IDS2017 |
| Encryption | PyCryptodome · cryptography (Fernet, RSA-OAEP) |
| Hashing | hashlib (SHA-256) |
| Off-chain Storage | IPFS via Pinata |
| Public Blockchain | Sepolia Ethereum Testnet (Web3.py) |
| Private Blockchain | Ganache (dev) / Hyperledger Besu QBFT (prod) |
| Smart Contracts | Solidity |
| API Server | Flask (Dockerized) |
| Input Validation | Cerberus |
| Monitoring | Prometheus + Grafana |
| Load Testing | Apache JMeter |

---

## Project Structure

```
├── data/
│   ├── raw/                        # Raw CIC-IDS2017 CSV files
│   └── splits/
│       ├── silo_A/                 # Non-IID split for Node A
│       ├── silo_B/                 # Non-IID split for Node B
│       └── silo_C/                 # Non-IID split for Node C
│
├── model/
│   ├── cnn_architecture.py         # CNN model definition (build_global_model)
│   ├── fedprox_loss.py             # FedProx proximal loss function
│   ├── baseline_train.py           # Centralized CNN training script
│   └── federated_train.py          # FL training loop (multi-round FedProx)
│
├── crypto/
│   ├── encrypt_weights.py          # AES-256 + RSA-2048 encryption
│   ├── decrypt_weights.py          # Decryption at aggregator
│   └── keys/
│       ├── public_key.pem
│       └── private_key.pem         # Never committed to repo
│
├── blockchain/
│   ├── contracts/
│   │   └── AnomalyLogger.sol       # Solidity smart contract
│   ├── deploy_contract.py          # Contract deployment script
│   ├── log_alert.py                # Alert logging to private chain
│   └── anchor_metadata.py          # CID + hash anchoring to Sepolia
│
├── ipfs/
│   └── pinata_upload.py            # Upload encrypted weights to IPFS via Pinata
│
├── flask_server/
│   ├── app.py                      # Flask inference API
│   ├── Dockerfile                  # Container definition
│   └── docker-compose.yml
│
├── monitoring/
│   ├── prometheus.yml
│   └── grafana_dashboard.json
│
├── evaluation/
│   ├── jmeter_test_plan.jmx        # JMeter load test plan
│   └── results/                    # Benchmark CSVs
│
└── README.md
```

---

## Setup & Installation

### Prerequisites

- Python 3.9+
- Node.js 16+ (for Hardhat/Truffle, optional)
- Docker & Docker Compose
- Ganache CLI or Ganache Desktop
- MetaMask (for Sepolia interactions)
- Pinata account (free tier works)

### 1. Clone the repo

```bash
git clone https://github.com/curiousdk29/Federated-Learning-with-Dual-Layer-Blockchain-Framework-for-Secure-and-Auditable-Intrusion-Detection.git
cd Federated-Learning-with-Dual-Layer-Blockchain-Framework-for-Secure-and-Auditable-Intrusion-Detection
```

### 2. Create virtual environment & install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Key packages in `requirements.txt`:**
```
tensorflow>=2.12
scikit-learn
pandas
numpy
web3
cryptography
pycryptodome
requests
flask
cerberus
prometheus-flask-exporter
pinata-python
```

### 3. Generate RSA key pair

```bash
python crypto/generate_keys.py
# Saves public_key.pem and private_key.pem to crypto/keys/
# NEVER commit private_key.pem — add it to .gitignore
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
PINATA_API_KEY=your_pinata_api_key
PINATA_SECRET_KEY=your_pinata_secret_key
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/your_project_id
SEPOLIA_PRIVATE_KEY=your_wallet_private_key
GANACHE_URL=http://127.0.0.1:7545
CONTRACT_ADDRESS=deployed_contract_address
API_KEY=your_flask_api_key
```

---

## Dataset Preparation & Splitting

### Download CIC-IDS2017

Download from the [Canadian Institute for Cybersecurity](https://www.unb.ca/cic/datasets/ids-2017.html) and place the CSV files in `data/raw/`.

### Class distribution (full dataset)

| Class | Samples |
|---|---|
| BENIGN | 2,271,320 |
| DoS Hulk | 230,124 |
| PortScan | 158,804 |
| DDoS | 128,025 |
| DoS GoldenEye | 10,293 |
| FTP-Patator | 7,935 |
| SSH-Patator | 5,897 |
| DoS Slowloris | 5,796 |
| DoS Slowhttptest | 5,499 |
| Bot | 1,956 |
| Web Attack – Brute Force | 1,507 |
| Web Attack – XSS | 652 |
| Infiltration | 36 |
| Web Attack – SQL Injection | 21 |
| Heartbleed | 11 |

### Non-IID Split for Federated Learning

```bash
python data/split_dataset.py --strategy non_iid --num_silos 3 --output_dir data/splits/
```

The script applies a **Non-IID partitioning strategy** — each silo receives a disproportionate share of certain attack classes, simulating real-world organizational diversity. A 70/15/15 train/validation/test split is applied within each silo.

The resulting split is:
- **Silo A:** DoS-heavy distribution
- **Silo B:** Web attack & scanning heavy
- **Silo C:** Mixed / balanced

---

## Model Training

### Baseline CNN (Centralized)

Trains on the full dataset as a reference point.

```bash
python model/baseline_train.py \
  --data_dir data/raw/ \
  --epochs 20 \
  --batch_size 256 \
  --output_path model/saved/baseline_cnn.h5
```

**CNN Architecture:**
```
Input: (9, 8, 1)  ← 72 features reshaped as 2D
Conv2D(32, 3×3, ReLU) → BatchNorm
Conv2D(64, 3×3, ReLU) → BatchNorm
Flatten → Dense(128, ReLU) → Dropout(0.3)
Dense(1, Sigmoid)   ← Binary: Benign / Attack
Loss: BinaryCrossentropy | Optimizer: Adam
```

---

### Federated Learning with FedProx

Run the full FL loop across 4 global rounds, 5 local epochs per round, 3 silos:

```bash
python model/federated_train.py \
  --silo_dirs data/splits/silo_A data/splits/silo_B data/splits/silo_C \
  --rounds 4 \
  --local_epochs 5 \
  --lr 0.0001 \
  --mu 0.01 \
  --public_key crypto/keys/public_key.pem \
  --pinata_key $PINATA_API_KEY \
  --sepolia_rpc $SEPOLIA_RPC_URL
```

**What happens each round:**
1. Global model weights broadcast to all silos
2. Each silo trains locally with FedProx loss:
   ```
   Loss = BCE(y_true, y_pred) + (μ/2) × ||w_local - w_global||²
   ```
3. Local weights encrypted: AES-256 (Fernet) + RSA-2048 key wrap
4. Encrypted `.bin` uploaded to IPFS via Pinata → CID returned
5. CID + SHA-256 hash anchored to Sepolia testnet
6. Aggregator downloads, verifies hash, decrypts, runs FedAvg
7. Repeat for next round

**The aggregator rejects any payload whose SHA-256 hash doesn't match the on-chain record.**

---

## Blockchain Infrastructure

### Private Chain (Ganache / Hyperledger Besu)

Used for **real-time operational alert logging**.

**Development (Ganache):**
```bash
ganache --port 7545 --networkId 1337 --accounts 10 --deterministic
```

**Production (Hyperledger Besu — QBFT, 3 nodes):**
```bash
cd blockchain/besu/
docker-compose up -d    # Spins up 3-node QBFT permissioned network
```

QBFT provides **immediate deterministic finality** — once a block is committed, it cannot be reverted without network-wide consensus. This is critical for forensic-grade alert immutability.

### Public Chain (Sepolia Testnet)

Used to **anchor AI training provenance** — CIDs, SHA-256 hashes, round metadata.

**Get Sepolia test ETH:** [sepoliafaucet.com](https://sepoliafaucet.com)

**Anchor a round's metadata:**
```bash
python blockchain/anchor_metadata.py \
  --node_id 1 \
  --round 4 \
  --cid QmdSpvReJEoNAd5mzrLPC9wWER2YifaPxJsHYnaMEwMdLv \
  --sha256 74b26fca8115dd58df41d65e8e0887ab7526bceff38e3f81565b121fa129921b \
  --sample_count 672584
```

---

## IPFS Storage via Pinata

Encrypted model weights are stored off-chain. Only the CID is committed on-chain.

```bash
python ipfs/pinata_upload.py \
  --file path/to/encrypted_weights.bin \
  --name "Node_1_Round_4_Update"
```

Returns a CID like: `QmTVFckFdW...`

**Why IPFS?** The CID is derived from the file's content hash — any tampering produces a different CID, making post-upload modification cryptographically detectable.

---

## Smart Contract Deployment

The Solidity contract (`AnomalyLogger.sol`) handles both model metadata logging and alert logging.

```bash
# Deploy to Ganache
python blockchain/deploy_contract.py --network ganache

# Deploy to Besu
python blockchain/deploy_contract.py --network besu
```

Update `CONTRACT_ADDRESS` in `.env` with the deployed address.

**Contract capabilities:**
- `logModelMetadata(versionId, hash, timestamp)` — provenance logging
- `logAlert(alertId, modelVersion, severity, timestamp, metadataHash)` — alert logging
- `onlyOwner` modifier — only the authorized AI inference agent can write
- EVM `revert` on unauthorized writes — verifiable at the blockchain level, not app level

---

## Flask API & Inference Server

### Run with Docker (recommended)

```bash
cd flask_server/
docker-compose up --build
```

### Run directly

```bash
cd flask_server/
python app.py
```

Server starts at `https://localhost:5006`

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/detect` | POST | CNN inference only (no blockchain) |
| `/record-only` | POST | Blockchain logging only (no inference) |
| `/detect-record` | POST | Full pipeline: inference + blockchain log |
| `/detect-record-500` | POST | Stress-test endpoint (500 req/s target) |
| `/immutability-check` | GET | Tamper demonstration interface |

### Example request

```bash
curl -X POST https://localhost:5006/detect-record \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_flask_api_key" \
  -d '{"features": [0.12, 0.45, ..., 0.89]}'   # 72-dimensional float vector
```

**Input validation:** Cerberus enforces strict 72-dimension float schema — malformed inputs are rejected before reaching TensorFlow.

---

## Monitoring Dashboard (Grafana + Prometheus)

```bash
cd monitoring/
docker-compose up -d    # Starts Prometheus + Grafana
```

- **Prometheus:** scrapes metrics from Flask (`/metrics`) and Ganache nodes
- **Grafana:** `http://localhost:3000` — import `grafana_dashboard.json`

Dashboard panels:
- Blockchain write latency (ms)
- AI inference latency (ms)
- Memory usage (GB)
- CPU usage (%)
- Throughput (TPS)

---

## Immutability Demo Interface

Navigate to `https://localhost:5006/immutability-check`

This page:
1. Submits an alert to the blockchain
2. Simulates an unauthorized overwrite attempt
3. Captures the raw EVM `revert` error from Ganache
4. Displays a 5-step animated timeline comparing before/after data field-by-field
5. Confirms the record is byte-for-byte identical post-tamper attempt

This proves tamper-rejection is enforced by the blockchain's `onlyOwner` modifier — **not** by application logic.

---

## Security Assessment

Vulnerabilities assessed using **CVSS v3.1**:

| Vulnerability | Before Mitigation | After Mitigation | Mitigation |
|---|---|---|---|
| Unauthorized Access | 9.8 Critical | 4.7 Medium | API key decorator on all sensitive endpoints |
| Improper Input Validation | 9.3 Critical | 0.0 None | Cerberus schema enforcement (72-dim float vector) |
| Data Integrity (In-Transit) | 6.5 Medium | 0.0 None | HTTPS via ad-hoc SSL context in Flask |
| System Availability (DoS) | 7.5 High | 5.3 Medium | TF session clearing + periodic garbage collection |

---

## Results Summary

### Detection Performance

| Metric | Baseline CNN | FL CNN (4 rounds) |
|---|---|---|
| Precision | 97.03% | 98.2% |
| Recall | 98.00% | 99.1% |
| F1-Score | 97.51% | 98.6% |
| False Positive Rate | 3.0% | 2.0% |

### Throughput (Normal Load — 1,000 samples)

| Configuration | TPS | Avg Latency |
|---|---|---|
| REST only (Baseline) | 209.9 | 2 ms |
| AI-Blockchain (Baseline) | 35.3 | 241 ms |
| REST only (FL) | 212.3 | 1 ms |
| AI-Blockchain (FL) | 50.7 | 155 ms |

### Throughput (Stress — 500 req/s, 10,000 samples)

Both deployments converge to ~**23–24 TPS** under blockchain load, confirming that the Ganache serialization ceiling (not inference speed) is the binding constraint at scale.

---

## Limitations & Future Work

- **Blockchain bottleneck:** The synchronous `bc_lock` mutex limits throughput to ~23 TPS. Replace with an atomic in-memory nonce counter + async write queue.
- **Ganache vs Besu:** All benchmarks were run against Ganache. Performance against the 3-node Besu QBFT network is expected to be substantially higher.
- **Inference layer privacy:** Alert metadata sent to the private chain is currently in plaintext within the secured local environment. Future: zero-knowledge proofs for alert verification.
- **Adversarial FL:** No defense against Byzantine poisoning nodes. Future: coordinate-wise median, FLTrust, or anomaly detection on weight distributions pre-aggregation.
- **Larger FL federation:** Test FedProx robustness with 10+ nodes and more extreme Non-IID distributions.
- **Newer datasets:** Evaluate on CIC-IDS2018 or UNSW-NB15 for broader generalizability.

---

## References

- Li et al. (2020) — FedProx: Federated Optimization in Heterogeneous Networks. *MLSys 2020*
- Goundar & Gondal (2025) — AI-Blockchain Integration for Real-Time Cybersecurity. *Journal of Cybersecurity and Privacy*
- Zhao et al. (2020) — Gradient inversion attacks on federated learning
- Sharafaldin et al. (2018) — CIC-IDS2017 Dataset. *ICISSP 2018*
- Dong et al. (2024) — Defending Against Poisoning Attacks in FL with Blockchain. *IEEE TDSC*
- Nododile & Nyirenda (2025) — Blockchain-IPFS hybrid storage
- Hyperledger Foundation (2022) — Besu QBFT Consensus Documentation

---

