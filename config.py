import os
from enum import Enum

from box import Box

NAMESPACE = os.getenv("NAMESPACE", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "DEV")
SERVICE_NAME = os.getenv("SERVICE_NAME", "phantom")
DOMAIN = os.getenv("DOMAIN", "phantom.internal")


class Account(Enum):
    DEV = "585905982547"



def contextualize(string: str, ctx=NAMESPACE, sep="-", append=True):
    groups = [string, ctx] if append else [ctx, string]
    return sep.join(groups).strip(sep)


_region = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-2"))
cnf = Box(
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
            },
        "github_branch": os.getenv("GITHUB_BRANCH", "master"),
    }
)