# NEXUS - Autonomous OSINT, Reconnaissance & Intelligence Research Platform

NEXUS is an agentic intelligence research and reconnaissance platform designed to investigate targets (companies, individuals, domains, technology focus areas, projects), gather evidence from permitted public sources, resolve entities, verify evidence, and produce structured, evidence-backed intelligence reports.

---

## Technical Stack (Foundation)
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Testing**: pytest, pytest-asyncio
- **Packaging**: Standard `pyproject.toml` with setuptools

---

## Quickstart

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Backend Setup & Virtual Environment

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies in editable mode
pip install -e ".[dev]"
```

### 3. Running Unit Tests

```bash
# Run pytest from the root or backend directory
pytest
```

### 4. Running the Development Server

```bash
# Launch FastAPI backend with Uvicorn
cd backend
uvicorn app.main:app --reload --port 8000
```

Verify endpoint at `http://localhost:8000/health`:
```json
{
  "status": "ok",
  "service": "nexus",
  "version": "0.1.0"
}
```

---

## Security & Ethical Boundaries
NEXUS is strictly designed for lawful, authorized research on publicly available information and defensive security reconnaissance. It must never be configured or extended to bypass access controls, harvest private data, or perform unauthorized active exploitation.
