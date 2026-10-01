# TrustGate

Supplier payment risk review inside Odoo. Requests use existing suppliers and bank accounts, receive an explainable risk score, and require an independent reviewer when the score reaches 50.

**Stack:** Odoo 20 · Python 3.12 · JavaScript/Owl · XML · PostgreSQL 17.

## Run locally

```sh
cp .env.example .env
# Set a local database password in .env.
docker compose build
docker compose run --rm odoo --addons-path=/opt/odoo/addons,/mnt/extra-addons --data-dir=/var/lib/odoo --db_host=db --db_user=odoo -d trustgate -i trustgate --without-demo=all --stop-after-init
docker compose up -d
```

Open http://localhost:8069. Sign in with `admin` / `admin` on the new development database and change that password. In developer mode, assign **TrustGate Operator** to requesters and **TrustGate Reviewer** to reviewers. Add a supplier bank account, then open **TrustGate → Payment Reviews**.

## Review rules

- New, recently edited or changed beneficiary account: +30.
- Amount above three times the supplier's approved average: +20; without history, use EUR 10,000 converted into company currency.
- Outside 08:00–18:00 weekdays in Brussels: +15.
- No approved request history: +15.

Requests below 50 are automatically approved. Other requests need a rationale from a reviewer who is not the requester. Submitted details and decisions cannot be edited through normal writes. Company access rules isolate records; PostgreSQL row locks serialize decisions. Odoo's chatter records status changes.

This is a review prototype, not a bank connector or an accounting payment block. The baseline uses approved review requests, not settled transactions. Account edit time is a conservative proxy for a recent beneficiary change; administrators retain database access. [Development and tests](docs/development.md).
