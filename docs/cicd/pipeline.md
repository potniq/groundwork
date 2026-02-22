# Groundwork: A Reference CircleCI Pipeline

**Repository:** [github.com/potniq/groundwork](https://github.com/potniq/groundwork)
**Passing build (full main pipeline):** [View on CircleCI](https://app.circleci.com/pipelines/circleci/D6cWZV8Ay28ELFRhwTUCno/HSujtgo1SQZFtF88eXY7qm/99/workflows/4581382b-c9ed-42c7-b99a-06562cd57f78)


## High level overview

This pipeline is for a production application — Groundwork by Potniq. The app is a dockerized Python/FastAPI web application backed by a PostgreSQL database, deployed on DigitalOcean App Platform.

The pipeline covers the full lifecycle of shipping production software:

- **Selective execution** — path filtering skips the pipeline entirely for documentation-only changes, saving compute
- **Parallel quality gates** — unit tests, integration tests, and dependency scanning run concurrently for fast feedback
- **Branch-based promotion** — feature branches run validations only; the `main` branch extends into container build, security scanning, release, and deployment
- **Security scanning** — both Python dependencies and the built Docker container are scanned for vulnerabilities using Snyk
- **Nightly scheduled builds** — catch newly disclosed vulnerabilities and confirm the build stays healthy without waiting for a code change

The pipeline is split across two configuration files in `.circleci/`:

- `setup-config.yml` — the entry point for commit-triggered builds, using [dynamic config](https://circleci.com/docs/guides/orchestrate/dynamic-config/) and path filtering to decide whether to run the full pipeline
- `config.yml` — the main configuration containing all job definitions and two mutually exclusive workflows, selected by pipeline parameters


## Validation flow

Every commit that touches application code goes through three parallel validation jobs before anything is built or shipped:

1. **Dependency installation (`install-deps`)** — installs Python packages from `requirements.txt` into a user-site directory, cached by a key derived from the requirements file checksum. The installed packages are persisted to a workspace so downstream jobs reuse them without reinstalling.

2. **Unit tests (`test-unit`)** — runs the unit test suite with `pytest`, publishing JUnit XML results and artifacts to CircleCI for visibility in the test insights dashboard.

3. **Integration tests (`test-integration`)** — runs integration tests against a real PostgreSQL instance provisioned as a [sidecar container](https://circleci.com/docs/using-docker#using-multiple-docker-images). Database migrations are applied before the tests execute, validating the full database interaction path.

4. **Dependency scan (`scan-python-deps`)** — uses the Snyk orb to scan `requirements.txt` for known vulnerabilities at the `high` severity threshold.

Unit tests, integration tests, and the dependency scan all run in parallel after `install-deps` completes, so the feedback loop is as fast as the slowest of the three.

On feature branches, the pipeline stops here. Nothing gets built or deployed until code reaches `main`.


## Dynamic workflow selection

The pipeline uses two mechanisms to control what runs and when.

### Path filtering (setup config)

`setup-config.yml` is a [setup workflow](https://circleci.com/docs/dynamic-config/) — the first stage in a dynamic pipeline. It uses the `path-filtering` orb to inspect which files changed in the commit and maps file patterns to the `run_workflow` pipeline parameter:

- Changes to application code (`app/`, `tests/`, `scripts/`), infrastructure (`Dockerfile`, `requirements.txt`, `.circleci/`), or database migrations (`supabase/`) set `run_workflow: true`
- Changes limited to markdown files (`*.md`, `docs/`) set `run_workflow: false`, skipping the pipeline entirely

This avoids burning CI minutes on documentation-only commits.

#### Caveats of the setup config approach

While powerful, especially in monorepo setups, splitting a pipeline dynamically presents additional complexity for a team. There are several tradeoffs to consider:

- **Harder to debug** — with two config files (`setup-config.yml` and `config.yml`), tracing why a pipeline did or didn't run requires understanding both stages. A failed path-filter evaluation can silently skip the entire pipeline, which is confusing if you expected it to run.
- **Local validation gaps** — you can't easily test path-filtering logic locally. The `circleci config validate` command checks syntax but doesn't simulate which paths would match a given commit. You're relying on CI itself to verify the filtering behaviour.
- **Mapping order matters** — the `path-filtering` orb evaluates rules top-to-bottom and last match wins. If a commit touches both `docs/README.md` and `app/main.py`, the final parameter value depends on rule ordering. Getting this wrong can skip builds that should have run.
- **First-push edge cases** — when a new branch is pushed for the first time, the `base-revision` diff against `main` includes all divergent commits, not just the latest push. This is usually fine but can produce unexpected results if the branch has a long history.

Sometimes, a more straightforward single-config pipeline — one that always runs and relies on branch filters or job-level conditions — can be worth the extra cost in credits, especially for smaller teams or single-service repositories where the filtering savings are marginal.

### Pipeline parameters (main config)

`config.yml` defines two workflows controlled by pipeline parameters:

- **`ci`** — activates when `run_workflow` is `true` and `nightly_build` is `false` (commit-triggered builds)
- **`nightly_build`** — activates when `nightly_build` is `true` and `run_workflow` is `false` (scheduled triggers)

The boolean conditions are mutually exclusive, ensuring only one workflow runs per pipeline execution.

### Nightly validations

A [scheduled pipeline](https://circleci.com/docs/scheduled-pipelines/) triggers `config.yml` directly with `nightly_build: true` and `run_workflow: false`, bypassing `setup-config.yml` since there's no commit diff to evaluate.

The nightly workflow runs the full test suite (unit, integration, dependency scan), builds the Docker image, scans the container with Snyk, and verifies the image starts and responds correctly. It does **not** deploy — its purpose is to catch newly disclosed vulnerabilities in dependencies or the base image and to confirm the build remains healthy between code changes.


Because nightly pipelines aren't pressured to complete as quickly as commit-triggered validation, they're a good place for work that would slow down the developer feedback loop:

- **Longer-running test suites** — end-to-end tests, performance benchmarks, or fuzz testing that would be too slow to gate every push can run nightly without blocking anyone.
- **Fresh dependency resolution** — nightly builds can skip the cache and install packages from scratch (`pip install --no-cache-dir`), verifying that dependencies still resolve cleanly rather than relying on a potentially stale cache. This catches issues like yanked packages or incompatible transitive dependency updates that cached installs would mask.
- **Full container rebuild** — similarly, building the Docker image without layer caching ensures the base image and all layers are pulled fresh, surfacing upstream breakage in base images or system packages.

## Security measures

Security is handled at two levels, with credentials scoped tightly to the jobs that need them.

### Vulnerability scanning

- **Dependency scanning** — the `scan-python-deps` job uses the [Snyk orb](https://circleci.com/developer/orbs/orb/snyk/snyk) to scan `requirements.txt` for known vulnerabilities, with a `high` severity threshold. This runs on every commit that triggers the pipeline.
- **Container scanning** — the `scan-docker-image` job scans the built Docker image for OS-level and application vulnerabilities. This runs only on `main`, after the image is built but before it's pushed to any registry.

Both scans also run in the nightly pipeline to catch newly disclosed CVEs.

### Credential isolation with contexts

Each set of credentials is managed through a dedicated [CircleCI context](https://circleci.com/docs/contexts/), attached only to the jobs that need them:

| Context | Scope | Used by |
|---|---|---|
| `snyk` | Snyk API token | `scan-python-deps`, `scan-docker-image` |
| `groundwork_docker` | Docker Hub credentials | `push-docker` |
| `groundwork_supabase` | Supabase database URL | `run-production-migrations` |
| `groundwork_digitalocean` | DigitalOcean API token | `deploy-digitalocean` |

On feature branches, none of the deployment or release contexts are attached — those jobs only run on `main` via branch filters. There is no path through the pipeline where credentials are accessible outside their intended scope.


## Pipeline optimizations

The pipeline uses several strategies to keep feedback fast and avoid redundant work:

- **Parallel quality gates** — unit tests, integration tests, and the Snyk dependency scan run concurrently as individual jobs after dependency installation, so total validation time equals the slowest job rather than the sum of all three. Each test suite fails independently, allowing you to pinpoint and resolve any regressions quicker.
- **Dependency caching** — pip packages are cached with a key derived from `requirements.txt` and the executor architecture. Cache hits skip installation entirely on subsequent runs.
- **Workspace handoff** — installed dependencies are persisted to a workspace once and attached by every downstream job, avoiding repeated pip installs. The built Docker image tarball is similarly passed through the workspace to verification, scanning, and push jobs.
- **Docker layer caching** — the `build-docker` job uses `setup_remote_docker` which allows Docker to reuse unchanged layers from previous builds, reducing image build times on frequent merges.
- **CircleCI orbs** — the `circleci/python` and `snyk/snyk` orbs encapsulate common tasks (package installation, vulnerability scanning) and reduce boilerplate in the config.
- **Pipeline parameter (`docker_repo`)** — the Docker repository name is defined once as a pipeline parameter and referenced throughout, avoiding duplication and making it easy to change.


## Deployment

Once all quality gates pass on `main`, the pipeline proceeds through four stages, each gating on the previous one:

### Container build and verification

The `build-docker` job builds the image and tags it with both `latest` and the commit SHA (`CIRCLE_SHA1`), then exports it as a tarball to the workspace. Two verification jobs run in parallel against the saved image:

- **`verify-docker`** — loads the image, starts it alongside a PostgreSQL container on a shared Docker network, applies database migrations, waits for the health endpoint to return HTTP 200, then runs an E2E API smoke test script (`scripts/e2e_api_smoke.py`). This validates the container actually works end-to-end before it's released.
- **`scan-docker-image`** — runs a Snyk container scan against the image.

### Production database migrations

The `run-production-migrations` job uses the [Supabase CLI](https://supabase.com/docs/guides/cli) (`supabase db push`) to apply any pending migrations to the production database. This runs after the container is verified and scanned, ensuring the database schema is ready before the new application version is deployed.

### Image push

The `push-docker` job authenticates with Docker Hub and pushes the image with both the `latest` and commit SHA tags. This only happens after migrations have succeeded.

### DigitalOcean deployment

The `deploy-digitalocean` job:

1. Installs `doctl` (the DigitalOcean CLI)
2. Plans a release using `circleci run release plan`, registering the deployment intent with CircleCI's [release management](https://circleci.com/docs/release/releases-overview/)
3. Triggers a DigitalOcean App Platform deployment via `doctl apps create-deployment --wait`
4. Updates the release status to `SUCCESS` or `FAILED` based on the outcome

This surfaces deployment history in CircleCI's Deploys tab and makes rollbacks traceable.


## Future optimizations

Several enhancements could build on this foundation as the project and team grow:

- **OIDC authentication for cloud deployments** — the pipeline currently authenticates with DigitalOcean using a long-lived API token stored in a context. For cloud providers that support it (such as AWS, GCP, and Azure), CircleCI's [OIDC token support](https://circleci.com/docs/openid-connect-tokens/) would allow jobs to assume short-lived credentials at runtime, eliminating stored secrets entirely. DigitalOcean App Platform does not currently support OIDC-authenticated deployments, but this would be the preferred approach for any AWS or GCP workloads.
- **Multi-environment promotion with gating** — the pipeline currently deploys directly to production from `main`. A natural next step would be introducing staging and development environments with gated promotion between them — deploying automatically to a staging environment on merge, running post-deploy verification there, and requiring a manual approval step before promoting to production. CircleCI's [approval jobs](https://circleci.com/docs/workflows/#holding-a-workflow-for-a-manual-approval) support this pattern natively.
- **Test parallelism and sharding** — as the test suite grows, CircleCI's [test splitting](https://circleci.com/docs/parallelism-faster-jobs/) can distribute tests across multiple containers based on timing data, keeping feedback times manageable.
- **Config policies** — [CircleCI config policies](https://circleci.com/docs/config-policy-management-overview/) could enforce pipeline governance standards (e.g., requiring security scans, restricting deployment contexts) across an organization's projects.
