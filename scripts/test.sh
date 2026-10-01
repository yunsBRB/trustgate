#!/usr/bin/env bash
set -euo pipefail
: "${ODOO_SOURCE:?Set ODOO_SOURCE to the Odoo 20 source directory}"
python "$ODOO_SOURCE/odoo-bin" --addons-path="$ODOO_SOURCE/addons,$PWD/addons" \
  --db_host="${PGHOST:-localhost}" --db_user="${PGUSER:-odoo}" \
  --db_password="${PGPASSWORD:?Set PGPASSWORD}" -d "${ODOO_TEST_DATABASE:-trustgate_test}" \
  -i trustgate --without-demo=all --test-enable --test-tags=/trustgate \
  --stop-after-init --http-port=8079 --log-level=test
