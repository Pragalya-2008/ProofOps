#!/bin/bash
export PYTHONUNBUFFERED=1
exec python3 -m streamlit run app.py --server.port 3000 --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false
