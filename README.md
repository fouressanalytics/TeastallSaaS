# Tea Stall Order Calculator — multi-tenant version

Every shop owner signs up with their own email/password. Each account has
its own menu items, prices, category assignments, and payment QR photo —
fully isolated from every other shop, stored in one shared Postgres
database on your VPS.

## What's in here

```
teastall-saas/
  docker-compose.yml     # Postgres + the FastAPI app, one more service behind Traefik
  .env.example            # copy to .env and fill in
  backend/
    Dockerfile
    requirements.txt
    app/
      main.py              # all API routes
      models.py            # users + items tables
      schemas.py
      auth.py               # password hashing + JWT
      database.py
  frontend/
    index.html             # login/signup + the calculator UI, talks to the API
```

## How it fits your existing setup

You're already running several Odoo instances on a Hostinger VPS with
Docker Compose behind Traefik (`odoo-3frd`, `odoo-depearl`, `veekay`,
`soroor`, `elegance`, `goodone`). This is just one more Compose project
on the same box, joining the same Traefik network.

## Password resets

Shop owners can tap **"Forgot password?"** on the login screen, enter
their email, and get a reset link (valid for 1 hour). Following the link
opens the same page with a "set new password" form.

For this to actually deliver email, fill in the `SMTP_*` variables in
`.env`:
- Hostinger gives you SMTP credentials under **hPanel → Emails** for any
  mailbox on your domain, or
- use a transactional email provider (SendGrid, Mailgun, Brevo, etc.) —
  better deliverability at scale than a shared-hosting mailbox once
  you're sending resets for thousands of users.

If `SMTP_HOST` is left blank, the reset link is only written to the
`api` container's logs (`docker compose logs api`) — fine for testing,
but real users obviously need the real email to arrive.

Also set `FRONTEND_URL` in `.env` to your real subdomain (e.g.
`https://teastall.yourdomain.com`) — it's what gets used to build the
link inside the reset email.

## First-time deploy

1. Copy `.env.example` to `.env` and fill in a real `DB_PASSWORD`,
   `SECRET_KEY`, `FRONTEND_URL`, and SMTP settings (see "Password
   resets" above).
2. Open `docker-compose.yml` and adjust the three marked lines:
   - the external Traefik network name (match what your other
     `odoo-*` containers join)
   - the subdomain in the `Host()` rule (e.g. `teastall.yourdomain.com`)
   - the `certresolver` name (match your existing Traefik config)
3. From the `teastall-saas` folder on the VPS:
   ```
   docker compose up -d --build
   ```
   Postgres tables are created automatically on first boot — no manual
   migration step needed for this version.
4. Point a DNS A record for your chosen subdomain at the VPS, same as
   you've done for the other client subdomains.

## How a shop owner uses it

1. Visits your subdomain, taps **"New shop? Create an account"**, enters
   a shop name, email, and password.
2. Adds their menu items (name, category, price, optional photo) and
   uploads a photo of their UPI/payment QR code from **Settings**.
3. That's it — from then on they just log in and use the same tap-to-add
   order calculator as before. Everything they set up is saved on the
   server, tied to their account, and shows up the same way on any
   device they log in from.

## Notes on scale and safety

- Passwords are hashed with bcrypt, never stored in plain text.
- Uploaded images (QR codes, item photos) are saved to a Docker volume
  (`teastall_uploads`) rather than the database, so the DB stays small
  even with thousands of shops.
- For thousands of active shops you may eventually want to move image
  storage to Hostinger's object storage or a CDN instead of local disk —
  the current setup works fine to start and can be swapped later without
  changing the frontend.
- This version creates tables automatically on startup. Once you're in
  production with real user data, switch to a proper migration tool
  (Alembic) before changing the schema again, so existing shops' data
  isn't touched by accident.
- Reset tokens are single-use and expire after 1 hour; the endpoint
  always replies with the same message whether or not the email exists,
  so it can't be used to check who has an account.
