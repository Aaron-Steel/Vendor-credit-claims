# Deploying Vendor Credit Claims — shared username/password (no SSO)

End state: `https://claims.yourcompany.com` → Caddy (HTTPS) → the app, which shows its own
styled **/login** page and checks a shared username/password. Anyone you give the shared
credentials to can get in. n8n keeps running untouched. Data (SQLite DB + uploaded files)
lives in `data/` on the droplet.

> **Already running the older basic-auth version?** See "Migrating from Caddy basic_auth"
> at the bottom — it's a 3-line change (env vars in, `basic_auth` block out).

> This is the quick "let a couple of people test it" path. When you're ready for proper
> per-person Microsoft logins, switch to `DEPLOY.md` (the Entra SSO version) — it reuses
> the same app container.

Do the steps in order. You'll collect: a subdomain, the droplet IP, Caddy's docker
network name, and the Caddyfile path inside the Caddy container.

---

## 1. DNS — point a subdomain at the droplet

In your DNS provider add an **A record**:

| Type | Name      | Value (points to)   |
|------|-----------|---------------------|
| A    | `claims`  | `170.64.200.224`    |

(Full host becomes `claims.yourcompany.com`.) Give it a few minutes, then verify:

```bash
ping claims.yourcompany.com      # should show 170.64.200.224
```

Caddy can't get an HTTPS certificate until this resolves to the droplet.

---

## 2. Get the code onto the droplet

SSH in (`ssh root@170.64.200.224`), then clone from GitHub:

```bash
mkdir -p /opt && cd /opt
git clone https://github.com/Aaron-Steel/Vendor-credit-claims.git vendor-credit-claims
cd vendor-credit-claims
```

(If the repo is private, git will prompt for your GitHub username + a personal access
token as the password. Or make a deploy key — but a one-off token paste is fine.)

---

## 3. Find Caddy's container name and docker network

The app container must join the same docker network Caddy is on so Caddy can reach it.

```bash
docker ps                                      # find the caddy container name
CADDY=$(docker ps --filter name=caddy -q)      # grab its id
docker inspect $CADDY -f '{{json .NetworkSettings.Networks}}'   # network name(s)
docker inspect $CADDY -f '{{json .Mounts}}'                     # where the Caddyfile lives
```

- Note the **network name** (commonly `root_default`) — goes in `.env` as `CADDY_NETWORK`.
- Note the **Caddyfile path** on the host (the `Source` of the mount whose `Destination`
  is something like `/etc/caddy/Caddyfile`) — you'll edit that file in step 6.

---

## 4. Configure and start the app

```bash
cd /opt/vendor-credit-claims/deploy
cp .env.basic.example .env
nano .env            # set CADDY_NETWORK, APP_USERNAME, APP_PASSWORD, APP_SECRET (see step 5)

docker compose -f docker-compose.basic.yml up -d --build
docker compose -f docker-compose.basic.yml logs -f    # watch it start; Ctrl-C to stop watching
```

On first start the app builds its product/retailer seed from the template, creates the
database, and starts serving on port 8000 inside the network (not exposed to the internet).

---

## 5. Set the shared login

Auth lives in the app now — no bcrypt hashing, no Caddy directive. In `deploy/.env` set:

```
APP_USERNAME=macgear                  # what testers type
APP_PASSWORD=ChooseAStrongSharedPassword
APP_SECRET=<paste output of: openssl rand -hex 32>
```

- `APP_SECRET` signs the login cookie. Use a long random string and keep it stable —
  changing it just signs everyone out (no data impact).
- If `APP_PASSWORD` is left blank the app **disables** auth — only do that for local dev.

After editing `.env`, apply it:

```bash
docker compose -f docker-compose.basic.yml up -d
```

---

## 6. Add the subdomain to Caddy

Edit the Caddyfile from step 3 and append (see `Caddyfile.basic.snippet`) — note there's
**no `basic_auth` block**, the app handles login itself:

```
claims.yourcompany.com {
    reverse_proxy claims:8000
}
```

Reload Caddy (no downtime). Use the Caddyfile path **inside** the container
(usually `/etc/caddy/Caddyfile`):

```bash
docker exec $CADDY caddy reload --config /etc/caddy/Caddyfile
```

Caddy fetches a Let's Encrypt certificate for the subdomain automatically.

---

## 7. Test

Open `https://claims.yourcompany.com` → the app's **/login** page appears → enter the
`APP_USERNAME` / `APP_PASSWORD` from `.env` → you land on the dashboard. "Sign out" is in
the top nav. Share that username/password with your testers.

---

## Day-2 operations

**Update the app after code changes** (pull, then rebuild just the app):
```bash
cd /opt/vendor-credit-claims && git pull
cd deploy && docker compose -f docker-compose.basic.yml up -d --build
```

**Change the shared password:** edit `APP_USERNAME` / `APP_PASSWORD` in `deploy/.env`, then
`docker compose -f docker-compose.basic.yml up -d`. No Caddy change, no rebuild needed.
(Existing sessions stay valid until they expire or you also rotate `APP_SECRET`.)

**Back up the data** (DB + uploaded files) — the important one:
```bash
tar czf claims-backup-$(date +%F).tar.gz -C /opt/vendor-credit-claims data
```
Copy that off the droplet regularly (or fold it into your n8n backups).

**Update product master / rebates:** replace `AU_Promo Form_TEMPLATE.xlsx` in the repo,
push, `git pull` on the droplet, then rebuild (existing promos are untouched; reference
data is upserted).

**Logs:** `docker compose -f docker-compose.basic.yml logs -f`

---

## Troubleshooting

- **502 from Caddy:** the app isn't reachable on Caddy's network — confirm `CADDY_NETWORK`
  in `.env` matches step 3, and `docker compose -f docker-compose.basic.yml ps` shows the
  `claims` container up.
- **No HTTPS cert:** DNS isn't pointing at the droplet yet, or ports 80/443 aren't open.
- **/login rejects the password:** check `APP_USERNAME` / `APP_PASSWORD` in `deploy/.env`,
  then `docker compose -f docker-compose.basic.yml up -d` to reload them (env changes need
  the container recreated).
- **Browser still pops a basic-auth box:** you've still got the old `basic_auth` block in
  the Caddyfile — remove it (see the migration note below) and reload Caddy.
- **Everyone got logged out:** `APP_SECRET` changed (or wasn't set, so it defaults per
  build). Set a fixed `APP_SECRET` in `.env` and recreate the container.

---

## Migrating from Caddy basic_auth (existing deploy)

If you deployed the earlier version where Caddy popped the browser login box:

1. **Add the login env** to `deploy/.env` (reuse your existing shared password if you like):
   ```
   APP_USERNAME=macgear
   APP_PASSWORD=YourSharedPassword
   APP_SECRET=<openssl rand -hex 32>
   ```
2. **Pull + recreate the app:**
   ```bash
   cd /opt/vendor-credit-claims && git pull
   cd deploy && docker compose -f docker-compose.basic.yml up -d --build
   ```
3. **Remove the `basic_auth { … }` block** from the Caddyfile (leave just
   `reverse_proxy claims:8000` inside the site block), then reload Caddy:
   ```bash
   docker exec $CADDY caddy reload --config /etc/caddy/Caddyfile
   ```

Now the browser popup is gone and you get the styled `/login` page instead. If you skip
step 3 you'll briefly get *both* the popup and the page.
