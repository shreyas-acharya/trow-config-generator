"""Generate Trow configuration from registry definitions.

Supports Docker, ECR, and ECR Public registries with appropriate
authentication.
"""

import logging
import os
from pathlib import Path

import boto3

from trow_config.configuration import RegistryConfig, RegistryType

logger = logging.getLogger(__name__)


def _retrieve_value(configuration: dict) -> str:
    """Retrieve configuration value from direct value, file, or environment.

    Args:
        configuration: Dict with one of: 'value', 'file', 'env'

    Returns:
        The resolved value as string

    """
    if len(configuration) != 1:
        raise ValueError(
            "Configuration must have exactly one key: value, file, or env",
        )

    if "value" in configuration:
        return configuration["value"]

    if "file" in configuration:
        with Path.open(
            Path(configuration["file"]),
            encoding="utf-8",
        ) as file:
            return file.read().strip()

    if "env" in configuration:
        return os.environ[configuration["env"]]

    raise ValueError("Unknown configuration option")


def generate_trow_configuration(registries: list[RegistryConfig]) -> dict:
    """Generate Trow configuration from registry list.

    Args:
        registries: List of registry configurations

    Returns:
        Dict containing Trow configuration

    """
    logger.info("Processing %d registries", len(registries))

    trow_configuration: dict = {
        "registry_proxies": {"registries": []},
        "image_validation": {"default": "Allow", "allow": [], "deny": []},
    }

    for registry in registries:
        logger.info(
            "Processing registry: %s (%s)",
            registry.alias,
            registry.registry_type,
        )

        if registry.registry_type == RegistryType.DOCKER:
            # Standard Docker registry authentication
            trow_configuration["registry_proxies"]["registries"].append(
                {
                    "alias": registry.alias,
                    "host": registry.host,
                    "username": _retrieve_value(
                        registry.auth_configuration["username"],
                    ),
                    "password": _retrieve_value(
                        registry.auth_configuration["password"],
                    ),
                },
            )

        elif registry.registry_type in [
            RegistryType.ECR_PUBLIC,
            RegistryType.ECR,
        ]:
            # AWS ECR authentication via IAM role assumption
            logger.debug("Assuming AWS role for %d", registry.alias)

            credentials = boto3.client("sts").assume_role_with_web_identity(
                RoleArn=_retrieve_value(
                    registry.auth_configuration["role_arn"],
                ),
                RoleSessionName=_retrieve_value(
                    registry.auth_configuration["role_session_name"],
                ),
                WebIdentityToken=_retrieve_value(
                    registry.auth_configuration["web_identity_token_file"],
                ),
            )

            if registry.registry_type == RegistryType.ECR_PUBLIC:
                # ECR Public authentication
                client = boto3.client(
                    "ecr-public",
                    region_name=_retrieve_value(
                        registry.auth_configuration["region"],
                    ),
                    aws_access_key_id=credentials["Credentials"][
                        "AccessKeyId"
                    ],
                    aws_secret_access_key=credentials["Credentials"][
                        "SecretAccessKey"
                    ],
                    aws_session_token=credentials["Credentials"][
                        "SessionToken"
                    ],
                )
                response = client.get_authorization_token()
                auth_token = response["authorizationData"][
                    "authorizationToken"
                ]

            else:
                # ECR Private authentication
                client = boto3.client(
                    "ecr",
                    region_name=_retrieve_value(
                        registry.auth_configuration["region"],
                    ),
                    aws_access_key_id=credentials["Credentials"][
                        "AccessKeyId"
                    ],
                    aws_secret_access_key=credentials["Credentials"][
                        "SecretAccessKey"
                    ],
                    aws_session_token=credentials["Credentials"][
                        "SessionToken"
                    ],
                )
                response = client.get_authorization_token(
                    registryIds=[
                        _retrieve_value(
                            registry.auth_configuration["registry_id"],
                        ),
                    ],
                )
                auth_token = response["authorizationData"][0][
                    "authorizationToken"
                ]

            trow_configuration["registry_proxies"]["registries"].append(
                {
                    "alias": registry.alias,
                    "host": registry.host,
                    "username": "AWS",
                    "password": auth_token,
                },
            )

    logger.info(
        "Generated configuration for %d registries",
        len(trow_configuration["registry_proxies"]["registries"]),
    )
    return trow_configuration
