# Vertex ERP

**A full retail management system, running in production every day at a real store with two branches.**

[Versão em português](README.md)

Point of sale, multi-store inventory, store credit ("fiado"), cash registers, payables and receivables, bank reconciliation and reports. It ships as a desktop app for the counter, an Android app and an iPhone web app for the owner, and a public storefront website. I designed, built and deployed it alone, and I maintain it in production.

![CI](https://github.com/anndreluizz/VertexERP/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6%20(Qt)-41CD52?logo=qt&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-02569B?logo=flutter&logoColor=white)

![Vertex ERP dashboard](docs/imagens/desktop-inicio.png)

## In numbers

| | |
|---|---|
| In production since | October 2026, one store with a head office and a branch |
| Development | Started July 2026: 380+ commits, 70+ merged pull requests |
| Code | ~110k lines (Python, Dart, TypeScript, PowerShell) |
| Automated tests | ~850: ~500 backend, ~300 desktop, ~50 mobile |
| Database migrations | 53 (Alembic), all of them applied to live store data without data loss |

## What it does

**Sales and cash register**
- Point of sale with barcode scanner, keyboard shortcuts, favorites, held sales and quotes
- Cash register opening and closing with counting, cash drops and top-ups, plus a detailed per-register PDF report
- Returns, cancellations and receipts on a thermal printer (ESC/POS) or over WhatsApp

**Customers and store credit**
- Customer file with statement, credit limit and balance owed
- Automatic rating (good payer, late payer, defaulter), payment receipts and collection reminders

**Finance**
- Payables with installments, recurring bills and boleto reading (typed line or PDF)
- Pix (Brazilian instant payments): reads the BR Code and fills in amount and payee
- Cash flow, bank reconciliation from OFX statements, and a business-intelligence screen

**Inventory and multi-store**
- One catalog with stock per store, transfers between stores and stock counts
- NF-e (electronic invoice) XML import and spreadsheet import

**Beyond the counter**
- Storefront website (Next.js, GitHub Pages) generated from the live catalog, with a shopping bag that sends the order over WhatsApp
- Android app (Flutter) and the same app as a web app for iPhone, reached over a private Tailscale network
- Users, permission profiles (admin and seller) and an audit log

## Screenshots

| Point of sale | Customer file |
|---|---|
| ![POS](docs/imagens/desktop-pdv.png) | ![Customer file](docs/imagens/desktop-ficha-cliente.png) |
| **Payables** | **Dark theme** |
| ![Payables](docs/imagens/desktop-contas-pagar.png) | ![Dark theme](docs/imagens/desktop-inicio-escuro.png) |

| App: home | App: customers | App: finance |
|---|---|---|
| ![App home](docs/imagens/app-inicio.png) | ![App customers](docs/imagens/app-clientes.png) | ![App finance](docs/imagens/app-financeiro.png) |

*Screenshots use fictitious test data.*

## Architecture

```
┌──────────────────────┐      HTTPS (TLS)       ┌───────────────────────────┐
│  Desktop (PySide6)   │ ─────────────────────▶ │  FastAPI                  │
│  counter, POS, branch│                        │  routes → services →      │
└──────────────────────┘                        │  repositories (SQLAlchemy)│
┌──────────────────────┐      HTTPS (TLS)       │                           │
│  Android / iPhone    │ ─────────────────────▶ │  JWT + refresh tokens,    │
│  (Flutter, Riverpod) │ ◀── push (FCM) ─────── │  permissions, audit log   │
└──────────────────────┘                        └─────────────┬─────────────┘
                                                              │
┌──────────────────────┐   catalog export       ┌─────────────▼─────────────┐
│  Storefront (Next.js)│ ◀───────────────────── │  PostgreSQL (Alembic)     │
└──────────────────────┘                        └───────────────────────────┘
```

- **Backend:** FastAPI, SQLAlchemy 2, Alembic and Pydantic, layered into routes, services and repositories.
- **Desktop:** PySide6 with its own design system (color and type tokens, light and dark themes). Every network call runs off the UI thread.
- **Mobile:** Flutter with Riverpod and Dio, an offline cache, Firebase Cloud Messaging, and a server certificate pinned on first use.

## Running a real store

These are the parts that only exist because the system is in production:

- **Automatic updates.** A merge to `main` builds a release on GitHub Actions. The store's launcher downloads it and checks its SHA-256. Before swapping anything, it backs up the database and keeps the previous version for rollback.
- **Backups.** Hourly dumps run with an integrity check, plus a daily copy to cloud storage.
- **Disaster recovery.** An emergency kit, mirrored to the cloud every day, turns any Windows PC into the store server. The last drill restored the live data in 31 seconds.
- **Self-healing launcher.** It starts a portable PostgreSQL and the API, and restarts the backend if it dies.
- **Production incidents become tests.** One example: the product screen froze at about 1,000 products because it created ~5,000 cell widgets. The fix builds rows only as they scroll into view (9 s down to 0.3 s), and a regression test now covers it.

## Quality

- **CI on every push:** the migrations run from an empty database to head, then the three test suites and Flutter static analysis.
- Backend tests run against a real PostgreSQL, and desktop tests run Qt offscreen.
- Every change to store data is preceded by a backup.

## Running locally

Requirements: Python 3.12 and PostgreSQL (Flutter for the app).

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows
pip install -r requirements.txt -r frontend/requirements.txt

cd backend                             # create .env (variables in backend/README.md)
alembic upgrade head
uvicorn main:app --reload              # API docs at /docs
```

In another terminal, run `cd frontend && python app.py`. On first launch, the setup screen creates the admin user.

Tests: `pytest` in `backend/` and `frontend/`, and `flutter test` in `mobile/`.

## Author

**Andre Luis Coelho Lopes**: design, development and deployment.

© 2026 Andre Luis Coelho Lopes. All rights reserved. The code is public for reference only (see [LICENSE](LICENSE)).
