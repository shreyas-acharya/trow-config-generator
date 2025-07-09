"""Generate the trow configuration."""

from pathlib import Path

import boto3
from configuration import RegistryConfig, RegistryType


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
                    "username": registry.auth_configuration["username"],
                    "password": registry.auth_configuration["password"],
                },
            )
        elif registry.registry_type in [
            RegistryType.ECR_PUBLIC,
            RegistryType.ECR,
        ]:
            with Path.open(
                Path(registry.auth_configuration["web_identity_token_file"]),
                encoding="utf-8",
            ) as file:
                token = file.read()

            credentials = boto3.client("sts").assume_role_with_web_identity(
                RoleArn=registry.auth_configuration["role_arn"],
                RoleSessionName=registry.auth_configuration["role_session_name"],
                WebIdentityToken=token,
            )

            if registry.registry_type == RegistryType.ECR_PUBLIC:
                client = boto3.client(
                    "ecr-public",
                    region_name=registry.auth_configuration["region"],
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
                    region_name=registry.auth_configuration["region"],
                    aws_access_key_id=credentials["Credentials"]["AccessKeyId"],
                    aws_secret_access_key=credentials["Credentials"]["SecretAccessKey"],
                    aws_session_token=credentials["Credentials"]["SessionToken"],
                )
                response = client.get_authorization_token(
                    registryIds=[registry.auth_configuration["registry_id"]],
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
