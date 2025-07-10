# Trow Configuration Generator

Generates [Trow](https://trow.io) registry configuration and manages it as a Kubernetes secret.

## Overview

This application reads registry configurations from a YAML file, generates authentication tokens for various registry types, and creates/updates Kubernetes secrets containing Trow configuration.

## Features

- **Multiple Registry Support**: Docker Hub, Amazon ECR, Amazon ECR Public
- **Dynamic Authentication**: Auto-generates fresh tokens for ECR registries
- **Kubernetes Integration**: Creates and updates secrets seamlessly
- **Flexible Configuration**: Supports direct values, files, and environment variables

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `K8S_HOST` | Kubernetes API server URL | *required* |
| `NAMESPACE` | Target namespace | *required* |
| `SECRET_NAME` | Secret name | *required* |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CONFIGURATION_FILE_PATH` | Registry config file path | `config.yaml` |
| `SA_TOKEN_FILE` | Service account token | `/var/run/secrets/kubernetes.io/serviceaccount/token` |
| `CA_CERT_FILE` | CA certificate | `/var/run/secrets/kubernetes.io/serviceaccount/ca.crt` |
| `LABELS` | Secret labels | `key1:value1,key2:value2` |
| `ANNOTATIONS` | Secret annotations | `key1:value1,key2:value2` |

### Registry Configuration File

```yaml
registries:
  - alias: "docker-hub"
    host: "registry-1.docker.io"
    registry_type: "docker"
    auth_configuration:
      username:
        value: "your-username"
      password:
        env: "DOCKER_PASSWORD"
  
  - alias: "ecr-public"
    host: "public.ecr.aws"
    registry_type: "ecr-public"
    auth_configuration:
      role_arn:
        value: "arn:aws:iam::123456789012:role/ECRRole"
      role_session_name:
        value: "trow-config-session"
      web_identity_token_file:
        file: "/var/run/secrets/eks.amazonaws.com/serviceaccount/token"
      region:
        value: "us-east-1"
  
  - alias: "ecr-private"
    host: "123456789012.dkr.ecr.us-east-1.amazonaws.com"
    registry_type: "ecr"
    auth_configuration:
      role_arn:
        value: "arn:aws:iam::123456789012:role/ECRRole"
      role_session_name:
        value: "trow-config-session"
      web_identity_token_file:
        file: "/var/run/secrets/eks.amazonaws.com/serviceaccount/token"
      region:
        value: "us-east-1"
      registry_id:
        value: "123456789012"
```

## Usage

### Local Development

```bash
export K8S_HOST="https://kubernetes.default.svc"
export NAMESPACE="default"
export SECRET_NAME="trow-config"
python main.py
```

### Kubernetes Job

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: trow-config-generator
spec:
  template:
    spec:
      serviceAccountName: trow-config-generator
      containers:
      - name: trow-config-generator
        image: trow-config-generator:latest
        env:
        - name: K8S_HOST
          value: "https://kubernetes.default.svc"
        - name: NAMESPACE
          value: "default"
        - name: SECRET_NAME
          value: "trow-config"
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
      volumes:
      - name: config
        configMap:
          name: trow-registry-config
      restartPolicy: Never
```

### RBAC Configuration

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: trow-config-generator
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: trow-config-generator
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "create", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: trow-config-generator
subjects:
- kind: ServiceAccount
  name: trow-config-generator
roleRef:
  kind: Role
  name: trow-config-generator
  apiGroup: rbac.authorization.k8s.io
```

## Registry Types

### Docker
Standard Docker registries with username/password authentication.

### ECR Public
Amazon ECR Public with IAM role authentication.

### ECR Private
Amazon ECR Private with IAM role authentication and registry ID.

## Development

```bash
# Install dependencies
poetry install

# Run application
poetry run python main.py

# Run with debug logging
export LOG_LEVEL=DEBUG
poetry run python main.py
```

## Requirements

- Python 3.13+
- Kubernetes cluster access
- Service account with secret permissions
- Dependencies: boto3, kubernetes, pydantic, pyyaml
