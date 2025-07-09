"""Client to interact with kubernetes."""

import base64
import json
import logging
from pathlib import Path

import kubernetes

logger = logging.getLogger(__name__)


class KubernetesClient:
    """Kubernetes client."""

    def __init__(self, host: str, token_path: str, ca_cert_path: str) -> None:
        """Initialize KubernetesClient."""
        logger.debug("Initializing kubernetes client ...")
        with Path.open(Path(token_path)) as file:
            token: str = file.read()

        configuration = kubernetes.client.Configuration(
            host=host,
            api_key={"authorization": token},
            api_key_prefix={"authorization": "Bearer"},
        )
        configuration.verify_ssl = True
        configuration.ssl_ca_cert = ca_cert_path
        self.client = kubernetes.client.ApiClient(configuration)

    def __del__(self) -> None:
        """Destructor for KubernetesClient."""
        logger.debug("Destroying kubernetes client ...")
        self.client.close()

    def check_if_secret_exists(self, namespace: str, secret_name: str) -> bool:
        """Check if the secret exists."""
        logger.debug(
            "Checking if the secret '%s' exists in the namespace '%s' ...",
            secret_name,
            namespace,
        )
        instance = kubernetes.client.CoreV1Api(self.client)
        continue_token: None | str = None

        while True:
            if continue_token:
                response = instance.list_namespaced_secret(namespace, limit=50)
            else:
                response = instance.list_namespaced_secret(
                    namespace,
                    limit=50,
                    _continue=continue_token,
                )

            for item in response.items:
                if item.metadata.name == secret_name:
                    return True

            if response.metadata.remaining_item_count:
                continue_token = response.metadata._continue  # noqa: SLF001
            else:
                break

        return False

    def create_trow_configuration_secret(
        self,
        namespace: str,
        secret_name: str,
        labels: dict[str, str],
        annotations: dict[str, str],
        trow_configuration: dict,
    ) -> None:
        """Create kubernetes secret containing the trow configuration."""
        logger.debug(
            "Creating the secret '%s' in the namespace '%s' ...",
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
                    "config.yaml": base64.b64encode(
                        json.dumps(trow_configuration).encode("utf-8"),
                    ).decode("utf-8"),
                },
            ),
        )

    def update_trow_configuration_secret(
        self,
        namespace: str,
        secret_name: str,
        labels: dict[str, str],
        annotations: dict[str, str],
        trow_configuration: dict,
    ) -> None:
        """Update kubernetes secret containing the trow configuration."""
        logger.debug(
            "Updating the secret '%s' in the namespace '%s' ...",
            secret_name,
            namespace,
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
                    "config.yaml": base64.b64encode(
                        json.dumps(trow_configuration).encode("utf-8"),
                    ).decode("utf-8"),
                },
            ),
        )
