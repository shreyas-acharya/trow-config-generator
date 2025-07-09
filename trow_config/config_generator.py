"""Generate the trow configuration."""

import os
from pathlib import Path

import boto3
from configuration import RegistryConfig, RegistryType


def _retrieve_value(configuration: dict) -> str:
    """Retrieve the value from the configuration."""
    if len(configuration) != 1:
        error = ValueError(
            "Invalid configuration. Exactly one value from the following"
            " keys must be provided: value, file, env"
        )
        raise error

    if "value" in configuration:
        return configuration["value"]
    if "file" in configuration:
        with Path.open(
            Path(configuration["file"]),
            encoding="utf-8",
        ) as file:
            return file.read()
    if "env" in configuration:
        return os.environ[configuration["env"]]

    error = ValueError("Invalid configuration. Unknown option.")
    raise error


def generate_trow_configuration(registries: list[RegistryConfig]) -> dict:
    """Generate the trow configuration."""
    trow_configuration: dict = {
        "registry_proxies": {"registries": []},
        "image_validation": {"default": "Allow"},
    }
    for registry in registries:
        if registry.registry_type == RegistryType.DOCKER:
            trow_configuration["registry_proxies"]["registries"].append(
                {
                    "alias": registry.alias,
                    "host": registry.host,
                    "username": _retrieve_value(
                        registry.auth_configuration["username"]
                    ),
                    "password": _retrieve_value(
                        registry.auth_configuration["password"]
                    ),
                },
            )
        elif registry.registry_type in [
            RegistryType.ECR_PUBLIC,
            RegistryType.ECR,
        ]:
            with Path.open(
                Path(
                    _retrieve_value(
                        registry.auth_configuration["web_identity_token_file"]
                    )
                ),
                encoding="utf-8",
            ) as file:
                token = file.read()

            credentials = boto3.client("sts").assume_role_with_web_identity(
                RoleArn=_retrieve_value(registry.auth_configuration["role_arn"]),
                RoleSessionName=_retrieve_value(
                    registry.auth_configuration["role_session_name"]
                ),
                WebIdentityToken=token,
            )

            if registry.registry_type == RegistryType.ECR_PUBLIC:
                client = boto3.client(
                    "ecr-public",
                    region_name=_retrieve_value(registry.auth_configuration["region"]),
                    aws_access_key_id=credentials["Credentials"]["AccessKeyId"],
                    aws_secret_access_key=credentials["Credentials"]["SecretAccessKey"],
                    aws_session_token=credentials["Credentials"]["SessionToken"],
                )
                response = client.get_authorization_token()
                trow_configuration["registry_proxies"]["registries"].append(
                    {
                        "alias": registry.alias,
                        "host": registry.host,
                        "username": "AWS",
                        "password": response["authorizationData"]["authorizationToken"],
                    },
                )
            else:
                client = boto3.client(
                    "ecr",
                    region_name=_retrieve_value(registry.auth_configuration["region"]),
                    aws_access_key_id=credentials["Credentials"]["AccessKeyId"],
                    aws_secret_access_key=credentials["Credentials"]["SecretAccessKey"],
                    aws_session_token=credentials["Credentials"]["SessionToken"],
                )
                response = client.get_authorization_token(
                    registryIds=[
                        _retrieve_value(registry.auth_configuration["registry_id"])
                    ]
                )
                trow_configuration["registry_proxies"]["registries"].append(
                    {
                        "alias": registry.alias,
                        "host": registry.host,
                        "username": "AWS",
                        "password": response["authorizationData"][0][
                            "authorizationToken"
                        ],
                    },
                )
    return trow_configuration
