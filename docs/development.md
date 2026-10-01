# Development

Target: Odoo Community 20.0, Python 3.12 and PostgreSQL 17. The build pins the official Odoo source to `17ff827a18248397342e73bb2bcac48e2b8e1027`; update that revision deliberately and rerun the suite.

## Local setup

Use an isolated virtual environment and install Odoo's own `requirements.txt`. Set `ODOO_SOURCE` to the checkout, and configure PostgreSQL in `~/.odoorc` or through CLI options. Never commit database credentials.

VS Code has a debug configuration in `.vscode/`. In PyCharm, select the virtual environment and run `odoo-bin` with the same arguments.

```sh
export ODOO_SOURCE=/path/to/odoo
export PGUSER=odoo PGPASSWORD=your-local-password
bash scripts/test.sh
```

Tests install the addon in a disposable PostgreSQL database. Do not point `ODOO_TEST_DATABASE` at an existing business database.

## Structure

- `addons/trustgate/models`: ORM fields and business methods.
- `addons/trustgate/views`: native XML views.
- `addons/trustgate/static/src`: Owl field component and template.
- `addons/trustgate/tests`: Odoo transaction tests.

Use the ORM for business data and let Odoo manage sessions, access control and transactions. There is no separate API service or database schema migration framework.

The Docker image is a development environment. PDF rendering tools, outgoing mail and production deployment are outside its scope. Start with a fresh database; importing data from another application requires a separate migration.

References: [Odoo source](https://github.com/odoo/odoo/tree/20.0), [release requirements](https://github.com/odoo/odoo/blob/20.0/odoo/release.py).
