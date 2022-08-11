import os
from enum import Enum

from box import Box

NAMESPACE = os.getenv("NAMESPACE", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "DEV")
SERVICE_NAME = os.getenv("SERVICE_NAME", "sno-calc")
DOMAIN = os.getenv("DOMAIN", "comp-sci-dev.internal")


class Account(Enum):
    DEV = "869241709189"



def contextualize(string: str, ctx=NAMESPACE, sep="-", append=True):
    groups = [string, ctx] if append else [ctx, string]
    return sep.join(groups).strip(sep)


_region = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-2"))
config = Box(
    {
        "namespace": NAMESPACE,
        "aws": {
            "region": _region,
            "account": Account[ENVIRONMENT].value,
            "tags": {
                "purpose": "testing ecs",
                "country": "NA",
                "customer_facing": "false",
            },
            }[ENVIRONMENT],
        "github_branch": os.getenv("GITHUB_BRANCH", "master"),
        "svc_host": {
            "DEV": f"{SERVICE_NAME}-{NAMESPACE}.svc.{DOMAIN}",
        }[ENVIRONMENT],  # TODO: add correct svc address
    }
)