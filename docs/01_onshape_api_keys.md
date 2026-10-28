# 01 · Onshape API keys (`.env`)

The pipeline talks to Onshape through its REST API. Authentication uses an
**access key + secret key pair** with HMAC-signed requests (implemented by
`onshape-to-robot`; our scripts reuse the exact same client).

## 1. Create the keys (one time)

1. Log in to Onshape: <https://cad.onshape.com>
2. Open **My Account → Developer → API keys**, or go directly to
   <https://dev-portal.onshape.com/keys>
3. **Create API key** — client credentials flow, no scopes needed beyond the
   defaults (read/write your own documents is enough).
4. Copy immediately: the **secret key is shown only once**.

## 2. Paste them into `.env`

```bash
# .env  (project root — never commit this file, it is .gitignore'd)
ONSHAPE_API=https://cad.onshape.com
ONSHAPE_ACCESS_KEY=<your access key>
ONSHAPE_SECRET_KEY=<your secret key>
```

`.env.example` is a committed template without secrets.

## 3. Verify

```bash
make check        # or: python scripts/env_check.py
```

Expected output:

```
  [OK]   .env file              keys loaded (https://cad.onshape.com)
  [OK]   assembly URL           document bffb4cd2fd50e50786659d67
  [OK]   API authentication     signed request accepted
  [OK]   document access        "Universal Robot UR10 - Raheb"
  [OK]   assembly element       assembly reachable
```

## Error meanings

| Symptom | Cause | Fix |
|---|---|---|
| "keys are not set yet" | placeholders left in `.env` | paste real keys |
| `401` | wrong key pair | re-copy both keys |
| `403` | keys valid, **no access to this document** | use keys from the account that owns/shares the document |
| `404` | wrong document/workspace/element id | re-copy the URL from the browser tab |

## Security notes

* `.env` is listed in `.gitignore` — never commit or share it.
* Keys can be revoked/regenerated any time from the same developer page.
* The same keys are also supported as shell exports (`export ONSHAPE_...`)
  if you prefer that over `.env`.
