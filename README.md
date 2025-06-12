# MIMIC-FHIR Bedrock Agent

> Production-grade reference implementation for conversational access to the
> [MIMIC-IV](https://mimic.mit.edu) FHIR data model, powered by AWS Bedrock and
> React 18.

```
┌──────────────────────────────┐    ┌─────────────────────────┐
│  React 18 + Cloudscape UI    │◀──▶│  python-server (FastAPI) │
└──────────────────────────────┘    │  • S2sSessionManager     │
                                     │  • MimicFhirAgent        │
WebSocket (S2S events)               │  • MimicFhirMcpClient    │
                                     │  • differential_diagnosis│
┌─────────────┐   Async Threads       └─────────────────────────┘
│ Bedrock LLM │  & boto3 calls                ▲
└─────────────┘                                │
       ▲                                        │
       │                         Local SQLite   │
       │                         (fhir/*)       │
       └────────────────────────────────────────┘
```

## Repository Layout

```
aws_hackathon/
├─ python-server/            # Backend (Python 3.12)
│  ├─ integration/
│  │  ├─ mimic_fhir_agent.py # Bedrock agent wrapper
│  │  ├─ mimic_fhir_mcp_client.py # FHIR tool dispatch
│  │  ├─ mimic_patient_class.py   # Rich patient object
│  │  └─ differential_diagnosis.py
│  ├─ s2s_session_manager.py # Streaming session ↔ frontend
│  └─ tests/                 # pytest
├─ react-client/             # Front-end (React 18, TS)
│  └─ src/s2s.js             # WebSocket + UI renderer
└─ fhir/                     # Local SQLite FHIR datastore & CLI
```

## Features

* 🔎 **Conversational FHIR Search** – Natural-language queries are mapped to
  schema-validated tool calls (e.g. `findPatient`, `getPatientObservations`).
* 🩺 **Differential Diagnosis** – Invokes Bedrock Claude Sonnet 4 with patient
  summary & symptoms to suggest differential lists.
* 📅 **Follow-up Scheduling** – `scheduleFollowUp` tool writes future
  appointment meta to the patient record.
* ⚡ **Streaming S2S Protocol** – Low-latency bi-directional events; supports
  text+audio.
* 🗄️ **Local MIMIC-IV Sandbox** – Lightweight SQLite store for offline dev.

## Quick-start

### 1. Clone & Install

```bash
$ git clone <repo-url> && cd aws_hackathon
$ python -m venv .venv && source .venv/bin/activate
$ pip install -r python-server/requirements.txt
$ cd react-client && npm ci && cd ..
```

### 2. Environment

Set **once** in `~/.bashrc` or similar (do **not** commit secrets):

```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=<key>
export AWS_SECRET_ACCESS_KEY=<secret>
export FHIR_AGENT_MODEL=amazon.nova-sonic-v1:0 # optional override
```

### 3. Ingest Demo Data (optional)

```bash
$ python fhir/process_ndjson.py --ndjson path/to/mimic-fhir.ndjson
```

### 4. Run Services

```bash
# backend
$ cd python-server
$ python server.py --agent mimic_fhir # port 8000
# frontend (in another shell)
$ cd react-client && npm start            # http://localhost:3000
```

> Backend automatically opens WebSocket `/api/s2s` for the React client.

## Tool Catalogue

| Tool Name              | Purpose                                        | Required Params |
|------------------------|------------------------------------------------|-----------------|
| `findPatient`          | Search patients by name, DOB, etc.             | `query`         |
| `searchById`           | Fetch single FHIR resource                     | `resource_id`   |
| `searchByType`         | All resources of a given FHIR type             | `resource_type` |
| `getPatientObservations` | Vital-sign / lab Observation list            | `patient_id`    |
| `getPatientConditions` | Chronic / encounter conditions                 | `patient_id`    |
| `getPatientMedications`| Active medication requests                     | `patient_id`    |
| `differential_diagnosis`| Claude-powered differential list              | `patient_id`, `symptoms` |
| `scheduleFollowUp`     | Persist follow-up appointment time             | `patient_id`, `scheduled_time`, `reason?` |

Tools are surfaced to the LLM via a JSON schema; new tools are
self-discoverable at runtime.

## Data Flow

1. React triggers a user prompt over WebSocket.
2. `S2sSessionManager` streams content to Bedrock; **toolUse** events are
   intercepted.
3. `MimicFhirAgent` maps tool to `MimicFhirMcpClient`, executes async (with
   timeout guards).
4. Responses are truncated safely (15 kB) and streamed back; React merges via
   `deepMerge` into component state.

## Testing

```bash
$ pytest -q python-server/tests
```

All new code **must** include Google-style docstrings and tests. Continuous
integration uses `ruff` + `pytest`.

## Deployment

*Python server* is container-ready (`Dockerfile` TBD). Front-end can be shipped
via Netlify (`npm run build`). Use **AWS Bedrock** VPC endpoints in production.

## Roadmap

- 🔐 Fine-grained IAM for tool execution
- 🩺 Clinical validation rules engine
- 📊 Grafana dashboards for prompt & performance metrics

---
### License
MIT (c) 2025 — for educational / research purposes only. MIMIC-IV data is
subject to PhysioNet credentialing.
