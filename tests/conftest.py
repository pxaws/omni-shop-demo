import os

# app.py builds its module-level app from ROLE at import time; tests build their own.
os.environ.setdefault("ROLE", "checkout")
