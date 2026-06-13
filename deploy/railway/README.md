# Deploy an Omnigraph cookbook on Railway

One-click deploys of any cookbook in this repo against a managed
S3-compatible bucket on [Railway](https://railway.com). No AWS account
needed; Railway provisions the storage, generates the bearer tokens, and
runs `omnigraph init` + seed load on first boot.

## What you get

| Piece                  | Where it runs                                                            |
| ---------------------- | ------------------------------------------------------------------------ |
| `omnigraph-server`     | Single Railway service (this repo's `deploy/railway/Dockerfile`)         |
| Storage                | Railway Bucket — first-party S3, unlimited free S3 ops + bucket egress   |
| Schema                 | Pulled from `OMNIGRAPH_SCHEMA_URL` at deploy time and applied via `omnigraph init` |
| Auth (3 actors)        | `admin` / `writer` / `reader` bearer tokens auto-generated at deploy     |
| Authz                  | Cedar-via-YAML policy at `/etc/omnigraph/policy.yaml` (baked into image) |
| Public HTTPS endpoint  | Railway-managed `*.up.railway.app` domain with auto-SSL                  |

The template is **schema-only**: it applies the schema you point at and
then stops. The graph starts empty and ready to receive your real data
via the `omnigraph` CLI or the HTTP API. Demo `seed.jsonl` files from
the cookbooks are not auto-loaded.

Total cost on Railway Hobby: ~$0.015/GB-month for stored data + the
service's compute. No volumes attached — all state lives in the Bucket.
Bucket egress and S3 API operations are free and unlimited, but note that
*uploads from the service to the Bucket* (every `init` / `load` / `change`)
count as **service egress** and are billed at Railway's standard public
egress rate — Buckets are not on the private network.

## Deploy

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/TEMPLATE_CODE?utm_medium=integration&utm_source=button&utm_campaign=omnigraph)

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

> **Status:** `TEMPLATE_CODE` in the button URL above is a placeholder —
> replace it with the real template code (and `utm_campaign` with the
> template name) once the template is published on Railway. Until then,
> deploy manually:
>
> ```bash
> railway init
> railway bucket create graph-storage --region <closest-to-you>
> railway add --service omnigraph
> # The ${{secret(48)}} template function only runs on a *template* deploy,
> # not via `railway variable set` — so generate real tokens yourself here:
> ADMIN=$(openssl rand -hex 24); WRITER=$(openssl rand -hex 24); READER=$(openssl rand -hex 24)
> railway variable set --service omnigraph --skip-deploys \
>   "OMNIGRAPH_SCHEMA_URL=https://raw.githubusercontent.com/ModernRelay/omnigraph-cookbooks/main/industry-intel/schema.pg" \
>   "OMNIGRAPH_TARGET_URI=s3://\${{graph-storage.BUCKET}}/graph" \
>   "AWS_ENDPOINT_URL=\${{graph-storage.ENDPOINT}}" \
>   "AWS_ENDPOINT_URL_S3=\${{graph-storage.ENDPOINT}}" \
>   "AWS_ACCESS_KEY_ID=\${{graph-storage.ACCESS_KEY_ID}}" \
>   "AWS_SECRET_ACCESS_KEY=\${{graph-storage.SECRET_ACCESS_KEY}}" \
>   "AWS_REGION=\${{graph-storage.REGION}}" \
>   "OMNIGRAPH_SERVER_BEARER_TOKENS_JSON={\"admin\":\"$ADMIN\",\"writer\":\"$WRITER\",\"reader\":\"$READER\"}"
> # Make sure the service's region matches the Bucket region (railway scale)
> railway up --service omnigraph
> ```

## Service region — this is critical, not cosmetic

**You must place the service in the same region as the Bucket.** A Railway
service with no explicit region (`region: null`, the default) deploys to
the workspace's default region — which is almost never the Bucket's region.
Because `omnigraph-server` does **many sequential S3 round-trips per
operation**, a cross-region service↔Bucket hop multiplies that RTT on every
read and write. Measured on a deliberately mismatched deploy (service on
default region, Bucket in `sjc`):

| Operation | Cross-region (mismatched) | In-region (expected) |
| --------- | ------------------------- | -------------------- |
| `/healthz` (no Bucket) | ~390 ms | ~390 ms |
| `snapshot` read | **~5.7 s** | sub-second |
| single-node write | **~46 s** | ~1 s |

So a mismatch isn't "a bit slower" — it makes the graph effectively
unusable for writes. The Bucket region is fixed at creation; set the
**service** region to match it (Railway dashboard → service **Settings →
Region**, or pin it in config-as-code via
[`multiRegionConfig`](https://docs.railway.com/config-as-code/reference#multi-region-configuration)
using the identifier from the table below). Verify after deploy that the
service's region matches the Bucket's.

Mind the two naming schemes: the **Bucket CLI** uses short codes
(`sjc` / `iad` / `ams` / `sin`), while the **service** region picker (and
config-as-code) uses the full identifiers. Match them up:

| Location               | Bucket code | Service identifier        |
| ---------------------- | ----------- | ------------------------- |
| California, US West    | `sjc`       | `us-west2`                |
| Virginia, US East      | `iad`       | `us-east4-eqdc4a`         |
| Amsterdam, EU West     | `ams`       | `europe-west4-drams3a`    |
| Singapore, SE Asia     | `sin`       | `asia-southeast1-eqsg3a`  |

Because no Railway Volume is attached, changing the service region later
is zero-downtime — only volume-backed services incur migration downtime.

## Scaling and availability

**Keep this service at a single replica.** Railway's production-readiness
checklist recommends ≥2 replicas, but that assumes a stateless service.
`omnigraph-server` is a single-writer store backed by one shared Bucket
prefix, and Railway load-balances replicas randomly with no sticky
sessions — two replicas would race on the same S3 objects and can corrupt
the graph. Do **not** raise the replica count or add multi-region
replicas in the dashboard. Durability comes from Railway's Bucket storage
plus the `ON_FAILURE` restart policy; for point-in-time safety, run
`omnigraph export` / `snapshot` to a second location on a schedule, since
Buckets have no built-in snapshot/versioning.

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

## Loading data

The deploy is schema-only; you fill the graph yourself. Two paths, with
sharp edges to know about:

- **Through the server (recommended): `omnigraph mutate` over HTTPS** with
  an admin bearer token, targeting the service URL. The server performs the
  writes in its own region, so it's version-safe and avoids cross-network
  S3. Note `omnigraph load` does **not** accept a remote server URL
  (*"load is only supported against local graph URIs in this milestone"*),
  so bulk loads go via `mutate`; keep each request modestly sized (a single
  mutation with ~100 inserts can exceed Railway's request timeout and
  return 502 — batch into smaller chunks).
- **Direct to the Bucket (`omnigraph load s3://…`): version-pinned and
  in-region only.** Two hazards, both learned the hard way:
  1. **Version skew corrupts the graph.** Your local CLI must match the
     deployed `OMNIGRAPH_REF`. An older CLI writing a graph created by a
     newer server writes Lance fragments and *then* aborts on the manifest
     version check, leaving the graph inconsistent (`Lance HEAD … ahead of
     manifest`, needs `omnigraph repair`). Always `omnigraph version`-check
     against the server before a direct load.
  2. **Run it in-region.** A direct load from a laptop across the world to
     the Bucket pays the cross-region RTT on every one of its many
     sequential S3 calls — minutes-to-hours for a few hundred rows. Run the
     loader from the Bucket's region (or just use `mutate`).

## Switching schemas

`OMNIGRAPH_SCHEMA_URL` only affects the first deploy (when the bucket
is empty). To switch a running service to a different schema either:

1. Apply the migration via `omnigraph schema apply` against the live
   server (recommended — preserves data where the migration plan
   allows).
2. Destroy the Bucket via `railway bucket -b graph-storage delete` (the
   bucket is named with the global `-b/--bucket` flag, not a positional)
   and redeploy; the next deploy re-runs init.sh against the new schema URL.

## Local validation

```bash
# Build the image
docker build -f deploy/railway/Dockerfile -t omnigraph-railway:test .

# Verify the binaries landed (the schema is fetched at deploy time from
# $OMNIGRAPH_SCHEMA_URL, not baked into the image, so there's nothing
# cookbook-specific to inspect here).
docker run --rm omnigraph-railway:test omnigraph --version
docker run --rm omnigraph-railway:test omnigraph-server --version

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
`ARG OMNIGRAPH_REF=v0.7.0`. Bump that on every omnigraph release that
changes server behavior, the policy schema, or the CLI surface. Schemas
are **not** baked into the image — `init.sh` fetches whatever
`OMNIGRAPH_SCHEMA_URL` points at, so a new cookbook needs no image
rebuild; just point a deploy at its `schema.pg` raw URL.

Because the service builds from this GitHub repo (not a prebuilt image),
merges to `main` surface an update PR to everyone who deployed the
template — keep a changelog and call out breaking changes (e.g. an
`OMNIGRAPH_REF` bump) so deployers know what they're accepting.

## Files

```
railway.toml             # build/deploy/preDeployCommand/healthcheck (at repo root — Railway reads it from here)
deploy/railway/
├── Dockerfile           # Pulls prebuilt omnigraph release binaries onto debian:trixie-slim
├── .dockerignore        # Trims context to schema/seed/queries/yaml only
├── scripts/
│   └── init.sh          # Idempotent omnigraph init + optional seed load
└── config/
    ├── omnigraph.yaml   # points the server at the bundled policy
    └── policy.yaml      # admin / writer / reader Cedar policy
```

`railway.toml` lives at the repo root because Railway reads its config from a service's root directory by default; everything else stays under `deploy/railway/` for tidiness.
