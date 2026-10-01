FROM python:3.12-slim-bookworm
ARG ODOO_REVISION=17ff827a18248397342e73bb2bcac48e2b8e1027
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential libldap2-dev libsasl2-dev libpq-dev libxml2-dev libxslt1-dev libjpeg62-turbo-dev zlib1g-dev libffi-dev libssl-dev libmagic1 postgresql-client ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git init /opt/odoo && cd /opt/odoo && git remote add origin https://github.com/odoo/odoo.git && git fetch --depth 1 origin "$ODOO_REVISION" && git checkout --detach FETCH_HEAD
RUN pip install --no-cache-dir -r /opt/odoo/requirements.txt
RUN useradd --create-home odoo && mkdir /var/lib/odoo && chown odoo:odoo /var/lib/odoo
COPY --chown=odoo:odoo addons /mnt/extra-addons
USER odoo
EXPOSE 8069
ENTRYPOINT ["python", "/opt/odoo/odoo-bin"]
CMD ["--addons-path=/opt/odoo/addons,/mnt/extra-addons", "--data-dir=/var/lib/odoo"]
