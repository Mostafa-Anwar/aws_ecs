import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    pipelines,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_ecs_patterns as ecs_patterns,
    aws_logs as logs,
    aws_iam as iam,
    aws_sns as sns,
)
from typing import Optional, Sequence
from config import config, contextualize, Account
from aws_cdk.pipelines import Step



class PhantomService(cdk.Stack):
    def __init__(self, scope, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_lookup(
            self,
            "default",
            vpc_name="default",
        )

        self.sculptor_cluster = ecs.Cluster(
            self,
            "phantom-cluster",
            vpc=vpc,
            cluster_name=config.contextualize("phantom"),
            container_insights=True,
            default_cloud_map_namespace=ecs.CloudMapNamespaceOptions(
                name=(
                    "phantom.internal"
                    if not config.NAMESPACE
                    else f"{config.NAMESPACE}.com"
                )
            ),
        )

        task_definition = ecs.Ec2TaskDefinition(self, "containertaskdef")
        task_definition.add_container("TheContainer",
            image=ecs.ContainerImage.from_asset("."),
            memory_limit_mi_b=256,
        )      

        self.sculptor_cluster.enable_fargate_capacity_providers()


class Stage(cdk.Stage):
    def __init__(self, scope, construct_id, env, **kwargs):

        super().__init__(scope, construct_id, env=env, **kwargs)

        api = PhantomService(
            self,
            "phantom-service",
            env=env,
            stack_name=contextualize("phantom-service"),
            tags=config.aws.tags,
        )

class DeploymentPipeline(cdk.Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        python_version = "3.9.12"

        self.install_commands = [
            "ls $(pyenv root)/versions",
            f"pyenv global {python_version}",
            "pip install -r requirements-dev.txt",
            "npm i -g aws-cdk",
        ]

        environment_variables = {
            "GITHUB_BRANCH": config.github_branch,
            "NAMESPACE": config.namespace,
            "DEPLOYED_BY": "CodePipeline",
        }

        self.build_environment = codebuild.BuildEnvironment(
            environment_variables={
                k: codebuild.BuildEnvironmentVariable(value=v)
                for k, v in environment_variables.items()
            },
            privileged=True,
        )

        self.build_pipeline("develop", account=Account.DEV)


        self.build_pipeline(
            "main",
            account=Account.PRD,
            pre=[pipelines.ManualApprovalStep("PromoteToProd")],
        )

    def build_pipeline(
        self,
        branch: str,
        account: Account,
        pre: Optional[Sequence[Step]] = None,
    ):

        environment_name = account.name.lower()

        _pipeline = codepipeline.Pipeline(
            self,
            f"pipeline-internal-{environment_name}",
            cross_account_keys=True,
            pipeline_name=contextualize(f"phantom-{environment_name}"),
        )

        if not config.namespace:

            pipeline_notification_topic = sns.Topic.from_topic_arn(
                self,
                f"pipeline-notification-topic-{environment_name}",
                topic_arn="arn:aws:sns:us-east-2:015712436568:deployment-events",
            )

            _pipeline.notify_on(
                f"pipeline-notification-{environment_name}",
                target=pipeline_notification_topic,
                events=[
                    codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_FAILED,
                    codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_SUCCEEDED,
                    codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_STARTED,
                    codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_CANCELED,
                ],
            )

        source = pipelines.CodePipelineSource.connection(
            "Agrium/sno-calc",
            branch,
            connection_arn="arn:aws:codestar-connections:us-east-2:015712436568:connection/ae948ef8-c2b0-44c6-afd2-3465c2b32f66",
        )

        pipeline = pipelines.CodePipeline(
            self,
            f"deployment-pipeline-{environment_name}",
            code_pipeline=_pipeline,
            self_mutation=True,
            docker_enabled_for_synth=True,
            synth=pipelines.ShellStep(
                "synth",
                input=source,
                install_commands=self.install_commands,
                commands=["cdk synth"],
            ),
            code_build_defaults=pipelines.CodeBuildOptions(
                build_environment=self.build_environment,
                role_policy=[
                    iam.PolicyStatement(
                        sid="assumeLookup",
                        actions=["sts:AssumeRole"],
                        resources=["arn:aws:iam::*:role/cdk-hnb659fds-lookup-role-*"],
                    ),
                ],
            ),
        )

        pipeline.add_stage(
            Stage(
                self,
                account.name.capitalize(),
                env={
                    "account": account.value,
                    "region": config.aws.region,
                },
            ),
            pre=pre,
        )
