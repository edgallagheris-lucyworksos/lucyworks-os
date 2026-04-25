#!/usr/bin/env bash
set -e
cd backend
python -m pip install -r requirements.txt
python smoke_test.py
