# Deploying Vendor Credit Claims — shared username/password (no SSO)

End state: `https://claims.yourcompany.com` → Caddy (HTTPS + a login prompt) → the app.
Anyone you give the shared username/password to can get in. n8n keeps running untouched.
Data (SQLite DB + uploaded files) lives in `data/` on the droplet.

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
nano .env            # set CADDY_NETWORK to the network name from step 3

docker compose -f docker-compose.basic.yml up -d --build
docker compose -f docker-compose.basic.yml logs -f    # watch it start; Ctrl-C to stop watching
```

On first start the app builds its product/retailer seed from the template, creates the
database, and starts serving on port 8000 inside the network (not exposed to the internet).

---

## 5. Generate the shared password hash

Caddy stores a bcrypt hash, not the plaintext. Generate one (replace the password):

```bash
docker exec $CADDY caddy hash-password --plaintext 'ChooseAStrongSharedPassword'
```

Copy the output — it starts with `$2a$`. That's the hash you'll paste into the Caddyfile.
Pick the username your testers will type (e.g. `team`).

---

## 6. Add the subdomain to Caddy

Edit the Caddyfile from step 3 and append (see `Caddyfile.basic.snippet`):

```
claims.yourcompany.com {
    basic_auth {
        team $2a$14$....your-generated-hash....
    }
    reverse_proxy claims:8000
}
```

Reload Caddy (no downtime). Use the Caddyfile path **inside** the container
(usually `/etc/caddy/Caddyfile`):

```bash
docker exec $CADDY caddy reload --config /etc/caddy/Caddyfile
```

Caddy fetches a Let's Encrypt certificate for the subdomain automatically.

> If reload errors with `unknown directive: basic_auth`, your Caddy is older — change
> `basic_auth` to `basicauth` (no underscore) in the block and reload again.

---

## 7. Test

Open `https://claims.yourcompany.com` → the browser pops a login box → enter the
username and the plaintext password (the one you hashed, not the hash) → you land on the
dashboard. Share that username/password with your testers.

---

## Day-2 operations

**Update the app after code changes** (pull, then rebuild just the app):
```bash
cd /opt/vendor-credit-claims && git pull
cd deploy && docker compose -f docker-compose.basic.yml up -d --build
```

**Change / add the shared password:** re-run step 5 for the new password, replace (or add
another `username  hash` line in) the `basic_auth` block, and reload Caddy (step 6).

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
- **Login box rejects the password:** you typed the hash instead of the plaintext, or the
  `$` signs in the hash got mangled when pasting — re-paste the full hash exactly.
- **`unknown directive: basic_auth`:** older Caddy — use `basicauth` (no underscore).
