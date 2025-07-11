"""Generate Trow configuration from registry definitions.

Supports Docker, ECR, and ECR Public registries with appropriate
authentication.
"""

import base64
import json
import logging
import os
import time
from pathlib import Path

import boto3
import jwt
import requests

from trow_config.configuration import RegistryConfig, RegistryType

logger = logging.getLogger(__name__)


def _generate_jwt_token(
    private_key: str, token_expiry_seconds: int, app_id: int
) -> str:
    """Generate a JWT token using the private key.

    Args:
        private_key (str): Github App private key
        token_expiry_seconds (int): JWT Token expiry time in seconds
        app_id: Github App ID

    Returns:
        (str) encoded jwt token

    """
    logger.info("Generating JWT Token ...")
    signing_key: jwt.AbstractJWKBase = jwt.jwk_from_pem(
        private_key.encode("utf-8")
    )

    payload: dict = {
        "iat": int(time.time()),
        "exp": int(time.time()) + token_expiry_seconds,
        "iss": str(app_id),
    }
    jwt_instance: jwt.JWT = jwt.JWT()
    return jwt_instance.encode(payload, signing_key, alg="RS256")


def _get_app_installation_id(jwt_token: str, app_id: int) -> str:
    """Retrieve the Github App installation token.

    Args:
        jwt_token (str) : JWT token
        app_id (int) : Github App ID

    Returns:
        (str)

    """
    logger.info(
        "Calculating Github App Installation ID for the Github app with ID %d",
        app_id,
    )
    page: int = 0
    app_installation_id: str | None = None
    while True:
        page += 1
        response = requests.get(
            f"https://api.github.com/app/installations?page={page}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {jwt_token}",
                "X-Github-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
        installations: list = json.loads(response.content)
        if not installations:
            break
        for installation in installations:
            if installation["app_id"] == app_id:
                app_installation_id = installation["id"]
                break

    if not app_installation_id:
        raise ValueError(
            "Error when calculating installation id for the github app with app id : %d",
            app_id,
        )
    return app_installation_id


def _generate_access_token(
    app_id: int, private_key: str, expiry_seconds: int
) -> str:
    """Generate a installation access token.

    Args:
        app_id (str) : Github App ID
        private_key (str) : Github App private key
        expiry_seconds (int) : JWT token expiry time

    Returns:
        (str) installation access token

    """
    logger.info("Generating installation access token ...")
    jwt_token: str = _generate_jwt_token(
        private_key=private_key,
        token_expiry_seconds=expiry_seconds,
        app_id=app_id,
    )
    app_installation_id: str = _get_app_installation_id(
        jwt_token=jwt_token, app_id=app_id
    )
    response = requests.post(
        f"https://api.github.com/app/installations/"
        f"{app_installation_id}/access_tokens",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
            "X-Github-Api-Version": "2022-11-28",
        },
        timeout=10,
    )
    return json.loads(response.content)["token"]


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
        elif registry.registry_type == RegistryType.GHCR:
            # Github Container Registry authentication
            trow_configuration["registry_proxies"]["registries"].append(
                {
                    "alias": registry.alias,
                    "host": registry.host,
                    "username": _retrieve_value(
                        registry.auth_configuration["username"],
                    ),
                    "password": _generate_access_token(
                        int(
                            _retrieve_value(
                                registry.auth_configuration["app_id"]
                            )
                        ),
                        _retrieve_value(
                            registry.auth_configuration["private_key"]
                        ),
                        600,
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

            decoded_token = base64.b64decode(auth_token).decode("utf-8")
            username, password = decoded_token.split(":")
            trow_configuration["registry_proxies"]["registries"].append(
                {
                    "alias": registry.alias,
                    "host": registry.host,
                    "username": username,
                    "password": password,
                },
            )

    logger.info(
        "Generated configuration for %d registries",
        len(trow_configuration["registry_proxies"]["registries"]),
    )
    return trow_configuration
