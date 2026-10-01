"""Check that the initialized Odoo database serves the login page."""
import http.client
import time
import urllib.error
import urllib.request

for attempt in range(30):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8069/web/login", timeout=5) as response:
            page = response.read().decode()
            if response.status == 200 and 'name="login"' in page and 'name="password"' in page:
                print("Odoo login page is ready")
                break
    except (urllib.error.URLError, OSError, http.client.HTTPException):
        pass
    time.sleep(2)
else:
    raise SystemExit("Odoo did not serve the login page within the startup deadline")
