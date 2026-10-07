# Run a cookbook on Railway

This deployment runs OmniGraph **0.13.0** against a Railway S3-compatible
bucket. The image starts an already-applied cluster; source bundles are
prepared locally and configuration updates go through the running server.
Seed data is optional and is never loaded automatically.

Use one service replica in the bucket's region. Disable GitHub autodeploys
and serverless sleeping for this service. OmniGraph retains its writer lock
after exit, so a replacement or crash recovery needs an operator-qualified
handoff. Set the restart policy to `NEVER`; this is an operated
single-writer deployment, with downtime for process replacement.

## Prepare Railway

Create a Railway bucket and an empty service. Configure the service before
connecting this repository or starting a deployment:

| Service setting | Value |
|---|---|
| Root directory | Repository root |
| Start command override | Empty; use the Dockerfile's `CMD` |
| Pre-deploy command | Empty |
| Healthcheck path | `/readyz` |
| Restart policy | `NEVER` |
| Replicas and region | One replica in the bucket's region |
| GitHub autodeploys and serverless sleeping | Disabled |

Keep the service stopped until bootstrap and ownership handoff are complete.
For an existing service, also clear its old **Railway Config File** path and
any pre-deploy command in service settings. Railway has deprecated
[`railway.toml`/`railway.json`](https://docs.railway.com/config-as-code/reference);
this recipe uses service settings. Teams managing infrastructure in code can
use Railway's current [IaC workflow](https://docs.railway.com/infrastructure-as-code)
with the same settings and ownership-handoff requirements.

Set these service variables using Railway's secret/reference-variable UI:

| Variable | Value |
|---|---|
| `RAILWAY_DOCKERFILE_PATH` | `deploy/railway/Dockerfile` |
| `RAILWAY_HEALTHCHECK_TIMEOUT_SEC` | `300` |
| `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` | `60` — longer than the server's default 25-second grace |
| `OMNIGRAPH_CLUSTER_URI` | `s3://<bucket>/cluster` — a dedicated cluster prefix |
| `AWS_ENDPOINT_URL_S3` | Bucket's HTTPS endpoint |
| `AWS_ENDPOINT_URL` | The same endpoint |
| `AWS_ACCESS_KEY_ID` | Bucket access key |
| `AWS_SECRET_ACCESS_KEY` | Bucket secret key |
| `AWS_REGION` | Bucket region |
| `OMNIGRAPH_SERVER_BEARER_TOKENS_JSON` | `{"act-admin":"<admin-secret>","act-writer":"<writer-secret>","act-reader":"<reader-secret>"}` |

Generate separate random secrets, for example with `openssl rand -hex 24`.
Keep them out of the repository and deployment bundle. Static actor-to-token
JSON is supported in 0.13. The bundled policies give the admin configuration
management, writers data changes, and readers read access. Only the admin can
apply schemas or delete graphs. See the engine's
[authentication guide](https://github.com/ModernRelay/omnigraph/blob/v0.13.0/docs/user/operations/server.md#authentication)
for signed identity or OIDC credentials.

The [build and teardown variables](https://docs.railway.com/variables/reference#user-provided-configuration-variables)
select the Dockerfile and shutdown grace. Railway supplies `PORT`; the server
binds to it. Generate a public HTTPS
domain for the service and preserve the `Omnigraph-Http-Api` header through
any additional proxy. Match the service region to the bucket in the dashboard;
remote storage round trips are part of every graph operation.

## Bootstrap once

Install the 0.13 CLI. From this repository's root, choose a cookbook:

| Cookbook | Graph ID |
|---|---|
| `industry-intel` | `spike` |
| `pharma-intel` | `pharma` |
| `second-brain` | `brain` |
| `vc-os` | `vcos` |
| `dev-graph` | `dev` |

Set `OMNIGRAPH_CLUSTER_URI` locally to the same literal S3 root used by the
service. Prepare a new directory:

```bash
export OMNIGRAPH_CLUSTER_URI='s3://your-bucket/cluster'
deploy/railway/scripts/prepare-config.sh industry-intel /tmp/spike-deployment
```

The script copies only the schema, queries, policies and `cluster.yaml`, adds
the storage root, and validates the bundle. It does not access cluster storage,
apply changes, load rows or release locks. Keep this bundle as your deployment
source; editing a cookbook in the repository does not update the server.

With the bucket's `AWS_*` credentials in the operator environment, and no
server or other writer using this fresh prefix:

```bash
# Inspect the proposed graph, schema, queries and policies.
omnigraph cluster plan --config /tmp/spike-deployment --json

# Create the ledger and graph; save the deployment and lock IDs it returns.
omnigraph cluster apply --config /tmp/spike-deployment --as act-admin --json
```

Direct apply retains its writer lock. Before handing ownership to the server,
establish that the apply process and its accepted graph/control-store I/O are
terminal, while excluding other admissions and unlock attempts. A successful
response or stopped process alone does not prove native I/O settlement. Follow
the engine's [ownership-transfer procedure](https://github.com/ModernRelay/omnigraph/blob/v0.13.0/docs/user/deployment.md#writer-topology),
then release only the exact lock ID:

```bash
omnigraph --cluster "$OMNIGRAPH_CLUSTER_URI" cluster status --json
omnigraph --cluster "$OMNIGRAPH_CLUSTER_URI" cluster force-unlock '<LOCK_ID>'
```

Now connect the repository, start the Railway service and wait for its readiness check. Bootstrap
failures or uncertain outcomes require inspection of the original deployment
ID; do not repeatedly run apply or remove storage to make startup pass.

## Use and update the graph

Set the service root and your token locally:

```bash
export ENDPOINT='https://your-service.up.railway.app'
export OMNIGRAPH_BEARER_TOKEN='<admin-secret>'
curl -fsS "$ENDPOINT/readyz"
omnigraph graphs list --server "$ENDPOINT" --json

# Optional: load the cookbook's sample data through the admitted server.
omnigraph load --server "$ENDPOINT" --graph spike \
  --data industry-intel/seed.jsonl --mode merge
```

For schema, query, policy, provider or Blob-rule changes, edit the prepared
bundle and use the server's deployment flow:

```bash
omnigraph cluster validate --config /tmp/spike-deployment
omnigraph cluster plan --server "$ENDPOINT" --config /tmp/spike-deployment --json
omnigraph cluster apply --server "$ENDPOINT" --config /tmp/spike-deployment \
  --timeout 1800 --json
```

The server applies and activates the changes without restarting. Schema
changes require only the `main` branch to remain. Review the whole plan:
omitting a graph **permanently deletes its managed root and all history**.
Switching to another cookbook is therefore a deliberate configuration/data
change, not a service variable or bucket deletion.

Apply prints an ID before submission. If waiting expires or the response is
lost, observe that ID rather than submitting another apply:

```bash
omnigraph cluster status --server "$ENDPOINT" \
  --deployment-id '<DEPLOYMENT_ID>' --wait --timeout 1800 --json
```

Data writes also continue after a disconnect. An unknown outcome is not a
retry instruction. Keep exact commit receipts and inspect the result before
resubmitting. Use the 0.13 CLI/SDK to handle the HTTP contract; raw protected
requests require `Omnigraph-Http-Api: 0.13` and a matching response header.

Vector-enabled cookbooks start with no embedding provider. Structural and
full-text queries work without one. To add vectors, bind a provider in the
bundle, supply its secret to the server and apply the configuration. Bulk load
does not generate embeddings: use `omnigraph embed` to produce embedded JSONL
before loading it. Changing the provider does not regenerate stored vectors.

## Replace or recover the server

Use this process for an engine image update, static-token rotation, region
change, or recovery after exit:

1. Stop new client work and any scheduled writer jobs. Preserve a verified
   whole-root backup before an upgrade; check the release's storage requirements.
2. Stop the previous service. Establish accepted graph and control-store I/O
   settlement and exclude competing starts/unlocks. Inspect root-addressed
   `cluster status`; resolve any outstanding deployment by its original ID
   using the [recovery guide](https://github.com/ModernRelay/omnigraph/blob/v0.13.0/docs/user/clusters/index.md#inspect-and-recover-a-deployment).
3. Release the exact retained lock only after that qualification. Start one
   replacement service, wait for `/readyz`, then check representative reads and
   writes before reopening traffic.

Railway's [normal replacement lifecycle](https://docs.railway.com/deployments/deployment-teardown)
starts a new deployment before stopping the old one. Even an overlap setting of
zero does not provide OmniGraph's required ownership handoff. Do not use a
normal rolling redeploy, automatic restart, or a pre-deploy direct apply for
this service. Never automate force-unlock based on lock age or process exit.

The image is pinned by `OMNIGRAPH_REF` in the Dockerfile. Older cookbook
clusters may need export/rebuild or explicit ledger conversion before 0.13 can
serve them; use the engine's [upgrade guide](https://github.com/ModernRelay/omnigraph/blob/v0.13.0/docs/user/operations/upgrade.md).
Keep the previous whole-root backup and binary together. Do not point an old
binary at new-format storage or replace real data with the demo seed.

## Check the deployment files

```bash
python3 -m unittest discover -s deploy/railway/tests -v

docker build --platform linux/amd64 -f deploy/railway/Dockerfile -t omnigraph-railway:test .
docker run --rm --platform linux/amd64 omnigraph-railway:test omnigraph --version
```

The script tests require the 0.13 CLI on `PATH` (or `OMNIGRAPH_BIN`); they
validate every prepared cookbook and check that preparation never invokes a
storage mutation. They do not deploy to Railway or qualify its S3 failure modes.
