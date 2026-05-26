# Deploy an Omnigraph cookbook on Railway

One-click deploys of any cookbook in this repo against a managed
S3-compatible bucket on [Railway](https://railway.com). No AWS account
needed; Railway provisions the storage, generates the bearer tokens, and
runs `omnigraph init` + seed load on first boot.

## What you get

| Piece                  | Where it runs                                                            |
| ---------------------- | ------------------------------------------------------------------------ |
| `omnigraph-server`     | Single Railway service (this repo's `deploy/railway/Dockerfile`)         |
| Storage                | Railway Bucket — first-party S3, R2-backed, free egress                  |
| Schema                 | Pulled from `OMNIGRAPH_SCHEMA_URL` at deploy time and applied via `omnigraph init` |
| Auth (3 actors)        | `admin` / `writer` / `reader` bearer tokens auto-generated at deploy     |
| Authz                  | Cedar-via-YAML policy at `/etc/omnigraph/policy.yaml` (baked into image) |
| Public HTTPS endpoint  | Railway-managed `*.up.railway.app` domain with auto-SSL                  |

The template is **schema-only**: it applies the schema you point at and
then stops. The graph starts empty and ready to receive your real data
via the `omnigraph` CLI or the HTTP API. Demo `seed.jsonl` files from
the cookbooks are not auto-loaded.

Total cost on Railway Hobby: ~$0.015/GB-month for storage + the service's
compute. No volumes attached — all state lives in the Bucket.

## Deploy

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/TBD)

At deploy time, paste the URL of the schema you want to apply via the
`OMNIGRAPH_SCHEMA_URL` variable. Any HTTPS URL to a `.pg` file works —
the bundled cookbooks in this repo are the obvious starting point:

| Cookbook | Schema URL to paste |
|---|---|
| AI/ML industry intelligence (SPIKE) | `https://raw.githubusercontent.com/ModernRelay/omnigraph-cookbooks/main/industry-intel/schema.pg` |
| Pharma competitive intelligence | `https://raw.githubusercontent.com/ModernRelay/omnigraph-cookbooks/main/pharma-intel/schema.pg` |
| Personal life automation | `https://raw.githubusercontent.com/ModernRelay/omnigraph-cookbooks/main/second-brain/schema.pg` |
| Venture-capital operating system | `https://raw.githubusercontent.com/ModernRelay/omnigraph-cookbooks/main/vc-os/schema.pg` |

You can also paste a URL to your own schema (GitHub raw, gist, S3
signed URL, anywhere HTTPS-reachable). The deploy initializes the graph
with that schema and then stops — fill the graph with your own data
afterwards via the `omnigraph` CLI or the HTTP API.

> **Status:** Template URL above is a placeholder until the template is
> published on Railway. Until then, deploy manually:
>
> ```bash
> railway init
> railway bucket create graph-storage --region <closest-to-you>
> railway add --service omnigraph
> railway variable set --service omnigraph --skip-deploys \
>   "OMNIGRAPH_SCHEMA_URL=https://raw.githubusercontent.com/ModernRelay/omnigraph-cookbooks/main/industry-intel/schema.pg" \
>   "OMNIGRAPH_TARGET_URI=s3://\${{graph-storage.BUCKET}}/graph" \
>   "AWS_ENDPOINT_URL=\${{graph-storage.ENDPOINT}}" \
>   "AWS_ENDPOINT_URL_S3=\${{graph-storage.ENDPOINT}}" \
>   "AWS_ACCESS_KEY_ID=\${{graph-storage.ACCESS_KEY_ID}}" \
>   "AWS_SECRET_ACCESS_KEY=\${{graph-storage.SECRET_ACCESS_KEY}}" \
>   "AWS_REGION=\${{graph-storage.REGION}}" \
>   'OMNIGRAPH_SERVER_BEARER_TOKENS_JSON={"admin":"CHANGEME","writer":"CHANGEME","reader":"CHANGEME"}'
> # Make sure the service's region matches the Bucket region (railway scale)
> railway up --service omnigraph
> ```

## Service region

Place the service in the same Railway region as the Bucket. The Bucket
region is fixed at creation (sjc / iad / ams / sin); the service should
match. Cross-region traffic to S3-API operations adds 200–500 ms RTT
per call, which makes `omnigraph load` painfully slow because the
referential-integrity validation does many sequential list/get calls.
In-region keeps loads at a few seconds even for thousands of rows.

## Required environment variables

The template configures these for you. Listed here so you understand
what each does (and to make manual deploys reproducible).

| Variable                              | Value at deploy                                                                          |
| ------------------------------------- | ---------------------------------------------------------------------------------------- |
| `OMNIGRAPH_SCHEMA_URL`                | HTTPS URL of a `.pg` schema file. Default: `https://raw.githubusercontent.com/ModernRelay/omnigraph-cookbooks/main/industry-intel/schema.pg`. Override with any URL. |
| `OMNIGRAPH_TARGET_URI`                | `s3://${{Bucket.BUCKET}}/graph`                                                          |
| `AWS_ENDPOINT_URL`                    | `${{Bucket.ENDPOINT}}` — read by Lance's `object_store`                                  |
| `AWS_ENDPOINT_URL_S3`                 | `${{Bucket.ENDPOINT}}` — read by the omnigraph S3 adapter (set both for cross-version safety) |
| `AWS_ACCESS_KEY_ID`                   | `${{Bucket.ACCESS_KEY_ID}}`                                                              |
| `AWS_SECRET_ACCESS_KEY`               | `${{Bucket.SECRET_ACCESS_KEY}}`                                                          |
| `AWS_REGION`                          | `${{Bucket.REGION}}`                                                                     |
| `OMNIGRAPH_SERVER_BEARER_TOKENS_JSON` | `{"admin":"${{secret(48)}}","writer":"${{secret(48)}}","reader":"${{secret(48)}}"}`      |
| `GEMINI_API_KEY` (optional)           | Empty by default; supply yours at deploy time to unlock text-input vector search         |

### Embeddings + Gemini

Three of the four cookbooks (`industry-intel`, `second-brain`, `vc-os`)
have schemas with `Vector(...) @embed("...")` fields. The seed load does
**not** populate those vectors — they stay null unless you run
`omnigraph embed --reembed-all` against the deployed graph (out of scope
for v1 of this template; the cookbooks don't yet ship the seed-side
`embeddings:` block required by that flow).

Practical consequences:

- Without `GEMINI_API_KEY`, the deploy still works for every query type
  we ship in the cookbook (`get_*`, `recent_*`, traversals like
  `pattern_signals`, FTS via `search(...)`). Only `nearest(field, "text",
  k)` queries that need to embed a *text* input at query time return 500
  with `"GEMINI_API_KEY is required when nearest() needs a string
  embedding"`.
- With `GEMINI_API_KEY` set, the same vector queries work once you've
  populated the embedding columns via `omnigraph embed` (workstation-
  initiated; runs against the running server).
- `pharma-intel` has no `@embed` fields and never needs the key.

The Railway template marks `GEMINI_API_KEY` as an **optional user-input
variable** — the deploy UI shows a blank field with the description
above. Leave it blank to skip; set it to a Gemini API key to enable
text-input vector search later.

`${{Bucket.*}}` and `${{secret(N)}}` are Railway's reference-variable
and template-function syntax — they resolve at deploy time without
appearing in build logs.

## Get your tokens

After the first deploy:

1. Open the omnigraph service in the Railway dashboard.
2. Go to the **Variables** tab.
3. Find `OMNIGRAPH_SERVER_BEARER_TOKENS_JSON`. Railway shows the
   resolved JSON; copy the three tokens.

Then call the server:

```bash
ENDPOINT="https://$YOUR_SERVICE.up.railway.app"
TOKEN="$ADMIN_TOKEN_FROM_VARS"

curl -fsS "$ENDPOINT/healthz" | jq .
curl -fsS -H "Authorization: Bearer $TOKEN" \
  "$ENDPOINT/snapshot?branch=main" | jq '.tables[] | select(.row_count > 0)'
```

## Authorization model

The bundled policy at `/etc/omnigraph/policy.yaml` defines three roles:

| Actor    | Can do                                                                       |
| -------- | ---------------------------------------------------------------------------- |
| `admin`  | Everything: `read`, `export`, `change`, `schema_apply`, `branch_*`           |
| `writer` | `read`, `export`, `change` on any branch; `branch_create` against unprotected branches |
| `reader` | `read`, `export` on any branch                                               |

`main` is marked protected — only `admin` can `branch_create` against it
or run `schema_apply` / `branch_delete` / `branch_merge` anywhere.

Bearer tokens are SHA-256 hashed on server startup; the plaintext lives
only in the Railway-encrypted env var, not in process memory. Constant-
time comparison via `subtle::ConstantTimeEq`.

## Rotation

Open the Variables tab → click the regenerate icon on a specific
sub-field of `OMNIGRAPH_SERVER_BEARER_TOKENS_JSON`, or edit the JSON
inline. Click **Redeploy** to pick up the change.

## Customizing the policy

The Cedar policy is baked into the image at build time. For deployments
that need a different role/group structure:

1. Fork this repo.
2. Edit `deploy/railway/config/policy.yaml`.
3. Validate locally: `omnigraph policy validate --policy ./deploy/railway/config/policy.yaml`.
4. Push the fork and point your Railway service at it.

## Re-deploy and schema changes

The `preDeployCommand` runs `omnigraph-railway-init.sh` between build
and start on every deploy. The script is idempotent:

- **Empty bucket** → `curl $OMNIGRAPH_SCHEMA_URL` + `omnigraph init`.
- **Existing graph** → script detects via `omnigraph snapshot` and
  skips. No data loss across re-deploys.

Schema changes are **not** auto-applied. After updating
`OMNIGRAPH_SCHEMA_URL` (or the file it points at), run
`omnigraph schema apply` against the running server from a workstation
to migrate the live graph. See the engine docs.

## Switching schemas

`OMNIGRAPH_SCHEMA_URL` only affects the first deploy (when the bucket
is empty). To switch a running service to a different schema either:

1. Apply the migration via `omnigraph schema apply` against the live
   server (recommended — preserves data where the migration plan
   allows).
2. Destroy the Bucket via `railway bucket delete graph-storage` and
   redeploy; the next deploy re-runs init.sh against the new schema URL.

## Local validation

```bash
# Build the image
docker build -f deploy/railway/Dockerfile -t omnigraph-railway:test .

# Verify the binaries and cookbooks landed
docker run --rm omnigraph-railway:test omnigraph --version
docker run --rm omnigraph-railway:test ls /cookbooks

# Run against a local RustFS (the engine repo ships a bootstrap script)
docker run --rm \
  -e OMNIGRAPH_SCHEMA_URL=https://raw.githubusercontent.com/ModernRelay/omnigraph-cookbooks/main/industry-intel/schema.pg \
  -e OMNIGRAPH_TARGET_URI=s3://omnigraph-local/graph \
  -e AWS_ENDPOINT_URL_S3=http://host.docker.internal:9000 \
  -e AWS_ACCESS_KEY_ID=rustfsadmin \
  -e AWS_SECRET_ACCESS_KEY=rustfsadmin \
  -e AWS_REGION=us-east-1 \
  -e AWS_S3_FORCE_PATH_STYLE=true \
  -e AWS_ALLOW_HTTP=true \
  omnigraph-railway:test \
  sh -c '/usr/local/bin/omnigraph-railway-init.sh && omnigraph snapshot $OMNIGRAPH_TARGET_URI --json'
```

## Pinning + maintenance

The Dockerfile pins the omnigraph engine to a specific tag via
`ARG OMNIGRAPH_REF=v0.5.0`. Bump that on every omnigraph release that
changes server behavior, the policy schema, or the CLI surface. The
cookbooks themselves are read at build time — adding a new cookbook to
the repo means rebuilding the image before a new Railway template can
target it.

## Files

```
railway.toml             # build/deploy/preDeployCommand/healthcheck (at repo root — Railway reads it from here)
deploy/railway/
├── Dockerfile           # Multi-stage build (rust:slim → debian:bookworm-slim)
├── .dockerignore        # Trims context to schema/seed/queries/yaml only
├── scripts/
│   └── init.sh          # Idempotent omnigraph init + optional seed load
└── config/
    ├── omnigraph.yaml   # points the server at the bundled policy
    └── policy.yaml      # admin / writer / reader Cedar policy
```

`railway.toml` lives at the repo root because Railway reads its config from a service's root directory by default; everything else stays under `deploy/railway/` for tidiness.
