# ShelfPoa Web Admin

Two apps:

- `backend/` — FastAPI service. Serves ML-derived endpoints (recommendations,
  forecasts, basket rules, stock-outs, merchandiser performance).
- `frontend/` — React (Vite + Tailwind) admin console, styled to the Figma
  design tokens (dark `#2b2a33` background, `#f4784e` accent, Inter font).

## Security note (read first)

A Firebase **service account** private key was shared in chat while building
this scaffold. Treat it as compromised — the old key/service account should
already be revoked. For the new key:

1. Save it somewhere **outside this repo**, e.g. `../secrets/firebase-service-account.json`.
2. `chmod 600` it.
3. Point `backend/.env` (not `.env.example`) → `GOOGLE_APPLICATION_CREDENTIALS` at that path.
4. Never paste the key contents into chat, a file upload, or a commit —
   `.gitignore` in `backend/` already excludes `*.json` and `secrets/`.

## Database

ShelfPoa uses the Firebase **Realtime Database**, not Firestore. Current
top-level nodes: `audits`, `mt_groups`, `osa_reports`, `outlets_universe`,
`sos_audits`. `backend/app/core/firebase.py` wraps `firebase_admin.db` and
exposes `get_ref(path)` for reading any node.

`/api/outlets` already reads live from `outlets_universe` (it's master data,
not model output, so it isn't behind the mock/live toggle). The stockout and
merchandiser-performance routes have `live` branches sketched against
`osa_reports` / `sos_audits` / `audits`, but the exact field names inside
each node are a guess — open one record in the Firebase console and adjust
the `TODO`-marked mapping in the matching route file.

## Running it

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit ML_MODE, credentials path, etc.
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local   # fill in Firebase WEB config (public-safe values)
npm run dev
```

Visit http://localhost:5173. The app talks to the FastAPI service at
http://localhost:8000 for anything ML-derived, and will talk to Firestore
directly (via the Firebase JS SDK) once `.env.local` is filled in — that
wiring is stubbed out in `frontend/src/services/firebase.js`, ready to use
once you add real Firestore reads in the page components.

## Mock → live model swap

Every ML-backed route in `backend/app/api/routes/` checks `settings.ml_mode`:

- `mock` (default): returns synthetic responses shaped exactly like the real
  output, generated in `backend/app/services/mock_data.py` using your actual
  15-SKU Blueband universe and the 75-branch/11-sub-county scope.
- `live`: currently raises `NotImplementedError` with a `# TODO` marking
  exactly where to plug in the trained XGBoost / FP-Growth calls. When a
  model is ready, replace that one function body — the route signature,
  response schema, and every frontend call site stay unchanged.

Flip modes by setting `ML_MODE=live` in `backend/.env` once a given model is
wired up; you can do this per-endpoint by editing that route directly.
