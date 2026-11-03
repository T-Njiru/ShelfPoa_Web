# ShelfPoa Web Platform

The administrator side of ShelfPoa, a shelf-intelligence system for Flora Food Group's Blueband SKUs in Nairobi modern-trade outlets. Merchandisers capture and analyse shelf photos in the Android app (`../ShelfPoa_mobile`); this platform lets administrators review the results and act on the model outputs.

- `backend/` is a FastAPI service that serves the machine-learning outputs: demand forecasts, recommendations, basket rules, stock-outs, merchandiser performance and shelf opportunities.
- `frontend/` is a React (Vite + Tailwind) admin console with four pages: Merchandiser performance, Recommendations, Recommendation maker and Stock-out alerts. Only accounts with the `admin` role can sign in.

General data is read and written directly in Firebase. FastAPI only serves model-derived results.

## Credentials

The Firebase service-account key must **never** be committed.

1. Download a key from the Firebase console (Project settings → Service accounts) and save it **outside this repo**, e.g. `..\secrets\firebase-service-account.json`.
2. Point `GOOGLE_APPLICATION_CREDENTIALS` in `backend/.env` at that path.

`.env` files and service-account JSON files are excluded by the root `.gitignore`. The Firebase **web** config in `frontend/.env.local` is not secret, but it is kept out of git too.

## Database

ShelfPoa uses the Firebase **Realtime Database** (project `planogram-adherance-ver-1`, region us-central1). The main nodes are:

| Node | Contents |
|---|---|
| `outlets_universe` | Outlets (`group_name`, `outlet_name`, sub-county) |
| `sos_audits` | Share of Shelf results submitted from the app |
| `osa_reports` | On-Shelf Availability results submitted from the app |
| `audits` | One record per store visit, linked to that visit's results by `audit_id` |
| `users`, `merchandisers` | Roles and merchandiser IDs (e.g. `m-10`) |

`backend/app/core/firebase.py` wraps `firebase_admin.db` and exposes `get_ref(path)`. Records tagged `source: "simulated"` are demo data written by the seed scripts below.

## Running it (Windows)

### Backend
```powershell
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # set ML_MODE, GOOGLE_APPLICATION_CREDENTIALS, FIREBASE_DATABASE_URL
uvicorn app.main:app --reload --port 8000
```
Check that it's up at http://127.0.0.1:8000/api/health. The interactive API docs are at http://127.0.0.1:8000/docs.

### Frontend
```powershell
cd frontend
npm install
copy .env.example .env.local   # fill in the Firebase web config
npm run dev
```
Open http://localhost:5173. To sign in, an account needs the admin role:
```powershell
cd backend
py -m scripts.make_admin you@example.com
```

## Mock and live modes

`ML_MODE` in `backend/.env` sets the mode for every ML route:

- `mock` (the default) returns synthetic responses in the same shape as the real output (`app/services/mock_data.py`).
- `live` loads the trained models from `app/ml/artifacts/` at start-up. If loading fails, the API falls back to mock instead of crashing. `/api/health` reports the active mode and whether the models loaded.

Route signatures and response schemas are the same in both modes, so the frontend doesn't change.

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | Mode and model status |
| GET | `/api/outlets` | Outlets from Firebase |
| GET | `/api/forecast?chain=&branch=&sku=` | Next week's XGBoost demand forecast. `branch` is the short name, e.g. `chain=Carrefour&branch=Mega` |
| POST | `/api/forecast/with-promo` | The same forecast for a planned promotion |
| GET | `/api/recommendations` | Restock and co-promotion recommendations |
| GET | `/api/basket/rules?sku=` | FP-Growth rules for a Blueband SKU |
| GET | `/api/stockouts` | Open stock-outs from submitted OSA reports |
| GET | `/api/merchandisers/performance` | SOS, OSA, compliance and visits per merchandiser |
| GET | `/api/shelf/opportunities?kind=sos\|planogram` | XGBoost what-if: sales gained by raising SOS or compliance to a target |

## Models and data

`backend/app/ml/artifacts/` contains:
- `demand_model_weekly.json`: the XGBoost demand model with shelf features.
- `demand_model_weekly_pre_shelf.json`: the sales-only comparison model.
- The FP-Growth rules, the outlet–sub-county mapping and the evaluation reports.
- The training datasets.

The sales, shelf-history and basket datasets are **simulated**, because per-SKU, per-outlet sales and shelf KPIs aren't currently recorded at this granularity. To retrain:
```powershell
python simulate_shelf_history.py
python train_xgboost_shelf.py
```
The YOLOv8n detector runs on the phone, not here (`ShelfPoa_mobile/.../assets/best_model.onnx`). The shelf images used to train it are proprietary and aren't included.

## Utility scripts (run from `backend/`)

Every seed script does a dry run unless you pass `--yes`, and `--purge --yes` removes the simulated records it wrote.

| Script | Purpose |
|---|---|
| `seed_outlets.py` | Adds the 75 Nairobi outlets to `outlets_universe` |
| `seed_osa_reports.py` | Simulated OSA readings |
| `seed_audits.py` | Simulated merchandisers, visits and SOS audits (run after `seed_osa_reports.py`) |
| `seed_merchandiser_users.py` | Login accounts for the simulated merchandisers |
| `link_merchandiser.py` | Turns a signed-up account into a merchandiser, e.g. `--email ... --name "..." --yes` |
| `scripts/make_admin.py` | Gives an existing account the admin role |
| `smoke_test.py` | Calls every endpoint against a running backend |
| `forecast_feedback_demo.py` | Shows the forecast responding to new sales without retraining |
