# Groundwork: A Reference CircleCI Pipeline

**Repository:** [github.com/potniq/groundwork](https://github.com/potniq/groundwork)  
**Passing build (full main pipeline):** [View on CircleCI](https://app.circleci.com/workflow/e49a8957-1567-4fe7-98a4-ced1f54db59b)



## What This Pipeline Demonstrates

This is a production CI/CD pipeline for a Python/FastAPI. It covers the full lifecycle from dependency management through automated testing, security scanning, container build and verification, release management, and deployment to DigitalOcean App Platform. 

The pipeline is designed around a real application, so the patterns here reflect the kinds of decisions you would make when shipping production software.

## Pipeline Structure

The pipeline uses two configuration files with different entry points depending on how a build is triggered. Both configuration are located in `.circleci/` dir.

`setup-config.yml` is the entry point for commit-triggered builds. It's a setup workflow - first stage in a [dynamic CircleCI pipeline](https://circleci.com/docs/guides/orchestrate/dynamic-config/) and uses the `path-filtering` orb to evaluate what changed in the commit. 
File patterns are mapped to a `run_workflow` pipeline parameter — changes to application code, tests, migrations, the Dockerfile, dependencies, or pipeline config itself set `run_workflow` to `true` and hand off to the main config. Changes limited to markdown or documentation files set it to `false`, skipping the pipeline entirely and avoiding unnecessary compute.

`config.yml` is the main pipeline configuration. It contains all job definitions and two workflows, selected by pipeline parameters: `build-test-deploy` runs when `run_workflow` is true (commit-triggered builds), and `nightly_build` runs when `nightly_build` is true (scheduled triggers). The two workflows are mutually exclusive — the parameter conditions ensure only one activates per pipeline run.

Scheduled pipelines trigger `config.yml` directly with `nightly_build: true` and `run_workflow: false`, bypassing `setup-config.yml` entirely since there's no commit to evaluate.

## Commit-Triggered Pipeline

### Feature Branches

On feature branches, the pipeline focuses on fast feedback. A dedicated `install-deps` job installs Python packages once, using a CircleCI cache keyed by `requirements.txt`. The installed packages are persisted to a workspace so every downstream job reuses them without reinstalling. 

Three jobs then run in parallel: unit tests provide fast isolated feedback, integration tests validate database interactions against a PostgreSQL instance running as a sidecar container, and a Snyk dependency scan checks `requirements.txt` for known vulnerabilities. Both test jobs publish JUnit results and artifacts to CircleCI for visibility. Nothing gets built or shipped on feature branches.

### Default Branch

On `main`, the pipeline runs the same test and scan gates, then extends into container, release, and deployment stages. Each stage gates on the one before it — deployment is only reachable if every upstream check has passed.

**Container build and validation:** The pipeline builds a Docker image with Docker layer caching enabled, reducing build times by reusing unchanged layers between runs. The image is tagged with both `latest` and the commit SHA, then exported as a tarball to the workspace. Two jobs run against the built image: one loads and starts the container alongside a PostgreSQL instance, applies migrations, verifies the health endpoint responds, and runs E2E API smoke tests. The other runs a Snyk security scan against the image. Both happen before the image reaches any registry.

**Production migrations:** Once the container is verified and scanned, production database migrations run against Supabase using `supabase db push`.

**Release:** The verified image is pushed to Docker Hub with versioned and `latest` tags.

**Deployment:** The pipeline triggers a DigitalOcean App Platform deployment via `doctl`, using CircleCI's release management to plan the deploy beforehand and update its status to `SUCCESS` or `FAILED` based on the outcome. This surfaces deployment history in CircleCI's deploys view and makes rollbacks available if needed.

## Nightly Pipeline

A scheduled pipeline runs nightly, independently of code changes. It runs the full test suite — unit tests, integration tests against the PostgreSQL sidecar, and the Snyk dependency scan — then builds the Docker image, runs the Snyk container scan, and verifies the image starts and responds correctly.

The nightly pipeline does not deploy. Its purpose is to catch newly disclosed vulnerabilities in dependencies or the container image, and to confirm the build remains healthy, without waiting for a code change to trigger a run.

## Security and Credential Handling

Credentials are managed through CircleCI contexts, each scoped to the jobs that need them. The `snyk` context attaches only to scan jobs. `groundwork_docker` attaches to Docker Hub push operations. `groundwork_supabase` is limited to the migration job. `groundwork_digitalocean` is scoped to the deployment job. On feature branches, none of the release or deployment contexts are attached — those jobs only run on `main`. There is no path through the pipeline where credentials are accessible outside their intended scope.

## CircleCI Features in Use

- **Setup workflows with path filtering** skip the full pipeline for documentation-only changes
- **Pipeline parameters** with mutual exclusion conditions cleanly separate commit-triggered and scheduled workflows in a single config
- **Docker layer caching** on the build job reduces image build times across frequent merges and nightly runs
- **Workspace handoff** passes cached dependencies and the Docker image tarball between jobs without rebuilding
- **Sidecar containers** provide real PostgreSQL instances for both integration tests and container verification
- **Branch filters** restrict release and deployment stages to the default branch
- **Parallelized quality gates** run unit tests, integration tests, and dependency scanning concurrently
- **Strict `requires` chains** enforce stage ordering so deployment can only proceed after all upstream jobs succeed
- **JUnit test results and stored artifacts** provide observability across every run
- **Scheduled pipelines** run nightly security scans and build verification independently of code changes
- **Release management** (plan/update) surfaces deployment status in the deploys view and enables rollbacks

## Future Optimizations

Several enhancements could build on this foundation. Automated post-deploy health verification or rollback gates would complement the existing manual rollback capability. Config policies could enforce pipeline governance standards across an organization. Snyk scan thresholds could be tuned by severity level and allowlist policy based on risk tolerance. As the test suite grows, parallel test sharding would keep feedback times manageable. Where the deployment platform supports it, OIDC-based cloud authentication would further reduce reliance on long-lived credentials. Dockerfile layer ordering could also be optimized to maximize cache hit rates.