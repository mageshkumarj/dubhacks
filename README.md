# T-Mobile Hackathon Sandbox

A mock wireless commerce and customer-context platform for building recommendation engines.

> **All data is synthetic stub data.** SKUs, prices, promotions and customers are invented for this
> hackathon. Nothing here is an official offer, real customer data, or a real T-Mobile system.

## Prerequisites

| You need | Details |
|---|---|
| **Python 3.11 or newer** | Check with `python3 --version` (`python --version` on Windows). It must include `venv` and `pip`, which the installers from [python.org](https://www.python.org/downloads/) do. On Debian or Ubuntu, also run `sudo apt install python3-venv`. |
| **Internet on the first run** | The first start downloads three packages (FastAPI, Uvicorn, Pydantic) from PyPI. After that it works offline. On a network with TLS inspection, set `PIP_CERT=/path/to/ca-bundle.pem` before running. |
| **Port 8000 free** | Use another port with `PORT=8001 ./run.sh`. |
| **A terminal** | bash or zsh on macOS and Linux, PowerShell on Windows. If Windows blocks the script, run `powershell -ExecutionPolicy Bypass -File .\run.ps1`. |

That is all. You do **not** need Docker, a database server, Node.js, an API key, an account, or admin rights.
Git is only needed to clone the repository; you can download it as a ZIP instead.

## Quickstart (about 2 minutes)

```bash
git clone <this-repo-url> && cd tmobile-sandbox
./run.sh            # macOS / Linux
.\run.ps1           # Windows (PowerShell)
```

Then open **http://localhost:8000/docs**. The script creates a virtual environment, installs
dependencies, and starts the API. The dataset ships pre-generated in `data/sandbox.db`.

Check it works: `curl http://localhost:8000/health`

For a thorough check of every endpoint (about 5 seconds, nothing extra to install, safe to repeat):
`python scripts/smoke_test.py` (add `--full` to check every account, or `--base-url https://...` for a hosted instance).

## What is in the sandbox

| Layer | What it models |
|---|---|
| Commerce | devices, plans, add-ons, promotions, trade-in value curves |
| Customer and context | accounts/households, lines, usage, billing, support interactions, risk signals |

About 5,000 accounts and 12,000 lines, plus **10 persona accounts** (`ACC-PERSONA-01` to `-10`) that
every team can demo against: a student, a family of five, an upgrader, an at-risk couple, an
overpaying household, a small business, a just-upgraded customer, retirees, a power user, and a
loyal bundled family. See [docs/data-dictionary.md](docs/data-dictionary.md).

## Customer and context API (v1)

A "customer" is an account (household). IDs look like `ACC-PERSONA-02` or `ACC-00042`. Try the personas first.

| Endpoint | What you get |
|---|---|
| `GET /v1/accounts?segment=&persona_only=&limit=&offset=` | Browse households (paginated) |
| `GET /v1/households/{account_id}` | Who is on the account: lines, plans, devices, add-ons, services |
| `GET /v1/customers/{account_id}/context` | **The one call that matters:** plan, devices, financing, upgrade and trade-in eligibility, estimated trade-in value, recent usage, billing trend, support friction, risk signals |
| `GET /v1/customers/{account_id}/usage?line_id=&months=` | Monthly usage per line (up to 12 months) |
| `GET /v1/customers/{account_id}/billing` | Monthly bills with change vs prior month |
| `GET /v1/customers/{account_id}/support-interactions?limit=` | Recent support contacts, newest first |

```bash
curl http://localhost:8000/v1/customers/ACC-PERSONA-03/context
```

Every response uses one envelope: `{"success", "data", "error", "meta", "data_source"}`. Lists carry
`meta: {total, limit, offset}`. Money is in cents. Commerce is below.

## Personas: 50 ready-made people for the five themes

Start from a persona instead of from nothing. There are 50, **ten per theme**: 42 existing customers
(`ACC-PERSONA-01` to `ACC-PERSONA-42`) and 8 prospects who are not customers yet (`PROSPECT-01` to `PROSPECT-08`).

| Theme | Example question the personas pose |
|---|---|
| `cart_whisperer` | The cart has a phone and nothing else. What would genuinely help this customer? |
| `matchmaker` | A prospect states lines, budget and usage. Which plan and phone fit? |
| `next_best_moment` | Who is drifting towards leaving, who is a false alarm, and what proportionate action fits? |
| `timekeeper` | Should this customer upgrade now, or wait? |
| `household_optimizer` | Is this household (or pair of households) arranged in the cheapest sensible way? |

```bash
curl "http://localhost:8000/v1/personas?theme=timekeeper"
curl "http://localhost:8000/v1/personas/ACC-PERSONA-11"      # includes a starting_cart you can send to /v1/cart
curl "http://localhost:8000/v1/customers/ACC-PERSONA-11/context"
```

Each persona has a `title` and a `scenario` that describe the situation. They never state the right answer, and the
judging answers are not in this repository. The other ~5,000 accounts are there for testing at scale.

## Commerce API (v1)

| Endpoint | What it does |
|---|---|
| `GET /v1/catalog/devices`, `/devices/{sku}`, `/plans`, `/plans/{sku}`, `/addons` | Browse the catalog (filter devices by `tier`, add-ons by `kind`) |
| `GET /v1/promotions?account_id=&cart_id=` | Every promotion with `eligible` and **`reasons`** why not |
| `GET /v1/tradein/value?device_sku=&age_months=&condition=` | Trade-in value (`good`, `fair`, `poor`) |
| `GET /v1/tradein/curve/{sku}` | Value by device age, 0-60 months (for "when should I trade in?") |
| `POST /v1/financing/quote` | Installment quote for 12, 24 or 36 months, by credit tier or `account_id` |
| `POST /v1/cart`, `GET /v1/cart/{id}` | Create a cart (anonymous or for an account) and read it with totals |
| `POST /v1/cart/{id}/items`, `DELETE /v1/cart/{id}/items/{item_id}` | Add or remove `device`, `plan`, `new_line`, `addon` or `tradein` items |
| `POST /v1/checkout` | Mock order. Needs an `Idempotency-Key` header; replays return the same order |

```bash
curl -X POST localhost:8000/v1/cart -H 'content-type: application/json' -d '{"account_id":"ACC-PERSONA-03"}'
curl -X POST localhost:8000/v1/cart/CART-.../items -H 'content-type: application/json' \
     -d '{"kind":"device","sku":"TMO-STUB-DEV-0002"}'
```

**How the stub pricing works** (so you can reason about it, and explain it in your demo):
- A financed device (the default) charges the minimum down payment for the customer's credit tier today
  and the rest monthly over 24 months. `prime` is 0% APR with nothing down; `near_prime` is 4.9% with 10%
  down; `subprime` is 9.9% with 20% down. `"payment": "full"` charges the whole price today.
- Trade-in credit from `tradein` items is applied to the **first device** in the cart. Anything left over is
  reported as `tradein_credit_unapplied_cents`. A `tradein` item takes its device from the line you name.
- A `plan` item charges the **difference** from the line's current plan. A `new_line` item is priced by its
  position in the household using the plan's published per-line table (each extra line costs less).
- Device protection must cover a real phone, and the tier must match it. Name the line (`line_id`) to protect the phone
  it has (or the new phone you are putting on that line), or leave `line_id` out to protect an uncovered phone already in
  the cart. A mismatch gives `PROTECTION_TIER_MISMATCH`, a cart with no phone gives `INVALID_ITEM`, covering a phone twice
  gives `DUPLICATE_ITEM`, and checkout rejects protection whose phone was removed (`PROTECTION_UNMATCHED`).
  The streaming add-on needs a More or Beyond plan and the Beyond connected-device line needs a Beyond plan
  (`ADDON_NOT_ELIGIBLE`). Accessories list the devices they fit in `compatible_device_skus`.
- Discount plans (55+, Partner, Community) are sold only to accounts with a matching `discount_group`;
  55+ and Saver plans allow at most 2 lines and the Essentials 4 Line Offer needs 4 or more (`PLAN_NOT_ELIGIBLE`,
  `PLAN_LINE_LIMIT`).
- `GET /v1/promotions` returns every offer with `eligible`, the `reasons` it is not, and `estimated_savings_cents`.
  Eligibility depends on the customer (segment group, tenure, credit tier, device age, recent support contacts),
  the cart (new line, `port_in`, trade-in, device, plan, add-ons, accessories) and the offer's own limits.
  `GET /v1/catalog/promotions` lists the rules; `source=stub` are invented retention offers.
- At checkout, `promo_skus` must be eligible. Only one device-attached offer can apply per device. Savings are reported in `promo_savings_cents`
  (an open-ended monthly credit counts for 12 months) and are **not** subtracted from the totals.
- A line's device can be traded in **once** per server run. `monthly_cents` can be negative (a plan downgrade).
- `Idempotency-Key` is scoped to the cart. Replaying with the same `promo_skus` returns the same order;
  different `promo_skus` return `409 IDEMPOTENCY_MISMATCH`. Request bodies are capped at 64 KB.
- Carts and orders live **in memory** and reset when the server restarts. Nothing is ever charged.

> Upgrade eligibility in this sandbox is a stub rule: the device has been owned for 12+ months (half of a 24-month installment plan).

## Regenerate the data (optional)

```bash
python -m datagen --seed 2026 --accounts 5000 --out data/sandbox.db
```

The same seed produces the same data on any machine. `metadata.content_sha256` is a checksum of all
data rows so you can verify your copy (file bytes can differ between SQLite versions).

## Troubleshooting

- **pip SSL errors on a corporate or school network**: set `PIP_CERT=/path/to/ca-bundle.pem` and retry.
- **Wrong Python version**: install 3.11+ or run `PYTHON=/path/to/python3.12 ./run.sh`.
- **Database on a Windows network share (UNC path)** is not supported; keep the project on a local drive.
- **Port in use**: `PORT=8001 ./run.sh`.

## For organizers

Held-out churn labels come from a **private model file that never goes in this repo**. The toy model in
`datagen/reference_model.py` is public, so it is for tests and dry runs only. Anyone can read it.

```bash
export LABEL_SALT="$(python -c 'import secrets; print(secrets.token_hex(32))')"   # keep secret
python -m datagen --labels-out private/labels.json --label-model private/model.py
```

- Labels are computed from the **existing** `data/sandbox.db`, opened read-only. Nothing is rebuilt, and your model
  cannot write to the dataset. Never commit a regenerated database that a private model has touched.
- `private/model.py` must define `probability(account_id, features, conn) -> float`. It may query `conn`
  for extra signals and should differ structurally from the public features, not just in coefficients.
- Labels can only be written to `private/` or outside the repo. Salts under 32 characters are rejected.
- The labels file stores a SHA-256 of the model, never its parameters.
- Exclude `ACC-PERSONA-*` accounts from scoring. Their notes describe their situation.
- Before publishing: `git ls-files | xargs grep -l churned_90d` must print nothing.
