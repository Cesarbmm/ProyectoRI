# FiQA API on Vercel

This adapter deploys the existing `ri_fiqa.api:app` on Python 3.12 with PyTorch
CPU. Retrieval code, embeddings, academic metrics and the frontend are unchanged.

The isolated `fiqa-api` project uses Root Directory `backend`, the FastAPI preset,
Fluid Compute and Large Functions beta. The frontend remains in `fiqa`, rooted at
`frontend`. Enable source files outside the root directory: the build copies the
repository's `src/ri_fiqa` package into the function.

## Reproduce the build

In Linux with [uv](https://docs.astral.sh/uv/), from `backend/`:

```bash
uv sync --frozen --no-dev
uv run --frozen python prepare_runtime.py
RI_RUNTIME_DIAGNOSTICS=1 uv run --frozen uvicorn main:app --port 8100
```

`uv.lock` pins production dependencies; Torch comes exclusively from the CPU
index. The root Windows/CUDA lockfile is not used for deployment. Evaluation
packages such as `ir-measures` are not installed in the function.

`prepare_runtime.py` downloads the [immutable runtime Release](https://github.com/Cesarbmm/ProyectoRI/releases/tag/fiqa-runtime-v1),
checks its archive SHA-256 and every extracted file, and downloads BGE revision
`a5beb1e3e68b9ab74eb54cfd186867f64f240e1a` with per-file hashes. The manifest is
versioned in `assets-manifest.json`. This includes the entire 57,638-document
corpus and the unchanged 57,600-vector FAISS index. It does not rebuild embeddings.

The build checks actual corpus/FAISS counts and requires CPU Torch. Generated
`runtime/`, the copied `ri_fiqa/` and local environments are ignored by Git and
source upload, then recreated during the build. The function includes them as
read-only files. Hugging Face runs offline at request time; models and retrievers
are cached only for the lifetime of each function instance.

## Vercel configuration

Build command: `uv run --frozen python prepare_runtime.py`.

| Variable | Preview | Production |
|---|---|---|
| `VERCEL_SUPPORT_LARGE_FUNCTIONS` | `1` | `1` |
| `RI_RUNTIME_DIAGNOSTICS` | `1` | `0` |
| `RI_CORS_ORIGINS` | Exact permitted origins | Exact permitted origins |
| `RI_CORS_ORIGIN_REGEX` | Account-scoped FiQA preview pattern | Same restricted pattern when needed |

The configured preview pattern is
`^https://fiqa-(?:[a-z0-9-]+-)?fonfini123-1060\.vercel\.app$`.
It does not allow arbitrary Vercel sites. Credentials are not used by browser
requests. The adapter preserves existing API validation and scores.

`/ready` additionally verifies all asset hashes once per instance. Preview-only
`POST /runtime/measure` executes all five real systems in the same process and
returns Linux RSS/peak RSS and the effective configuration. It is absent from
Production. Logs contain path, duration and process memory, not query contents,
documents, headers or credentials.

## Verification

From the repository root:

```powershell
python backend/verify_api.py http://127.0.0.1:8100 --report build/linux-api.json
# For a protected Preview, use the pinned CLI's dist/vc.js:
python backend/verify_api.py https://<preview>.vercel.app --cli <path-to-vercel/dist/vc.js> --report build/preview-api.json
# Public Production omits diagnostic endpoints:
python backend/verify_api.py https://<api-domain>.vercel.app --no-diagnostics --report build/production-api.json
```

This verifies health, integrity/readiness, the catalog/frozen settings, individual
searches for every model, the five-model comparison, and the BGE APR/APY regression.
Preview checks also require all models and all corpus documents to be loaded in
one CPU process below 2 GB RSS. No search response is mocked.

Verified on Ubuntu/WSL: approximately 1.32 GB RSS. Verified on Vercel Preview:
1,263,628,288 bytes RSS/peak RSS, all five systems loaded. Vercel reports a function
package of approximately 932 MB. Machine-readable evidence is in
`docs/deployment/linux-cpu-api.json` and `docs/deployment/vercel-preview-api.json`.

## Cost and limits

The selected account remains Hobby. No paid resource, Pro upgrade or performance
instance is activated. Hobby includes 4 active CPU hours, 360 provisioned GB-hours
and 1 million invocations monthly; quota exhaustion can pause service. The
function is limited to 2 GB/1 vCPU and 300 seconds. Large Functions is beta, with
a 5 GB bundle limit. These checks demonstrate a working low-volume deployment,
not an unlimited capacity guarantee. See [current Hobby quotas](https://vercel.com/docs/plans/hobby)
and [Function limits](https://vercel.com/docs/functions/limitations).

Separate projects keep frontend deploys independent from the API's large build
and allow separate rollbacks. Vercel Services offers one domain and atomic deploys
but adds another beta integration and couples deployments; it is not required for
this verified configuration. No Render service is changed by this migration.
