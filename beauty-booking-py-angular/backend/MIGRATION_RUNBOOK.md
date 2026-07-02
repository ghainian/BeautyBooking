# BeautyBooking Python Cutover Runbook (App Service Slots)

This runbook is for zero-downtime migration from ASP.NET production to FastAPI + Angular on the same Linux App Service using deployment slots.

## 1) Build and package

1. Build Angular frontend:
   - From `beauty-booking-py-angular/frontend`
   - `npm ci`
   - `npm run build`
2. Ensure generated frontend output is copied into `beauty-booking-py-angular/backend/frontend-dist`.
3. Confirm backend dependencies:
   - `pip install -r requirements.txt`

## 2) Required App Service startup command

Use this startup command for Python App Service Linux:

`gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT`

## 3) Route parity redirects implemented

Route parity redirects are also active:

- `/contact` -> `/home#hours-contact`
- `/gallery` -> `/home#gallery`
- `/services` -> `/home#services`
- `/price` -> `/home#services`

## 4) Staging validation before swap

1. Health:
   - `GET /api/health` returns status ok.
2. Route checks:
   - `/`, `/home`, `/book`, `/book/elev`, `/contact`, `/gallery`, `/services`, `/price`, `/thanks`
3. Language checks:
   - `/home?culture=da&ui-culture=da`
   - `/home?culture=en&ui-culture=en`
   - `/home?culture=fr&ui-culture=fr`
   - `/home?culture=de&ui-culture=de`
   - `/home?culture=zh&ui-culture=zh`

## 5) Swap and rollback

1. Swap staging -> production during low traffic.
2. Monitor for 30-60 minutes:
   - 5xx rate
   - response latency
3. If thresholds fail, swap back immediately.

## 6) Azure CLI command examples

Replace placeholders before use.

```powershell
az webapp deployment slot swap --resource-group <rg> --name <app-name> --slot staging --target-slot production
```

```powershell
az webapp log tail --resource-group <rg> --name <app-name> --slot staging
```
