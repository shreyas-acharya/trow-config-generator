"""Kubernetes client for managing Trow configuration secrets.

Handles secret creation, updates, and existence checks with service account
authentication.
"""

import base64
import json
import logging
from pathlib import Path

import kubernetes

logger = logging.getLogger(__name__)


class KubernetesClient:
    """Kubernetes client for Trow configuration secrets."""

    def __init__(self, host: str, token_path: str, ca_cert_path: str) -> None:
        """Initialize Kubernetes client with service account authentication."""
        logger.info("Initializing Kubernetes client")

        # Read service account token
        with Path.open(Path(token_path)) as file:
            token: str = file.read()

        # Configure client with Bearer token authentication
        configuration = kubernetes.client.Configuration(
            host=host,
            api_key={"authorization": token},
            api_key_prefix={"authorization": "Bearer"},
        )
        configuration.verify_ssl = True
        configuration.ssl_ca_cert = ca_cert_path
        self.client = kubernetes.client.ApiClient(configuration)

        logger.info("Kubernetes client initialized")

    def __del__(self) -> None:
        """Clean up Kubernetes client connection."""
        logger.debug("Closing Kubernetes client")
        self.client.close()

    def check_if_secret_exists(self, namespace: str, secret_name: str) -> bool:
        """Check if secret exists in namespace using pagination."""
        logger.debug(
            "Checking for secret '%s' in namespace '%s'",
            secret_name,
            namespace,
        )

        instance = kubernetes.client.CoreV1Api(self.client)
        continue_token: None | str = None

        # Paginate through secrets to find target
        while True:
            if continue_token:
                response = instance.list_namespaced_secret(namespace, limit=50)
            else:
                response = instance.list_namespaced_secret(
                    namespace,
                    limit=50,
                    _continue=continue_token,
                )

            # Check if secret exists in current page
            for item in response.items:
                if item.metadata.name == secret_name:
                    logger.debug("Found secret '%s'", secret_name)
                    return True

            # Continue if more pages exist
            if response.metadata.remaining_item_count:
                continue_token = response.metadata._continue  # noqa: SLF001
            else:
                break

        logger.debug("Secret '%s' not found", secret_name)
        return False

    def create_trow_configuration_secret(
        self,
        namespace: str,
        secret_name: str,
        labels: dict[str, str],
        annotations: dict[str, str],
        trow_configuration: dict,
    ) -> None:
        """Create Kubernetes secret with Trow configuration."""
        logger.info(
            "Creating secret %s in namespace %s",
            secret_name,
            namespace,
        )

        instance = kubernetes.client.CoreV1Api(self.client)
        instance.create_namespaced_secret(
            namespace,
            kubernetes.client.V1Secret(
                api_version="v1",
                kind="Secret",
                type="Opaque",
                metadata=kubernetes.client.V1ObjectMeta(
                    name=secret_name,
                    namespace=namespace,
                    annotations=annotations,
                    labels=labels,
                ),
                data={
                    # Base64 encode JSON configuration
                    "config.yaml": base64.b64encode(
                        json.dumps(trow_configuration).encode("utf-8"),
                    ).decode("utf-8"),
                },
            ),
        )
        logger.info("Created secret '%s'", secret_name)

    def update_trow_configuration_secret(
        self,
        namespace: str,
        secret_name: str,
        labels: dict[str, str],
        annotations: dict[str, str],
        trow_configuration: dict,
    ) -> None:
        """Update existing Kubernetes secret with new Trow configuration."""
        logger.info(
            "Updating secret '%s' in namespace '%s'",
            secret_name,
            f"Updating secret '{secret_name}' in namespace '{namespace}'",
        )

        instance = kubernetes.client.CoreV1Api(self.client)
        instance.patch_namespaced_secret(
            secret_name,
            namespace,
            kubernetes.client.V1Secret(
                metadata=kubernetes.client.V1ObjectMeta(
                    annotations=annotations,
                    labels=labels,
                ),
                data={
                    # Base64 encode JSON configuration
                    "config.yaml": base64.b64encode(
                        json.dumps(trow_configuration).encode("utf-8"),
                    ).decode("utf-8"),
                },
            ),
        )
        logger.info("Updated secret '%s'", secret_name)
