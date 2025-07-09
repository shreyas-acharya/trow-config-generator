"""Configuration for the Trow Configuration App."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def _split_comma_seperated_dictionary(value: str) -> dict[str, str]:
    items: dict[str, str] = {}
    for item in value.split(","):
        parts: list[str] = item.strip().split(":")
        items[parts[0].strip()] = parts[1].strip()
    return items


class RegistryType(str, Enum):
    """Registry type."""

    DOCKER = "docker"
    ECR_PUBLIC = "ecr-public"
    ECR = "ecr"


class RegistryConfig(BaseModel):
    """Configuration for a registry."""

    alias: str = Field(description="Registry alias")
    host: str = Field(description="Registry host")
    registry_type: RegistryType = Field(
        default=RegistryType.DOCKER,
        description="Registry type",
    )
    auth_configuration: dict = Field(
        default_factory=dict,
        description="Registry authentication configuration",
    )


class Config(BaseModel):
    """Configuration for the Trow Configuration App."""

    CONFIGURATION_FILE_PATH: str = Field(
        default="config.yaml",
        description="Path to the configuration file",
    )

    SA_TOKEN_FILE: str = Field(
        default="/var/run/secrets/kubernetes.io/serviceaccount/token",
    )
    CA_CERT_FILE: str = Field(
        default="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt",
    )
    K8S_HOST: str
    NAMESPACE: str
    SECRET_NAME: str
    LABELS: Annotated[
        dict[str, str],
        BeforeValidator(_split_comma_seperated_dictionary),
    ] = Field(default_factory=dict)
    ANNOTATIONS: Annotated[
        dict[str, str],
        BeforeValidator(_split_comma_seperated_dictionary),
    ] = Field(default_factory=dict)
