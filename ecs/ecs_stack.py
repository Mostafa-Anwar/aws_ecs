from xml.dom import UserDataHandler
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
    aws_servicediscovery as sd,
    aws_autoscaling as autoscaling
)
from typing import Mapping, Optional, Sequence
from config import cnf, contextualize, Account
from aws_cdk.pipelines import Step
import config


class PhantomService(cdk.Stack):
    def __init__(self, scope, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc.from_lookup(
            self,
            "default",
            vpc_name="eks-vpc-cdk-poc-mayhem",
        )

        self.sg = ec2.SecurityGroup.from_lookup_by_name(
            self,
            "ecs-sg",
            security_group_name="ecs-sg",
            vpc=vpc
        )

        self.phantom_cluster = ecs.Cluster(
            self,
            "phantom-cluster",
            vpc=vpc,
            
            cluster_name=contextualize("phantom"),
            container_insights=True,
            default_cloud_map_namespace=ecs.CloudMapNamespaceOptions(
                name=(
                    "phantom.internal"
                    if not config.NAMESPACE
                    else f"{config.NAMESPACE}.internal"
                )
            ),
        )

        # self.user_data_script=ec2.UserData.for_linux()
        # self.user_data_script.add_commands("sudo yum install vim")

        # launch_template = ec2.LaunchTemplate(self, "ASG-LaunchTemplate",
        #     launch_template_name="ecs-phantom-launch-template",
        #     instance_type=ec2.InstanceType("t3.medium"),
        #     machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
        #     user_data=self.user_data_script,
        #     key_name="ecs",
        #     # role=iam.IRole.role_name("admin")
        # )
        
        auto_scaling_group = autoscaling.AutoScalingGroup(self, "ASG",
                             vpc=vpc,
                             instance_type=ec2.InstanceType("t3.medium"),
                             machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
                             security_group=self.sg,
                             desired_capacity=1,
                             max_capacity=2,
                             key_name="serv"
                        #      mixed_instances_policy=autoscaling.MixedInstancesPolicy(
                        #      instances_distribution=autoscaling.InstancesDistribution(
                        #      on_demand_percentage_above_base_capacity=100
                        #   ),
                #   launch_template=launch_template
            )


        capacity_provider = ecs.AsgCapacityProvider(self, "AsgCapacityProvider",
                            capacity_provider_name="cap-prov",
                            auto_scaling_group=auto_scaling_group,
                            machine_image_type=ecs.MachineImageType.AMAZON_LINUX_2
        )

        self.phantom_cluster.add_asg_capacity_provider(capacity_provider)

        self.task_definition = ecs.Ec2TaskDefinition(self, "containertaskdef", 
                    network_mode=ecs.NetworkMode.AWS_VPC,
        )
        self.task_definition.add_container("phantomtroop",
            image=ecs.ContainerImage.from_asset("."),
            memory_limit_mib=512,
            cpu=256,
            # command=["python3 -m svc.grpc"],
            # environment=(Mapping["AWS_REGION": "us-east-2"])
        )  

        service = ecs.Ec2Service(self, "container-service", 
                                cluster=self.phantom_cluster, 
                                task_definition=self.task_definition,
                                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT),
                                cloud_map_options=ecs.CloudMapOptions(name='sdservice',
                                    cloud_map_namespace=self.phantom_cluster.default_cloud_map_namespace,
                                    dns_record_type=sd.DnsRecordType.A,
                                    dns_ttl=cdk.Duration.seconds(30)
                                    ),
                                desired_count=1,

        )


# class Stage(cdk.Stage):
#     def __init__(self, scope, construct_id, env, **kwargs):

#         super().__init__(scope, construct_id, env=env, **kwargs)

#         api = PhantomService(
#             self,
#             "phantom-service",
#             env=env,
#             stack_name=contextualize("phantom-service"),
#             tags=cnf.aws.tags,
#         )

# class DeploymentPipeline(cdk.Stack):
#     def __init__(self, scope, construct_id, **kwargs):
#         super().__init__(scope, construct_id, **kwargs)

#         python_version = "3.9.12"

#         self.install_commands = [
#             "ls $(pyenv root)/versions",
#             f"pyenv global {python_version}",
#             "pip install -r requirements-dev.txt",
#             "npm i -g aws-cdk",
#         ]

#         environment_variables = {
#             "GITHUB_BRANCH": cnf.github_branch,
#             "NAMESPACE": cnf.namespace,
#             "DEPLOYED_BY": "CodePipeline",
#         }

#         self.build_environment = codebuild.BuildEnvironment(
#             environment_variables={
#                 k: codebuild.BuildEnvironmentVariable(value=v)
#                 for k, v in environment_variables.items()
#             },
#             privileged=True,
#         )

#         self.build_pipeline("develop", account=Account.DEV)


#     def build_pipeline(
#         self,
#         branch: str,
#         account: Account,
#         pre: Optional[Sequence[Step]] = None,
#     ):

#         environment_name = account.name.lower()

#         _pipeline = codepipeline.Pipeline(
#             self,
#             f"pipeline-internal-{environment_name}",
#             cross_account_keys=True,
#             pipeline_name=contextualize(f"phantom-{environment_name}"),
#         )

#         if not cnf.namespace:

#             pipeline_notification_topic = sns.Topic.from_topic_arn(
#                 self,
#                 f"pipeline-notification-topic-{environment_name}",
#                 topic_arn="arn:aws:sns:us-east-2:015712436568:deployment-events",
#             )

#             _pipeline.notify_on(
#                 f"pipeline-notification-{environment_name}",
#                 target=pipeline_notification_topic,
#                 events=[
#                     codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_FAILED,
#                     codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_SUCCEEDED,
#                     codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_STARTED,
#                     codepipeline.PipelineNotificationEvents.PIPELINE_EXECUTION_CANCELED,
#                 ],
#             )

#         source = pipelines.CodePipelineSource.connection(
#             "Agrium/sno-calc",
#             branch,
#             connection_arn="arn:aws:codestar-connections:us-east-2:585905982547:connection/11bb3fab-f9a7-433b-b478-a399a5dfccbd",
#         )

#         pipeline = pipelines.CodePipeline(
#             self,
#             f"deployment-pipeline-{environment_name}",
#             code_pipeline=_pipeline,
#             self_mutation=True,
#             docker_enabled_for_synth=True,
#             synth=pipelines.ShellStep(
#                 "synth",
#                 input=source,
#                 install_commands=self.install_commands,
#                 commands=["cdk synth"],
#             ),
#             code_build_defaults=pipelines.CodeBuildOptions(
#                 build_environment=self.build_environment,
#                 role_policy=[
#                     iam.PolicyStatement(
#                         sid="assumeLookup",
#                         actions=["sts:AssumeRole"],
#                         resources=["arn:aws:iam::*:role/cdk-hnb659fds-lookup-role-*"],
#                     ),
#                 ],
#             ),
#         )

#         pipeline.add_stage(
#             Stage(
#                 self,
#                 account.name.capitalize(),
#                 env={
#                     "account": account.value,
#                     "region": cnf.aws.region,
#                 },
#             ),
#             pre=pre,
#         )
