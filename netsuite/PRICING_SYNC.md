# Automated pricing sync — NetSuite → app

Keeps product/customer pricing current by pulling the master price level saved
searches from NetSuite on a schedule and upserting them into the app.

```
n8n (daily)
  ├─ GET  NetSuite RESTlet ?searchId=customsearch1084   (AU master price levels)
  ├─ POST http://claims:8000/admin/sync-pricing  {country:"AU", rows:[…]}
  ├─ GET  NetSuite RESTlet ?searchId=customsearch1413   (NZ master price levels)
  └─ POST http://claims:8000/admin/sync-pricing  {country:"NZ", rows:[…]}
```

**NetSuite is the source of truth for the product list and pricing.** Each sync makes
the app's catalog for that country match the feed: it adds new SKUs, updates RRP + every
channel/retailer price, and **prunes discontinued SKUs** (codes no longer in the feed).
Deleting a product is safe — promos store the code as text, so existing promos are
unaffected. A safety guard skips pruning if a feed comes back suspiciously small
(< 50 rows), so a broken/empty NetSuite response can never wipe the catalog.

The bundled template is only a **bootstrap**: on a fresh, empty database the app seeds
products from it so the app isn't blank before the first sync. Once products exist,
restarts never reseed from the template — NetSuite owns the catalog.

> Saved searches: **AU = `customsearch1084`**, **NZ = `customsearch1413`**.
> They already return exactly the columns the importer expects (Code, Description,
> Brand, AU/NZ Status, Base (RRP Inc), then one column per retailer channel).

---

## 1. Deploy the RESTlet in NetSuite

1. **Customization → Scripting → Scripts → New.**
2. Upload `netsuite/run_saved_search_restlet.js` (from this repo) as the script file.
   Type = **RESTlet**. Functions: GET = `get`, POST = `post`. Save.
3. **Deploy Script:** status **Released**, and set the audience/role to one that can
   run the searches (e.g. a dedicated integration role with "Lists > Items" view +
   search permissions). Save.
4. From the deployment, copy the **External URL**. It looks like:
   ```
   https://<ACCOUNTID>.restlets.api.netsuite.com/app/site/hosting/restlet.nl?script=<SCRIPTID>&deploy=<DEPLOYID>
   ```
   You'll append `&searchId=customsearch1084` (or `1413`) when calling it.

Quick manual test (in browser you can't, but) — once tokens exist (step 2), n8n or
`curl` with OAuth1 should return a JSON array of rows.

---

## 2. Create token-based auth (TBA) credentials

1. **Setup → Company → Enable Features → SuiteCloud:** ensure **Token-Based
   Authentication** and **RESTlets** are enabled.
2. **Setup → Integration → Manage Integrations → New:** name e.g.
   "Vendor Credit Claims pricing sync". Untick TBA: Authorization Flow / OAuth2; tick
   **Token-Based Authentication**. Save → copy the **Consumer Key** and **Consumer
   Secret** (shown once).
3. **Setup → Users/Roles → Access Tokens → New:** pick the integration above, a user,
   and a role that can run the searches. Save → copy the **Token ID** and **Token
   Secret** (shown once).
4. Note your **Account ID** (realm), e.g. `1234567` (or `1234567_SB1` for sandbox).

You now have the four secrets n8n needs: consumer key/secret, token id/secret (+ account id).

---

## 3. Set the app's shared secret

On the droplet:
```bash
cd /opt/vendor-credit-claims/deploy
# generate a secret and put it in .env
echo "PRICING_SYNC_TOKEN=$(openssl rand -hex 24)" >> .env   # or edit .env by hand
docker compose -f docker-compose.basic.yml up -d            # recreate to pick up the env
```
The endpoint rejects every call unless this is set and matched.

---

## 4. Build the n8n workflow

Create a workflow with these nodes:

1. **Schedule Trigger** — e.g. daily at 06:00.

2. **HTTP Request — "NetSuite AU"**
   - Method **GET**, URL = the RESTlet URL **+** `&searchId=customsearch1084`
   - Authentication: **Generic Credential → OAuth1**
     - Consumer Key / Secret, Access Token (= Token ID) / Token Secret from step 2
     - Signature Method: **HMAC-SHA256**
     - Realm: your **Account ID** from step 2
   - Response: JSON. The body is the array of rows.

3. **HTTP Request — "Sync AU"**
   - Method **POST**, URL = `http://claims:8000/admin/sync-pricing`
     (n8n and the app share the Docker network, so this internal name works — no Caddy,
     no basic-auth. If your n8n runs outside that network, use
     `https://promos.macgeargroup.com/admin/sync-pricing` and add the site's basic-auth too.)
   - Headers: `X-Sync-Token: <the PRICING_SYNC_TOKEN value>`
   - Body: **JSON**, using an expression that wraps the previous node's rows:
     ```
     { "country": "AU", "rows": {{ $json }} }
     ```
     (If the AU node returns the array under `$json.body`, use `{{ $json.body }}`.)

4. **HTTP Request — "NetSuite NZ"** — same as #2 but `&searchId=customsearch1413`.

5. **HTTP Request — "Sync NZ"** — same as #3 but `"country": "NZ"`.

Wire 1→2→3→4→5 (or run AU and NZ branches in parallel). Each Sync node returns a
summary like `{"country":"AU","received":1760,"inserted":3,"updated":1757}` — handy to
log or alert on.

> **n8n OAuth1 + NetSuite note:** NetSuite TBA requires the **realm** (Account ID) in
> the OAuth header and **HMAC-SHA256**. If your n8n's OAuth1 credential has no Realm
> field, either use the community **n8n-nodes-netsuite** node, or compute the OAuth1
> header in a Code node. Ping me and I'll hand you the Code-node snippet.

---

## 5. Verify

Run the workflow manually once. Then in the app, open a promo and check a SKU's
buy/channel price reflects NetSuite. The Sync node's response shows how many rows were
inserted/updated.

---

## Notes

- **NetSuite is authoritative for products.** Template product seeding only happens on an
  empty catalog (bootstrap). The daily sync adds/updates/removes SKUs to match NetSuite.
- **Pruning guard:** if a sync receives < 50 rows for a country it upserts but does **not**
  prune (the response shows `"prune_skipped": true`). You can also send `"prune": false`
  in the POST body to update-only without removing anything.
- **Retailers/rebates** still come from the templates (they change rarely). If the retailer
  list/rebates should also sync from NetSuite, that's a second saved search + a small addition.
- The endpoint only accepts `country` AU or NZ and requires the `X-Sync-Token` header.
- The sync response (e.g. `{"inserted":12,"updated":1748,"pruned":5,...}`) is worth logging
  in n8n so you can see daily catalog churn and get alerted if `pruned` spikes.
