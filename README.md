# SmartParcelCue

A parcel-delivery slot booking system built with Django. Students/residents
book a delivery time slot for an incoming parcel; the system prevents
overbooking a slot's capacity and can auto-assign an alternate slot when a
preferred one is full.

## Features

- Slot-based booking with configurable per-slot capacity
- **Race-condition-safe booking**: concurrent booking requests for the same
  slot are serialized with `select_for_update()` inside `transaction.atomic()`
  so two users can never both take the last seat in a slot
- Auto-assignment: if a user's preferred slot is full, the system looks for
  the next available overlapping slot
- Full booking lifecycle: Pending → Booked / Auto-Assigned → Delivered /
  Cancelled / Rescheduled
- Staff-only parcel status management via a custom Django admin (bulk
  "mark as delivered" action, recurring slot creation)
- **REST API** (`/api/`) built with Django REST Framework, covering slots
  and bookings, with the same concurrency-safe booking logic as the
  server-rendered flow
- 14 automated tests covering models, views, and the API (including the
  double-booking race condition)

## Tech stack

Django 5.2 · Django REST Framework · django-filter · SQLite (dev) ·
python-dotenv for environment-based configuration

## Project layout

```
smartparcel/     # project settings, root urls
parcels/         # server-rendered app: models, views, templates, admin
api/             # DRF serializers, viewsets, routers for /api/
```

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate      # .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env           # set DJANGO_SECRET_KEY etc.

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then visit `http://127.0.0.1:8000/` for the web app, `/admin/` for the
Django admin, and `/api/` for the REST API root.

## REST API

| Endpoint | Method | Notes |
|---|---|---|
| `/api/auth-token/` | POST | `{"username", "password"}` → DRF auth token |
| `/api/slots/` | GET | List slots (any authenticated user) |
| `/api/slots/` | POST | Create a slot (staff only) |
| `/api/bookings/` | GET | List your own bookings (staff see all) |
| `/api/bookings/` | POST | Book a slot; returns `409` if it just filled up |
| `/api/bookings/{id}/cancel/` | POST | Cancel your booking |
| `/api/bookings/{id}/mark_delivered/` | POST | Staff-only |

Authenticate API requests with either the Django session cookie or a token:

```
Authorization: Token <token from /api/auth-token/>
```

## Tests

```bash
python manage.py test
```

## Deploying (Render)

A `render.yaml` blueprint is included:

1. Push this repo to GitHub.
2. On Render: **New → Blueprint**, point it at the repo — it reads
   `render.yaml` and provisions the web service automatically, including a
   1GB persistent disk for the SQLite file and an auto-generated
   `DJANGO_SECRET_KEY`.
3. First deploy runs `collectstatic` + `migrate` automatically. Create an
   admin user afterward via the Render shell: `python manage.py createsuperuser`.

For Postgres instead of SQLite (recommended once you have real traffic),
add a Render Postgres instance and change the `DATABASES` block in
`settings.py` to read `DATABASE_URL` (e.g. via `dj-database-url`).

## Possible next steps

- Swap SQLite for Postgres in production (`DATABASES` already reads from
  env vars, so this is a config change, not a code change)
- Add Swagger/OpenAPI docs via `drf-spectacular`
- Containerize with Docker + a `docker-compose.yml` for one-command setup
- Deploy to Railway/Render and link a live demo here
