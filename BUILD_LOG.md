# 🛡️ Autonomous Tier-1.5 SOAR & AI Triage Pipeline — Engineering Build Log

**Author:** G. P. Dinujaya Thamara  
**Target Architecture:** Wazuh SIEM + n8n SOAR + OSINT APIs (VirusTotal, AbuseIPDB, GreyNoise) + Groq LLM (`llama-3.3-70b-versatile`) + ChatOps Active Response  
**Primary SOAR Host:** Zorin OS 18.1 (Ubuntu 24.04 Noble base, 8GB RAM)  
**Secondary SIEM/Endpoint Host:** MSI Gaming Laptop (Windows 11, 24GB RAM)

---

## 📅 Phase 0: Environment Preparation & Architectural Decisions

### Milestone 0.1 — Docker Engine & Repository Troubleshooting on Zorin OS
- **Action:** Installed Docker Engine and Docker Compose on Zorin OS 18.1.
- **Challenge & Fix:** The default `get.docker.com` script misidentified the OS base via `/etc/debian_version` (`trixie/sid`). Manually configured the official Docker `apt` repository targeting the `ubuntu noble` (24.04) stable channel and added user to the `docker` group.
- **Verification:** Confirmed Docker Engine and Compose v2 operational without `sudo`.

### Milestone 0.2 — Kernel Memory Tuning & Wazuh Indexer SSL Certificates
- **Action:** Configured Linux kernel virtual memory limits required by OpenSearch/Wazuh Indexer (`sudo sysctl -w vm.max_map_count=262144`).
- **Action:** Cloned `wazuh-docker` (`v4.9.2` branch) and executed `generate-indexer-certs.yml` via Docker Compose to provision root CA, node, and admin TLS certificates.

### Milestone 0.3 — Architectural Decision: Distributed Hybrid Lab & Cloud LLM Selection
- **Constraint Analysis:** The primary SOAR host runs on 8GB RAM. Running a local 8B LLM via Ollama (~4.5GB VRAM/RAM) alongside the Wazuh OpenSearch Indexer (~4GB RAM) and n8n would cause severe memory swap and latency.
- **Engineering Solution:**
  1. **AI Inference Offload:** Selected **Groq Cloud LPU API (`llama-3.3-70b-versatile`)** with strict JSON schema enforcement (`response_format: json_object`), achieving sub-second Tier-2 alert triage with **0 MB local RAM overhead**.
  2. **Multi-Host Enterprise Topology:** Isolated the n8n SOAR orchestration engine on Zorin OS (8GB RAM) while leveraging the 24GB RAM Windows 11 host for heavy endpoint telemetry (Sysmon + PowerShell logging) and SIEM workload distribution.

---

## ⚡ Phase 1: Core n8n SOAR Engineering & Execution Synchronization

### Milestone 1.1 — Programmatic Workflow Generation & Terminal Buffer Bypass
- **Challenge:** Pasting large multi-node n8n JSON schemas via raw heredoc (`cat << 'EOF'`) hit the Linux `N_TTY_BUF_SIZE` (4096-byte) paste buffer limit and browser pipe character corruption.
- **Engineering Fix:** Built an automated Python generator using `json.dump()` to programmatically compile `workflows/soar-pipeline.json` with strict schema validation.
- **Evidence:** `docs/screenshots/01_n8n_base_pipeline.png`

### Milestone 1.2 — Debugging Asynchronous Fan-In Race Condition (n8n v1 Execution Engine)
- **Bug Observed:** Connecting `Node 3 (Is Unique Alert?)` in a 4-way parallel fan-out directly into `Node 5 (Aggregate Enriched Context)` caused `Node 5` to fire as soon as `Node 4a (AbuseIPDB)` completed, throwing `Error: Node '4b. GreyNoise Scanner Check' hasn't been executed`.
- **Root Cause & Fix:** Re-architected the OSINT enrichment chain (`4a -> 4b -> 4c -> 4d -> 5`) using explicit state references (`$('2. Extract IOCs & 15m Dedup').first().json`) and defensive `safeGet()` `try/catch` wrappers in `Node 5`.
- **Evidence:** `docs/screenshots/02_race_condition_debug.png` (Failure) -> `docs/screenshots/03_full_pipeline_green_execution.png` (Resolved End-to-End Execution).

### Milestone 1.3 — Stage 1: Webhook Ingestion, IOC Regex Extraction & 15-Min Deduplication
- **Action:** Configured `POST /webhook/wazuh-soar-ingest` and engineered a JavaScript normalization node to extract `ioc_ip`, Sysmon/FIM `SHA256` hashes via regex (`/SHA256=([a-fA-F0-9]{64})/i`), `hostname`, and `command_line`.
- **Alert Fatigue Guardrail:** Implemented a stateful 15-minute (900,000 ms) TTL deduplication cache using `$getWorkflowStaticData('global')` keyed on `${hostname}_${ruleId}_${iocPart}`.
