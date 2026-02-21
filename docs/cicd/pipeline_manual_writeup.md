# Groundwork: A Reference CircleCI Pipeline

**Repository:** [github.com/potniq/groundwork](https://github.com/potniq/groundwork)  
**Passing build (full main pipeline):** [View on CircleCI](https://app.circleci.com/workflow/e49a8957-1567-4fe7-98a4-ced1f54db59b)


## High level overview

This pipeline is for a production application - Groundwork by Potniq. The app is a dockerized Python web application with a Postgres database, that is deployed on DigitalOcean App Plaform.

It demonstrates:
- Full build-test-deploy flow on CircleCI
- Security scanning
- Selective running of pipeline - based on the file paths that have changed. A docs update won't trigger a build
- Branch selection. Pushes to default `main` branch will trigger a full deployment. Pushes to other branches will trigger validations only
- Security scanning - dependency and docker container scanning using Snyk
- Nightly scheduled builds that run a 


## Validation flow

## Dynamic workflow selection

### Nightly validations

## Security measures

- Snyk scanning - project dependencies

## Pipeline optimizations

Pipeline features several speed optimizations:

- Parallelism
- Docker Layer Caching
- Dependency caching
- Passing pre-built dependencies along
- CircleCI orbs: cimg/python and snyk/snyk

##  Deployment

- Docker image building
- Validating docker image - e2e test
- Security scanning the docker container
- Deployment - DigitalOcean 


