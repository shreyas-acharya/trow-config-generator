"""Main entry point for Trow configuration generator.

Generates Trow registry configuration from YAML file and manages it as a
Kubernetes secret.
"""

import logging
import os
from pathlib import Path

import yaml

from trow_config.config_generator import generate_trow_configuration
from trow_config.configuration import Config, RegistryConfig
from trow_config.kubernetes_client import KubernetesClient


def main() -> None:
    """Entrypoint for Trow configuration generator.

    Loads configuration, generates Trow config, and creates/updates
    Kubernetes secret.
    """
    # Load configuration from environment first to get LOG_LEVEL
    config: Config = Config.model_validate(os.environ)

    # Configure logging with the specified level
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting Trow config generator")
    logger.info("Loaded configuration")

    # Initialize Kubernetes client
    kubernetes_client = KubernetesClient(
        config.K8S_HOST,
        config.SA_TOKEN_FILE,
        config.CA_CERT_FILE,
    )

    # Read registry configuration file
    logger.info(
        "Reading configuration file: %s",
        config.CONFIGURATION_FILE_PATH,
    )
    with Path.open(
        Path(config.CONFIGURATION_FILE_PATH),
        encoding="utf-8",
    ) as file:
        registries_config = yaml.safe_load(file)

    # Parse registry configurations
    registries: list[RegistryConfig] = [
        RegistryConfig(**registry)
        for registry in registries_config["registries"]
    ]
    logger.info("Loaded %d registry configurations", len(registries))

    # Generate Trow configuration
    trow_configuration: dict = generate_trow_configuration(registries)
    logger.info("Generated Trow configuration")

    # Create or update Kubernetes secret
    secret_exists = kubernetes_client.check_if_secret_exists(
        config.NAMESPACE,
        config.SECRET_NAME,
    )

    if secret_exists:
        logger.info("Updating existing secret: %s", config.SECRET_NAME)
        kubernetes_client.update_trow_configuration_secret(
            config.NAMESPACE,
            config.SECRET_NAME,
            config.LABELS,
            config.ANNOTATIONS,
            trow_configuration,
        )
    else:
        logger.info("Creating new secret: %s", config.SECRET_NAME)
        kubernetes_client.create_trow_configuration_secret(
            config.NAMESPACE,
            config.SECRET_NAME,
            config.LABELS,
            config.ANNOTATIONS,
            trow_configuration,
        )

    logger.info("Trow config generator completed successfully")


if __name__ == "__main__":
    main()
