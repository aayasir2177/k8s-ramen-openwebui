# Hybrid Local AI: Kubernetes Open WebUI + Bare-Metal RAMen AI

A high-efficiency, zero-recomputation local AI infrastructure running on modest home server hardware (**Intel Core i3-4160T**, 16 GB DDR3 RAM, Fedora Linux). 

This setup combines a **Kubernetes-hosted Open WebUI** frontend exposed securely via **Cloudflare Tunnel** with a **Bare-Metal RAMen AI Context Engine** on the host OS to eliminate container CPU throttling, constrain context size to prevent CPU freezes, and persist KV-cache attention slots directly to NVMe/SSD.

---

## Architecture Diagram

![Hybrid Local AI Architecture](docs/architecture.png)

```text
[ Browser / User ]
        │ (HTTPS)
        ▼
[ Cloudflare Edge: openwebui.homenode.online ]
        │
        ▼ (Outbound QUIC Tunnel - Zero Inbound Ports)
┌────────────────────────────────────────────────────────────────────────┐
│ Kubernetes Cluster (k3s) - Namespace: ai                               │
│                                                                        │
│  [ cloudflared ] ───► [ openwebui-service:8080 ]                       │
│                              │                                         │
│                              ▼                                         │
│                     [ openwebui Pod ] ───► [ openwebui-pvc (2Gi) ]     │
│                              │              (Users & Chat History)     │
│                              │                                         │
└──────────────────────────────┼─────────────────────────────────────────┘
                               │ OpenAI API: http://192.168.100.11:8090/v1
                               ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Bare-Metal Host (Fedora Linux - Intel i3-4160T, 16 GB RAM)             │
│                                                                        │
│  [ firewalld: Port 8090/TCP Allowed ]                                  │
│        │                                                               │
│        ▼                                                               │
│  [ RAMen AI Daemon (:8090) ]                                           │
│        │                                                               │
│        ├──► [ llama-server ] (Qwen3 4B Instruct / 2048 Context / 4 Thr)│
│        │                                                               │
│        └──► [ SSD KV-Cache Store ] (~/.context-engine/sessions)        │
│             (Zero-Recompute Slot Swapping in ~50ms)                    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## The Engineering Challenge & Solution

### 1. The Dual-Core CPU & Memory Bottleneck
Running local LLMs on an older dual-core processor (Intel Core i3-4160T, 2 cores, 4 threads, 35W TDP, Haswell) poses severe constraints:
* **8B Model Overload**: An 8-Billion parameter model requires reading ~4.7 GB of weights per token. On a dual-core CPU with DDR3 memory bandwidth, prompt processing locks the CPU at 100% for minutes.
* **Unconstrained Context Windows**: When RAMen starts with 14+ GB of free memory, its automatic planner allocates **19,000 to 51,000 token context windows**. On a low-power CPU, calculating attention matrices across 19K tokens paralyzes the system indefinitely.
* **The Solution**: 
  1. Downscale to a compact, high-efficiency 4B model (**Qwen3 4B Instruct**, 2.5 GB).
  2. Enforce a strict context window of **2,048 tokens** (`--ctx 2048`).
  3. Maximize parallel execution across all logical threads (`--threads 4`).

### 2. Why Run RAMen Bare-Metal Outside Kubernetes?
* **Zero Container/Cgroups Throttling**: Direct access to AVX2 instruction sets without container virtualization layers.
* **Persistent Model & Cache Directory**: Models and session snapshots live permanently in `/home/yasir/.context-engine/` on host storage without re-downloading on pod restarts.
* **Direct Network Access**: Open WebUI in Kubernetes connects directly to the host IP (`http://192.168.100.11:8090/v1`) after allowing port 8090 in Fedora's `firewalld`.

### 3. How RAMen AI Eliminates Prompt Prefill Latency
In standard inference engines (vanilla llama.cpp or Ollama):
* Every turn in a conversation forces the model to re-read and compute the mathematical Key-Value attention states for **all previous messages** (Prompt Evaluation).
* On an i3 CPU, a 1,500-token chat history requires 30 to 60 seconds of 100% CPU time before emitting token 1.

With RAMen AI:
* RAMen captures the computed **KV cache vectors** in memory after each generation.
* **SSD Slot Swapping**: When switching chats or when an idle timeout triggers, RAMen snapshots the binary KV matrices to `~/.context-engine/sessions/` on the SSD.
* **Instant Recall**: When resuming a conversation, RAMen reads the session back into memory in ~50ms, skipping the prompt prefill phase entirely.

---

## Repository Structure

```text
.
├── diagram.py                         # Python diagrams script generating architecture.png
├── docs/
│   └── architecture.png               # High-resolution visual system diagram
└── k8s/
    ├── 01-deployment-openwebui.yaml   # Open WebUI deployment (points to 192.168.100.11:8090)
    ├── 02-service-openwebui.yaml      # ClusterIP service for Open WebUI (port 8080)
    ├── 03-pvc-openwebui.yaml          # 2Gi storage for SQLite database & user sessions
    └── kustomization.yaml             # Single-command Kustomize bundle
```

---

## Step-by-Step Deployment Guide

### Phase 1: Host Preparation (Fedora Linux)

#### 1. Open Port 8090 in Fedora Firewall
Fedora's `firewalld` blocks pod network traffic (`10.42.0.0/16`) to host ports by default. Allow TCP port 8090:

```bash
sudo firewall-cmd --add-port=8090/tcp --permanent
sudo firewall-cmd --reload
```

#### 2. Install RAMen AI
```bash
curl -fsSL https://getramenai.com/install.sh | bash
export PATH="$HOME/.ramen/bin:$PATH"
```

#### 3. Start RAMen with 2048 Context Limit
```bash
ramen start qwen3-4b --ctx 2048 --host 0.0.0.0 --port 8090
```

Verify the local model server is healthy:
```bash
curl http://127.0.0.1:8090/v1/models
# Output: {"object": "list", "data": [{"id": "qwen3:4b", ...}]}
```

---

### Phase 2: Kubernetes Deployment (k3s)

#### 1. Deploy Open WebUI
Deploy Open WebUI using Kustomize:

```bash
kubectl apply -k k8s/
```

#### 2. Verify Pod and Service
```bash
kubectl get pods,svc -n ai
```

#### 3. Verify Direct Connectivity to Host
Test that the Open WebUI container can reach RAMen running on the host:

```bash
kubectl exec -it -n ai deploy/openwebui -- curl -s http://192.168.100.11:8090/v1/models
```

---

## Operational Verification

### Check Context Memory & Active Slots
```bash
ramen status
```
* Displays active conversation slots currently resident in RAM.
* Confirms the 2,048 token limit per slot.

### Inspect Saved KV-Cache on SSD
```bash
ls -lh ~/.context-engine/sessions/
```
Shows serialized binary cache files persisted to disk for instant conversation resumption without CPU recalculation.

---

## Hardware Specifications

| Component | Specification |
| :--- | :--- |
| **Host System** | Fedora Linux 41 (x86_64) |
| **CPU** | Intel(R) Core(TM) i3-4160T @ 3.10GHz (2 Cores, 4 Threads, 35W TDP) |
| **Memory** | 16 GB DDR3 Non-ECC |
| **Storage** | High-speed SSD (KV-cache slot swapping) |
| **Orchestration**| Lightweight Kubernetes (`k3s`) |
| **Ingress** | Outbound Cloudflare QUIC Tunnel (`cloudflared`) |
| **Active Model** | `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (2.5 GB) |
