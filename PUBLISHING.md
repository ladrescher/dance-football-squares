# Publish the fundraiser at your own URL

This package is ready for deployment. It has NOT been deployed and no public URL has been created.

## What you need

- A Linux hosting server with Docker Engine and the Docker Compose plugin installed.
- A domain or subdomain you control, such as squares.your-domain.com.
- Access to edit its DNS records and open server ports 80 and 443.

A static website host cannot run this app: it needs a server and persistent storage for shared reservations. Use one app instance; do not scale it to multiple replicas. Docker Compose runs the app behind Caddy, which obtains and renews HTTPS certificates once DNS and ports are configured.

## Files provided

- Dockerfile: builds the app container.
- compose.yaml: runs the app, HTTPS proxy, and persistent storage.
- Caddyfile: routes your hostname to the app and enables HTTPS.
- .env.example: template for your domain and private organizer key.
- fundraiser-settings.json: current public fundraiser settings, used only on first start.
- server.py, excel_export.py, static/: application source.

The package excludes supporter data, local databases, backups, and your current organizer key. A new installation starts with one empty Board 1. Existing hosted databases retain their own settings during app updates.

## Publish

1. Extract the ZIP and upload its bills-squares folder to your server. Open a terminal in that folder.
2. Create an A record for your chosen hostname pointing to the server's public IPv4 address. Only add an AAAA record if the server has working IPv6. Allow inbound TCP ports 80 and 443. Do not expose app port 8000 publicly.
3. Copy the environment template:

       cp .env.example .env
       chmod 600 .env

4. Edit .env. Replace DOMAIN with your bare hostname, without https:// or a trailing slash. Replace ADMIN_TOKEN with a long, unique secret. Do not use the example value. The local organizer key is not bundled; configure your chosen hosted key here. Keep .env private.
5. Build and start:

       docker compose up -d --build

6. Check health and logs:

       docker compose ps
       docker compose logs --tail=80 app proxy

7. Once the app is healthy and the proxy has issued its certificate, open https:// followed by your configured DOMAIN. That is the shareable URL. DNS propagation and certificate issuance can take time. If HTTPS fails, check DNS, ports, and the proxy logs.

Do not share logs or the output of `docker compose config` without reviewing them for secrets.

## Before sharing

Unlock Organizer with the key set on the host. Verify the headings, team colors, game date, price, payment recipient, payment instructions, and payout rules. Make a test reservation with contact information, confirm the payment status manually, and download Excel. Reset the fundraiser after testing through its two confirmation prompts; then verify that Board 1 is empty and open.

The Venmo link is best-effort prefilling, not a payment processor. Verify the real recipient and note on your phone before sharing. Payments, refunds, winner notifications, the one-hour cancellation deadline, number drawing, and adding boards remain manual organizer tasks. No automatic deadline enforcement is included.

This is a small-fundraiser prototype using Python's basic HTTP server behind an HTTPS reverse proxy, a shared organizer key, and SQLite. It does not include individual organizer accounts, automated rate limiting, or bot protection. Those are appropriate upgrades for a larger public launch.

## Storage, backups, and updates

The fundraiser_data Docker volume stores the database and reset backups; caddy_data stores HTTPS certificate state. Ordinary restarts and `docker compose down` preserve these volumes. Do not use `docker compose down -v`: it deletes persistent volumes and fundraiser data.

Reset backups are created only when a reset is performed. Schedule regular host-level backups of the fundraiser_data volume and test restoration. For a consistent manual database copy, create it using SQLite's backup function while the service is running:

       docker compose exec -T app python -c "import sqlite3; source=sqlite3.connect('/data/board.db'); dest=sqlite3.connect('/data/manual-backup.db'); source.backup(dest); dest.close(); source.close()"
       docker compose cp app:/data/manual-backup.db ./fundraiser-backup.db

Store downloaded backups securely: they contain supporter contact information. Restoration should be done with the app stopped, replacing /data/board.db with the selected backup. Keep another copy of the current database first. Restart the app and check the board before reopening sales.

For source updates, replace the application files while keeping .env, then run `docker compose up -d --build`. Do not overwrite volumes. Changes to fundraiser-settings.json only affect a new database; edit an existing fundraiser through Organizer.

## Other container hosts

You may deploy the Dockerfile alone on a host that supplies its own HTTPS URL. Set ADMIN_TOKEN, REQUIRE_ADMIN_TOKEN=1, PORT=8000, and DATABASE_PATH=/data/board.db. Attach persistent storage at /data and run one replica. Use the host's HTTPS routing; do not also run the included Caddy proxy there unless it is specifically supported. If the host cannot provide persistent storage, this SQLite version is not suitable for it.

## Reference documentation

- Caddy HTTPS: https://caddyserver.com/docs/automatic-https
- Docker environment configuration: https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/
