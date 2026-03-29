# CLAUDE.md — routers/

Every router in this directory follows the same pattern:

1. Import models from models.py (never define inline)
2. Import get_db from database (never open sqlite3 directly)
3. Use APIRouter() with a tag matching the filename
4. Return 404 with {"detail": "..."} for missing records
5. Return 200 for all execution endpoints — mock system never fails
6. End of file: comment block with curl examples for every endpoint

Prefix is applied in main.py — do not set prefix on the router itself.