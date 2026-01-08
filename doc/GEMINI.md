# GEMINI.md

This file provides guidance to Gemini when working with code in this repository.

## Project Overview

NVIDIA InfiniBand Network Health Check Platform - a full-stack web application for analyzing network diagnostics from IBDiagnet archives and UFM CSV files.

The application consists of a React/Vite frontend and a FastAPI backend. The backend provides a REST API for uploading and analyzing network health data. The frontend provides a user interface for uploading files and viewing the analysis results.

## Building and Running

### Quick Start (Both Frontend & Backend)
```bash
npm install          # First time only
npm run server       # Starts both frontend and backend
```

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev      # Dev server at http://localhost:5173
npm run build    # Production build
npm run lint     # ESLint
```

### Docker
```bash
docker-compose up -d
```

## Architecture

**Frontend** (`frontend/`): React 19 SPA with Vite. Single main component (`src/App.jsx`) handles file uploads and displays tabbed analysis results. Communicates with backend at `http://localhost:8000/api`.

**Backend** (`backend/`): FastAPI server with two main endpoints:
- `POST /api/upload/ibdiagnet` - Accepts .zip/.tar.gz archives, extracts them, and runs analysis.
- `POST /api/upload/ufm-csv` - Parses CSV files with pandas.

**Analysis Service** (`backend/services/analysis_service.py`): The core analysis logic, which processes the uploaded data and generates a health score and detailed analysis.

**Log Analysis Service** (`backend/services/log_analysis_service.py`): Parses `ibdiagnet2.log` to extract critical errors, warnings, and routing validation results (e.g., credit loops), implementing the "Routing Validation" capability.

**File Storage**: Uploads stored in `uploads/` with UUID-based task directories. Generated HTML topology maps served as static files.
