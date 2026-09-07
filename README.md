# NEXUS - Autonomous OSINT, Reconnaissance & Intelligence Research Platform

NEXUS is an agentic intelligence research and reconnaissance platform designed to investigate targets (companies, individuals, domains, technology focus areas, projects), gather evidence from permitted public sources, resolve entities, verify evidence, and produce structured, evidence-backed intelligence reports.

---

## Technical Stack (Foundation)
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Testing**: pytest, pytest-asyncio
- **Packaging**: Standard `pyproject.toml` with setuptools

---

## Quickstart & Local Execution

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Backend Setup & Virtual Environment

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### 3. Running Unit & Integration Tests

```bash
cd backend
pytest -v
```

### 4. Running the Development Server

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Interactive Demonstration UI

Once the server is running, open your browser to the interactive demo:

👉 **[http://localhost:8000/demo](http://localhost:8000/demo)**

The standalone demo provides:
- Live target investigation (`python.org`, `djangoproject.com`, `example.com`)
- Real-time execution status and phase timing breakdown (`target_validation`, `crawl`, `extraction`, `enrichment`, `total`)
- Interactive cards for Organization Profile, Detected Technologies, Verified Findings, and Entity Relationships
- Full Raw JSON inspector

Interactive Swagger API docs are also available at **[http://localhost:8000/docs](http://localhost:8000/docs)**.

---

## Website Intelligence API

### Endpoint: `POST /api/v1/investigations/website`

Executes the complete bounded website intelligence pipeline with SSRF protections and public OSINT enrichment.

#### Request Example (cURL)
```bash
curl -X POST "http://localhost:8000/api/v1/investigations/website" \
  -H "Content-Type: application/json" \
  -d '{
    "target": "https://www.python.org",
    "max_pages": 2,
    "enrich": true
  }'
```

#### Response Structure
```json
{
  "investigation_id": "8f3b2075-8025-4b5b-9d41-38e55e094c97",
  "status": "completed",
  "target": "https://www.python.org",
  "canonical_domain": "python.org",
  "tasks_count": 2,
  "findings_count": 4,
  "evidence_count": 2,
  "entities_count": 36,
  "relationships_count": 25,
  "timings": {
    "target_validation_ms": 1.25,
    "crawl_ms": 1420.30,
    "extraction_ms": 15.40,
    "enrichment_ms": 3210.80,
    "total_ms": 4647.75
  },
  "report": {
    "executive_summary": "Passive reconnaissance of 'python.org' identified organization...",
    "organization_profile": { ... },
    "technologies": [ ... ],
    "findings": [ ... ],
    "people_and_organizations": [ ... ],
    "relationships": [ ... ]
  }
}
```

---

## Documentation
- [Architecture Specification](docs/architecture/nexus_architecture_v1.md)
- [Website Intelligence Capability](docs/capabilities/website_intelligence.md)
- [Real-World Validation & Hardening Report](docs/capabilities/website_intelligence_validation.md)
- [Agents SDK Integration Guide](docs/architecture/agents_sdk_integration.md)

---

## Security & Ethical Boundaries
NEXUS is strictly designed for lawful, authorized research on publicly available information and defensive security reconnaissance. It must never be configured or extended to bypass access controls, harvest private data, or perform unauthorized active exploitation.
