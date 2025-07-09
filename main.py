"""Main module."""

import os
from pathlib import Path

import yaml

from trow_config.config_generator import generate_trow_configuration
from trow_config.configuration import Config, RegistryConfig
from trow_config.kubernetes_client import KubernetesClient


def main() -> None:
    """Entrypoint for trow config app."""
    config: Config = Config.model_validate(os.environ)
    kubernetes_client = KubernetesClient(
        config.K8S_HOST,
        config.SA_TOKEN_FILE,
        config.CA_CERT_FILE,
    )

    with Path.open(
        Path(config.CONFIGURATION_FILE_PATH),
        encoding="utf-8",
    ) as file:
        registries_config = yaml.safe_load(file)

    registries: list[RegistryConfig] = [
        RegistryConfig(
            **registry,
        )
        for registry in registries_config["registries"]
    ]

    trow_configuration: dict = generate_trow_configuration(registries)

    if kubernetes_client.check_if_secret_exists(
        config.NAMESPACE,
        config.SECRET_NAME,
    ):
        kubernetes_client.update_trow_configuration_secret(
            config.NAMESPACE,
            config.SECRET_NAME,
            config.LABELS,
            config.ANNOTATIONS,
            trow_configuration,
        )
    else:
        kubernetes_client.create_trow_configuration_secret(
            config.NAMESPACE,
            config.SECRET_NAME,
            config.LABELS,
            config.ANNOTATIONS,
            trow_configuration,
        )


if __name__ == "__main__":
    main()
