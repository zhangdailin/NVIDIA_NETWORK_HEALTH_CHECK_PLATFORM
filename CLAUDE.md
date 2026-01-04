# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NVIDIA InfiniBand Network Health Check Platform - a full-stack web application for analyzing network diagnostics from IBDiagnet archives and UFM CSV files.

## Analysis Tool

The `ib_analysis` module is integrated directly into `backend/ib_analysis/`. It provides InfiniBand diagnostics analysis with the following operations:
- `brief` - Comprehensive summary
- `topo` - Network topology visualization (HTML)
- `cable` - Cable and optical module analysis
- `xmit` - Transmission/congestion analysis
- `ber` - Bit Error Rate analysis
- `hca` - Host Channel Adapter/firmware analysis

## Input Sources

1. **IBDiagnet Archives** (.zip/.tar.gz): Output from UFM's ibdiagnet tool
2. **UFM CSV Files**: Generated via UFM REST API, e.g.:
   ```bash
   curl -s 127.0.0.1:9002/csv/xcset/low_freq_debug > low_freq_debug.csv
   ```

## Reference Documentation

- [IBDiagnet User Manual v2.13.0](https://docs.nvidia.com/ibdiagnet-infiniband-fabric-diagnostic-tool-user-manual-v2-13-0.pdf)
- [UFM Enterprise REST API Guide v6.22](https://docs.nvidia.com/networking/display/nvidia-ufm-enterprise-rest-api-guide-v6-22-2.2.pdf)

## Commands

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

## Architecture

**Frontend** (`frontend/`): React 19 SPA with Vite. Single main component (`src/App.jsx`) handles file uploads and displays tabbed analysis results. Communicates with backend at `http://localhost:8000/api`.

**Backend** (`backend/`): FastAPI server with two main endpoints:
- `POST /api/upload/ibdiagnet` - Accepts .zip/.tar.gz archives, extracts them, runs analysis via integrated `ib_analysis` module
- `POST /api/upload/ufm-csv` - Parses CSV files with pandas

**ib_analysis Module** (`backend/ib_analysis/`): Integrated analysis library using `OperationManager` for executing operations. Key classes:
- `OperationManager` - Orchestrates analysis operations
- `Graph` - Network topology
- `Xmit`, `Ber`, `CableManager`, `HcaManager` - Specialized analyzers

**File Storage**: Uploads stored in `uploads/` with UUID-based task directories. Generated HTML topology maps served as static files.
