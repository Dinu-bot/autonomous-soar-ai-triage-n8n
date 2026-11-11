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

### Milestone 1.4 — Stage 2 & 3: OSINT Threat Intelligence & Internal Asset CMDB Correlation
- **GreyNoise Community API Bypass:** Verified that `GET https://api.greynoise.io/v3/community/{ip}` supports unauthenticated queries from residential IPs without requiring corporate domain registration. Disabled header injection on `Node 4b` to query scanner status cleanly.
- **Asset Criticality CMDB (`Node 4d`):** Engineered an internal asset classification lookup mapping `FINANCE-SRV-01` to `CRITICAL (Tier-0 Crown Jewel)` so downstream LLM triage weighs business impact alongside technical severity.

### Milestone 1.5 — Stage 4: Groq LLM (`openai/gpt-oss-120b`) Structured JSON Triage
- **Troubleshooting `401 Invalid API Key` & Model Deprecation:**
  1. Diagnosed initial `401 Unauthorized` response (`docs/screenshots/04a_groq_401_auth_debug.png`) and migrated `Node 6` to n8n's native `Generic Credential Type -> Bearer Auth`.
  2. Inspected Groq platform API logs and identified `model_not_found` for legacy `llama-3.3-70b-versatile`.
  3. Migrated inference payload to OpenAI's flagship 120B open-weight reasoning model on Groq (`openai/gpt-oss-120b`) with `"response_format": {"type": "json_object"}` and `temperature: 0.1`.
- **Verification:** Executed live alert triage against IOC `89.248.165.131`. Confirmed `openai/gpt-oss-120b` returned both Chain-of-Thought `reasoning` and strict JSON `content` containing `risk_verdict`, `mitre_technique: "T1059.001"`, `root_cause_bullets`, and PowerShell firewall containment commands.
- **Evidence:** `docs/screenshots/04_groq_ai_json_verdict.png`

### Milestone 1.6 — Stage 5: Discord ChatOps Dispatch & Windows Backslash JSON Serialization Fix
- **Bug Observed:** When `openai/gpt-oss-120b` generated Windows PowerShell remediation commands containing unescaped file path backslashes (`Remove-Item -Path 'C:\Windows\Temp\payload.ps1'`), raw string interpolation inside `Node 8`'s JSON body threw `JSON parameter needs to be valid JSON`.
- **Engineering Fix:** Migrated `Node 8 (Dispatch ChatOps Interactive Card)` from raw JSON string interpolation (`specifyBody: "json"`) to structured key-value body parameters (`Using Fields Below` / `specifyBody: "keypair"`), delegating RFC 8259 backslash and quote escaping to n8n's native serializer before posting to Discord's `/slack` webhook adapter.
- **Verification:** Confirmed `200 OK` (`"ok"`) response from Discord API and verified live interactive incident card rendering in the SOC Discord server (`Confidence: 0.93`, `MITRE: T1059.001`).
- **Evidence:** `docs/screenshots/05_discord_chatops_alert_card.jpeg`

### Milestone 1.7 — Human-in-the-Loop Active Response Webhook (`Nodes 9 & 10`) & Custom Wazuh Bridge
- **Action:** Verified `GET /webhook/soar-active-response` and `/webhook-test/soar-active-response` (`action=isolate_host`, `agent_id=004`, `hostname=FINANCE-SRV-01`, `ioc_ip=89.248.165.131`), confirming query parameter extraction (`Node 9`) and downstream Active Response execution (`Node 10` -> `status: "ACTIVE_RESPONSE_EXECUTED"`).
- **Wazuh Integration Bridge:** Authored `integrations/custom-n8n.py` and `integrations/ossec_integration_snippet.xml` to forward Level 10+ Wazuh alerts directly into the n8n ingestion webhook.
- **Evidence:** `docs/screenshots/06_active_response_webhook.png` & `docs/screenshots/07_active_response_executed.png`
