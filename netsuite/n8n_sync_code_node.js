// n8n Code node — NetSuite pricing sync (paste this into a Code node set to
// "Run Once for All Items"). It signs NetSuite token-based-auth (OAuth1, HMAC-SHA256)
// itself, pulls both master price level saved searches via the RESTlet, and POSTs the
// rows to the app. No n8n OAuth1 credential needed — that UI doesn't fit NetSuite TBA.
//
// Wire it as:  Schedule Trigger  ->  this Code node.
//
// Secrets: filled in below for simplicity. To avoid storing them in the node, set them
// as environment variables on the n8n container and swap each constant for
// e.g. $env.NETSUITE_CONSUMER_KEY.

const crypto = require('crypto');

// ---------- fill these in ----------
const ACCOUNT_ID      = 'REPLACE_ACCOUNT_ID';      // Setup > Company > Company Information > ACCOUNT ID (e.g. 1234567 or 1234567_SB1)
const CONSUMER_KEY    = 'REPLACE_CONSUMER_KEY';    // from the Integration record
const CONSUMER_SECRET = 'REPLACE_CONSUMER_SECRET';
const TOKEN_ID        = 'REPLACE_TOKEN_ID';        // from the Access Token
const TOKEN_SECRET    = 'REPLACE_TOKEN_SECRET';
const RESTLET_SCRIPT  = 'REPLACE_SCRIPT_ID';       // the "script=" number in the RESTlet deployment URL
const RESTLET_DEPLOY  = 'REPLACE_DEPLOY_ID';       // the "deploy=" number
const APP_URL         = 'http://claims:8000/admin/sync-pricing';
const SYNC_TOKEN      = 'REPLACE_PRICING_SYNC_TOKEN';
const SEARCHES        = [{ country: 'AU', searchId: 'customsearch1084' },
                         { country: 'NZ', searchId: 'customsearch1413' }];
// -----------------------------------

const host = ACCOUNT_ID.toLowerCase().replace(/_/g, '-');
const RESTLET_BASE = `https://${host}.restlets.api.netsuite.com/app/site/hosting/restlet.nl`;
const helpers = this.helpers;

// RFC-3986 percent-encoding
const pct = (s) => encodeURIComponent(String(s)).replace(/[!*'()]/g,
  (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase());

function authHeader(method, baseUrl, queryParams) {
  const oauth = {
    oauth_consumer_key: CONSUMER_KEY,
    oauth_token: TOKEN_ID,
    oauth_signature_method: 'HMAC-SHA256',
    oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
    oauth_nonce: crypto.randomBytes(16).toString('hex'),
    oauth_version: '1.0',
  };
  const all = Object.assign({}, queryParams, oauth);
  const paramStr = Object.keys(all).sort()
    .map((k) => pct(k) + '=' + pct(all[k])).join('&');
  const base = [method.toUpperCase(), pct(baseUrl), pct(paramStr)].join('&');
  const signingKey = pct(CONSUMER_SECRET) + '&' + pct(TOKEN_SECRET);
  const signature = crypto.createHmac('sha256', signingKey).update(base).digest('base64');
  const headerParams = Object.assign({}, oauth, { oauth_signature: signature });
  return 'OAuth realm="' + ACCOUNT_ID + '", ' + Object.keys(headerParams).sort()
    .map((k) => pct(k) + '="' + pct(headerParams[k]) + '"').join(', ');
}

const out = [];
for (const s of SEARCHES) {
  const query = { script: RESTLET_SCRIPT, deploy: RESTLET_DEPLOY, searchId: s.searchId };
  const url = RESTLET_BASE + '?' + Object.keys(query)
    .map((k) => pct(k) + '=' + pct(query[k])).join('&');

  const rows = await helpers.httpRequest({
    method: 'GET', url,
    headers: { Authorization: authHeader('GET', RESTLET_BASE, query) },
    json: true,
  });

  const result = await helpers.httpRequest({
    method: 'POST', url: APP_URL,
    headers: { 'X-Sync-Token': SYNC_TOKEN, 'Content-Type': 'application/json' },
    body: { country: s.country, rows },
    json: true,
  });

  out.push({ json: result });   // e.g. {country:"AU", received:1760, inserted:..., updated:..., pruned:...}
}
return out;
