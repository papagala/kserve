# InferenceGraph Retry — E2E Test Branch

This branch contains the E2E test infrastructure for validating the InferenceGraph step retry feature.
The production code lives on [`feat/inferencegraph-step-retry`](https://github.com/papagala/kserve/tree/feat/inferencegraph-step-retry).

## What this tests

An Ensemble InferenceGraph with two steps:
- **flaky-model** — a Python HTTP server that returns `503 Service Unavailable` **50% of the time**
- **stable-model** — a Python HTTP server that always returns `200 OK`

The flaky step has `retry.maxRetries: 5` configured. The test sends 20 requests and verifies that all 20 succeed thanks to the retry logic, then checks the router logs (via `stern`) for retry entries with escalating backoff delays.

## Prerequisites

The following tools must be installed on your machine before running the tests.

| Tool | Tested version | Install |
|---|---|---|
| **Kind** | v0.30.0 | `go install sigs.k8s.io/kind@v0.30.0` or [kind.sigs.k8s.io](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) |
| **kubectl** | v1.33+ | [kubernetes.io/docs/tasks/tools](https://kubernetes.io/docs/tasks/tools/) |
| **Docker** or **Podman** | Docker 24+ / Podman 5+ | [docs.docker.com](https://docs.docker.com/get-docker/) or [podman.io](https://podman.io/getting-started/installation) |
| **Go** | 1.25+ | [go.dev/dl](https://go.dev/dl/) |
| **stern** (optional) | 1.30+ | `brew install stern` or [github.com/stern/stern](https://github.com/stern/stern#installation) |
| **curl** | any | Pre-installed on macOS/Linux |

## Setting up the Kind cluster

If you don't already have a Kind cluster with KServe installed, use the provided scripts:

```bash
# 1. Create a Kind cluster with a local registry on localhost:5001
bash hack/setup/dev/manage.kind-with-registry.sh

# 2. Install Istio, Knative Serving, cert-manager, and KServe
#    (requires bash 4+ on macOS: brew install bash)
bash hack/kserve-install.sh --type all
```

> **Note**: On macOS, the install script requires bash 4+. If `/bin/bash` is version 3.x,
> run with `/opt/homebrew/bin/bash` or install via `brew install bash`.

If you already have a Kind cluster with KServe running, skip to the next section.

## Running the E2E test

### One command (build + deploy + test)

```bash
make test-retry-e2e
```

This will:
1. Build the router and controller images from this branch
2. Push them to the local registry (`localhost:5001`)
3. Apply the updated InferenceGraph CRD
4. Update the controller and router images in the cluster
5. Deploy the flaky-model, stable-model, and InferenceGraph fixtures
6. Send 20 requests and report the results
7. Print router retry logs

### Step by step

```bash
# Build and push router + controller images
make test-retry-e2e-build

# Deploy CRDs, update controller/router, deploy test fixtures
make test-retry-e2e-deploy

# Run the test (20 requests + retry log check)
make test-retry-e2e-run

# Clean up test resources when done
make test-retry-e2e-clean
```

### Configuration

| Variable | Default | Description |
|---|---|---|
| `RETRY_E2E_REGISTRY` | `localhost:5001` | Container registry to push images to |
| `RETRY_E2E_TAG` | `retry-test` | Image tag for router and controller |
| `RETRY_E2E_NS` | `ig-retry-test` | Kubernetes namespace for test resources |
| `ENGINE` | `docker` | Container engine (`docker` or `podman`) |

Example with Podman:

```bash
ENGINE=podman make test-retry-e2e
```

## Expected output

```
=== Sending 20 requests ===
....................
=== Results: 20/20 succeeded, 0/20 failed ===

=== Router retry logs ===
{"msg":"Step returned retriable status, will retry","url":"http://flaky-model.ig-retry-test.svc.cluster.local","attempt":0,"statusCode":503}
{"msg":"Retrying step","url":"http://flaky-model.ig-retry-test.svc.cluster.local","attempt":1,"maxRetries":5,"delay":0.039452613}
{"msg":"Retrying step","url":"http://flaky-model.ig-retry-test.svc.cluster.local","attempt":2,"maxRetries":5,"delay":0.015573684}
{"msg":"Retrying step","url":"http://flaky-model.ig-retry-test.svc.cluster.local","attempt":3,"maxRetries":5,"delay":0.606106227}
=== Done ===
```

All 20 requests should succeed. The retry logs confirm exponential backoff with jitter on the 503 responses from the flaky model.

## Test fixtures

| File | Description |
|---|---|
| [`test/e2e-retry/flaky-model.yaml`](test/e2e-retry/flaky-model.yaml) | ConfigMap + Deployment + Service for a Python server returning 503 50% of the time |
| [`test/e2e-retry/stable-model.yaml`](test/e2e-retry/stable-model.yaml) | ConfigMap + Deployment + Service for a Python server always returning 200 |
| [`test/e2e-retry/inference-graph.yaml`](test/e2e-retry/inference-graph.yaml) | Ensemble InferenceGraph with `retry.maxRetries: 5` on the flaky step |
| [`test/e2e-retry/run-test.sh`](test/e2e-retry/run-test.sh) | Test script: port-forward, warmup, 20 requests, retry log check |
