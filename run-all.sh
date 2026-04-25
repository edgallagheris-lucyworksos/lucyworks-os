#!/usr/bin/env bash
set -e

# backend
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# frontend
cd ../frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
