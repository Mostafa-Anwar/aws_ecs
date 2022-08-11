#!/usr/bin/env python3
import os

import aws_cdk as cdk
from config import contextualize, Account, cnf
from ecs.ecs_stack import PhantomService


app = cdk.App()

PhantomService(
        app,
        contextualize("ECS"),
        stack_name=contextualize("ecs"),
        env=cdk.Environment(
            account=Account.DEV.value,
            region=cnf.aws.region,
        ),
        tags=cnf.aws.tags,
    )

app.synth()
