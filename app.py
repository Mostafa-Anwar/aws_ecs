#!/usr/bin/env python3
import os

import aws_cdk as cdk
import config
from ecs.ecs_stack import Cluster


app = cdk.App()

Cluster(
        app,
        config.contextualize("ECS"),
        stack_name=config.contextualize("troop"),
        env=cdk.Environment(
            account=config.aws.account_map["DEV"],
            region=config.aws.region,
        ),
        tags=config.aws.tags,
    )

app.synth()
