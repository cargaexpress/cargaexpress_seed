# CargaExpress seed

A command that fills the database with mock data. The data is realistic, always
the same for the same settings, and safe to run many times.

## 1. What it does and why it exists

The seed creates brands, carriers, distribution centers, orders, guides,
tracking events, SLA results, penalties, settlements and carrier compliance.

It exists so that every developer has the same dataset from day one, and so we
can test the business rules (RN-01 to RN-10) and the data-quality checks
without waiting for real data.

## 2. How to run it

Start the local database (once), install the packages and run the seed:

```bash
docker compose up -d                       # PostgreSQL on localhost:5432
python -m venv .venv
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m seed --size small --seed 42
```

The command creates the tables if they do not exist, so no manual SQL or
inserts are needed.

### Options

| Option | Meaning | Default |
|---|---|---|
| `--size` | `small`, `medium` or `large` | `small` |
| `--seed` | any integer, makes the data reproducible | `42` |
| `--defects` | comma-separated list of data-quality defects | none |
| `--database-url` | database to use | `DATABASE_URL` variable, or the Docker database |
| `--reset` | **drops and recreates the CargaExpress tables first** | off |

### Examples

```bash
python -m seed --size small --seed 42
python -m seed --size medium --seed 42 --defects mixed_dates,out_of_order_events
python -m seed --size large  --seed 7  --defects duplicate_webhooks,invalid_tracking
python -m seed --size small  --seed 42 --reset      # start again from zero
```

## 3. Volumes

| Size | Brands | Orders (total) | Records touched by each defect |
|---|---|---|---|
| `small` | 5 | 100 | 5 |
| `medium` | 20 | 2,000 | 25 |
| `large` | 60 | 20,000 | 100 |

Always the same: 12 carriers (5 type A, 4 type B, 3 type C), 9 distribution
centers, 9 regions, 3 shipping types. "Orders" includes the 12 fixed scenario
orders. An order has 1 to 3 guides.

## 4. Fixed scenario orders

Orders whose reference starts with `SCN-` always exist, with the same dates, for
every size and seed. They are the "controlled cases" of the business rules.

| Reference | Case |
|---|---|
| `SCN-01` | normal dispatch, delivered inside the SLA |
| `SCN-02` | dispatch Friday 17:00 (after 16:00) with a Monday holiday (the CA-02 example) |
| `SCN-03` | late delivery, carrier responsible (penalty passed to the carrier) |
| `SCN-04` | dispatch took 54 h, CD responsible |
| `SCN-05` | wrong-address NOVEDAD, brand responsible (no penalty) |
| `SCN-06` | one order with 2 guides: one on time, one late (RN-07) |
| `SCN-07` | an event arrives after ENTREGADO (RN-02) |
| `SCN-08` | dispatched on a Saturday, 14 business hours to the deadline, still EN_TRANSITO: at risk |
| `SCN-09` | same dates as SCN-08 but already EN_REPARTO: not at risk |
| `SCN-10` | NOVEDAD open for 16 hours: at risk |
| `SCN-11` | dispatched on a public holiday |
| `SCN-12` | CD in Mexico, destination Peru: the destination calendar is used |

Carrier 12 stays under 85% compliance for two consecutive half-months and is
`EN_REVISIÓN` (RN-09). Carrier 11 has only one bad period and stays `ACTIVO`.

## 5. Defects

Enable them with `--defects name1,name2`. Every defect is deterministic, touches
only a few records and is marked inside `raw_event.payload` with the key
`"seed_defect"`. Normal data is never changed by a defect.

| Defect | What it creates | How to find it |
|---|---|---|
| `mixed_dates` | the date inside the raw message uses another format (`dd/mm/yyyy HH:MM`, `mm-dd-yyyy HH:MM`, epoch seconds, `yyyymmddHHMMSS`) | `payload.seed_defect = "mixed_dates"` |
| `out_of_order_events` | two events of a guide are received in the wrong order; the late one has `es_anomalia = true` | `payload.seed_defect = "out_of_order_events"` |
| `duplicate_webhooks` | a repeated webhook message from a type A carrier (extra field `"retry": 1`) | `payload.seed_defect = "duplicate_webhooks"` |
| `invalid_tracking` | messages for guides that do not exist (`INVALID-000001`...) plus `unmatched_event` rows | `numero_guia` starts with `INVALID-` |

Not implemented: `repeated_headers`. It only exists inside Excel/CSV files, and
this seed fills database tables. The command rejects it with a clear message.

Note about `duplicate_webhooks`: `raw_event.hash` is UNIQUE, so an identical copy
could not be stored. The duplicate has an extra `retry` field, so its hash is
different. No second `tracking_event` is created for it.

## 6. How reproducibility works

- One `--seed` number feeds every random choice.
- Each order has its own random generator (`"<seed>:order:<number>"`), so an
  order never depends on how many orders were built before it.
- The code never calls `datetime.now()` or `uuid4()`. "Now" is fixed in
  `seed/config.py` (`REFERENCE_NOW = 2026-07-01 15:00 UTC`).
- IDs come from counters (`1, 2, 3...`). Tracking numbers look like
  `G05-0000123`. The `raw_event.hash` is a SHA-256 of the message.
- Same size + same seed + same defects = the same rows.

## 7. How idempotency works

- All IDs are deterministic, and the tables already have UNIQUE constraints
  (`brand_id + referencia_marca`, `carrier_id + numero_guia`, `hash`, ...).
- Every insert is `ON CONFLICT DO NOTHING`: rows that already exist are skipped.
  Existing rows are never updated or deleted.
- Everything is written in one transaction.
- The database is only dropped if you pass `--reset`.

**Rule: one database = one size + one seed + one set of defects.** If you run the
seed with another size or seed on the same database, rows with the same ID are
kept as they are and the result is a mix. Use `--reset` to change settings.

After inserting, the seed moves the PostgreSQL ID counters, so the application
can insert new rows without ID conflicts.

## 8. Tests

```bash
pytest                    # everything
pytest -m "not slow"      # skips the "large" dataset test
pytest tests/test_5_defects.py -v
```

The tests use a temporary SQLite file, so Docker is not needed to run them.

| File | Checks |
|---|---|
| `test_1_basic_execution.py` | the command creates the whole dataset |
| `test_2_reproducibility.py` | seed 42 gives the same dataset twice |
| `test_3_idempotency.py` | running twice does not duplicate anything |
| `test_4_volumes.py` | small / medium / large have the configured size |
| `test_5_defects.py` | each defect creates its anomaly and is marked |
| `test_6_existing_data.py` | existing data is not overwritten, duplicated or deleted |
| `test_business_rules.py` | RN-01 to RN-10 can be tested with the seeded data |
| `test_calendar_utils.py` | business-day and cutoff math |

## 9. Test values (not defined by the project)

The project documents do not define these, so the seed uses test values:
the 3 countries (Colombia, Mexico, Peru), the holidays (a short sample, not an
official calendar), the SLA days (STANDARD 3, EXPRESS 2, ECONOMY 5, +1 for the
third region of each country), the penalty ranges (1-2 days 5%, 3-5 days 10%,
6+ days 20%), the 14 carrier status codes and the data volumes.
