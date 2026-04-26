---
layout: project
title: anomali-flow/
project: anomali-flow
repo: datascience-labs/anomali-flow
permalink: /:path/:basename:output_ext
---

# AnomaliFlow
This application provides a robust framework for managing machine learning tasks using FastAPI, Celery, MongoDB, Redis, Streamlit, and a React + TypeScript + Ant Design dashboard.

## Features
- API-first asynchronous task execution (`/tasks`)
- Tenant-aware task status, causal report, and action recommendation APIs
- Operations APIs for dashboard summary, audit events, and quota
- Streamlit legacy UI (parallel run)
- React enterprise dashboard (new)

## Components
- FastAPI: API server
- Celery: async workers
- MongoDB: result/audit/report storage
- Redis: broker
- React + TypeScript + Ant Design: enterprise dashboard (`frontend/`)
- Streamlit: legacy UI

## Run (recommended)
> docker compose up --build -d redis mongo celery_worker fastapi frontend

Optional legacy UI:
> docker compose up --build -d streamlit

## Access
- React Dashboard: http://localhost:5173
- FastAPI Docs: http://localhost:8000/docs
- Streamlit (legacy): http://localhost:8501
- Prefect Orion: http://localhost:4200

### Quick local test (without Docker)
Backend:
1. `python -m venv .venv`
2. `.\\.venv\\Scripts\\activate`
3. `pip install -r requirements.txt`
4. `uvicorn main:app --reload --port 8000`

Frontend:
1. `cd frontend`
2. `copy .env.example .env`
3. `npm install`
4. `npm run dev`

### Validation commands
- Backend compile check: `python -m compileall main.py worker.py repositories.py app.py`
- Frontend lint/build: `cd frontend && npm run lint && npm run build`
