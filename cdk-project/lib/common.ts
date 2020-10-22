import cdk = require("@aws-cdk/core");
import codebuild = require("@aws-cdk/aws-codebuild");
import ecr = require("@aws-cdk/aws-ecr");
import events = require("@aws-cdk/aws-events");
import targets = require("@aws-cdk/aws-events-targets");
import iam = require("@aws-cdk/aws-iam");
import lambda = require("@aws-cdk/aws-lambda");

import path = require("path");
import { ManagedPolicy } from "@aws-cdk/aws-iam";
import { Duration, Stack } from "@aws-cdk/core";
import { Schedule } from "@aws-cdk/aws-events";

export class Constants {
    static readonly buildImage = {
        repo: "sagemaker-codebuild",
        tag: "cpu",
    };

    static readonly defaultGitHubOwner = "aws";
    static readonly exampleNotebooksRepo = "amazon-sagemaker-examples";

    static readonly gitHubOAuthSecretId = "/codebuild/github/oauth";

    static readonly region = "us-west-2";
}

export class Environments {
    private static readonly exampleNotebooksAccountId = "521695447989";

    static current(): cdk.Environment {
        return {
            account: process.env.AWS_DEFAULT_ACCOUNT,
            region: process.env.AWS_DEFAULT_REGION,
        };
    }

    static sandbox(): cdk.Environment {
        const env = Environments.current();

        if (env.account && Environments.isProdAccount(env.account)) {
            process.stderr.write(
                "\nWARNING: Do not deploy Sandbox stacks to the example notebooks account!\n\n",
            );
        }

        return env;
    }

    static prod(): cdk.Environment {
        return { account: Environments.exampleNotebooksAccountId, region: Constants.region };
    }

    static isProdAccount(accountId: string): boolean {
        return Environments.exampleNotebooksAccountId === accountId;
    }

    static prefix(accountId: string): string {
        if (Environments.isProdAccount(accountId)) {
            return "Prod";
        }

        return "Sandbox";
    }
}

interface ProjectProps {
    name?: string;
    owner?: string;
    repo: string;
    branch?: string;
    enablePullRequestBuild?: boolean;
    enableReleaseBuild?: boolean;
    enableAutomaticRelease?: boolean;
    computeType?: codebuild.ComputeType;
    customImage?: codebuild.IBuildImage;
    timeout?: Duration;
    deploymentTimeout?: Duration;
    pullRequestBuildSpec?: string;
    releaseBuildSpec?: string;
    deployBuildSpec?: string;
    addSourceToReleasePipeline?: boolean;
    releasePipelineScheduleExpression?: string;
    additionalBuildProjects?: Build[];
}

interface BuildProps {
    name: string;
    computeType?: codebuild.ComputeType;
    customImage?: codebuild.IBuildImage;
    timeout?: Duration;
    pullRequestBuildSpec: codebuild.BuildSpec;
}

export class Build {
    readonly name: string;
    readonly computeType: codebuild.ComputeType;
    readonly customImage?: codebuild.IBuildImage;
    readonly timeout: Duration;
    readonly pullRequestBuildSpec: codebuild.BuildSpec;

    constructor(props: BuildProps) {
        this.name = props.name;
        this.computeType = props.computeType || codebuild.ComputeType.SMALL;
        this.customImage = props.customImage;
        this.timeout = props.timeout === undefined ? Duration.hours(1) : props.timeout;
        this.pullRequestBuildSpec = props.pullRequestBuildSpec;
    }
}

export class Project {
    readonly name: string;
    readonly owner: string;
    readonly repo: string;
    readonly branch: string;
    readonly enablePullRequestBuild: boolean;
    readonly enableReleaseBuild: boolean;
    readonly computeType: codebuild.ComputeType;
    readonly customImage?: codebuild.IBuildImage;
    readonly timeout: Duration;
    readonly deploymentTimeout: Duration;
    readonly pullRequestBuildSpec: codebuild.BuildSpec;
    readonly releaseBuildSpec: codebuild.BuildSpec;
    readonly deployBuildSpec: codebuild.BuildSpec;
    readonly addSourceToReleasePipeline: boolean;
    readonly releasePipelineScheduleExpression: string;
    readonly additionalBuildProjects: Build[];
    readonly enableAutomaticRelease: boolean;

    constructor(props: ProjectProps) {
        this.repo = props.repo;
        this.owner = props.owner === undefined ? "aws" : props.owner;
        this.branch = props.branch === undefined ? "master" : props.branch;
        this.enablePullRequestBuild =
            props.enablePullRequestBuild === undefined ? true : props.enablePullRequestBuild;
        this.enableReleaseBuild =
            props.enableReleaseBuild === undefined ? true : props.enableReleaseBuild;
        this.computeType = props.computeType || codebuild.ComputeType.SMALL;
        this.customImage = props.customImage;
        this.timeout = props.timeout === undefined ? Duration.hours(1) : props.timeout;
        this.deploymentTimeout =
            props.deploymentTimeout === undefined ? Duration.hours(8) : props.deploymentTimeout;
        this.pullRequestBuildSpec =
            props.pullRequestBuildSpec === undefined
                ? codebuild.BuildSpec.fromSourceFilename("buildspec.yml")
                : codebuild.BuildSpec.fromSourceFilename(props.pullRequestBuildSpec);
        this.releaseBuildSpec =
            props.releaseBuildSpec === undefined
                ? codebuild.BuildSpec.fromSourceFilename("buildspec-release.yml")
                : codebuild.BuildSpec.fromSourceFilename(props.releaseBuildSpec);
        this.deployBuildSpec =
            props.deployBuildSpec === undefined
                ? codebuild.BuildSpec.fromSourceFilename("buildspec-deploy.yml")
                : codebuild.BuildSpec.fromSourceFilename(props.deployBuildSpec);
        this.addSourceToReleasePipeline =
            props.addSourceToReleasePipeline === undefined
                ? false
                : props.addSourceToReleasePipeline;
        this.additionalBuildProjects =
            props.additionalBuildProjects === undefined ? [] : props.additionalBuildProjects;
        this.enableAutomaticRelease =
            props.enableAutomaticRelease === undefined ? true : props.enableAutomaticRelease;

        // default is 15h15 UTC, M-F (07h15 PDT, 08h15 PST)
        this.releasePipelineScheduleExpression =
            props.releasePipelineScheduleExpression === undefined
                ? "cron(15 15 ? * MON-FRI *)"
                : props.releasePipelineScheduleExpression;

        if (props.name === undefined) {
            // default is <owner>-<repo>-<branch>
            // but 'aws' and 'master' are omitted for brevity
            this.name = `${this.owner}-${this.repo}-${this.branch}`
                .replace(/^aws-/, "")
                .replace(/-master$/, "");
        } else {
            this.name = props.name;
        }
    }
}

export function stackId(prefix: string, base: string, props: cdk.StackProps): string {
    if (props.env === undefined || props.env.region === undefined) {
        throw Error("region is undefined");
    }

    return `${prefix}${base}`;
}

export function importBuildImage(scope: cdk.Stack, env?: cdk.Environment): codebuild.IBuildImage {
    const image = Constants.buildImage;

    let arn;
    if (env !== undefined) {
        arn = `arn:aws:ecr:${env.region}:${env.account}:repository/${image.repo}`;
    } else {
        arn = `arn:aws:ecr:${Stack.of(scope).region}:${Stack.of(scope).account}:repository/${
            image.repo
        }`;
    }

    const repo = ecr.Repository.fromRepositoryAttributes(scope, "BuildImage", {
        repositoryArn: arn,
        repositoryName: `${image.repo}`,
    });

    return codebuild.LinuxBuildImage.fromEcrRepository(repo, image.tag);
}

export function enableCrossAccountImagePull(project: codebuild.Project): void {
    const cfnProject = project.node.findChild("Resource") as codebuild.CfnProject;
    cfnProject.addPropertyOverride("Environment.ImagePullCredentialsType", "SERVICE_ROLE");

    const projectPolicy = new iam.PolicyStatement();
    projectPolicy.addActions(
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
    );
    projectPolicy.addAllResources();
    project.addToRolePolicy(projectPolicy);
}

export function enableSageMakerOperation(project: codebuild.Project): void {
    const cfnProject = project.node.findChild("Resource") as codebuild.CfnProject;
    cfnProject.addPropertyOverride("Environment.ImagePullCredentialsType", "SERVICE_ROLE");

    const projectPolicy = new iam.PolicyStatement();
    projectPolicy.addActions(
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:CreateVpc",
        "ec2:CreateSubnet",
        "ec2:CreateSecurityGroup",
        "ec2:CreateTags",
        "ec2:DescribeVpcEndpointServices",
        "iam:GetRole",
        "kms:CreateKey",
        "kms:CreateAlias",
        "kms:CreateGrant",
        "kms:PutKeyPolicy",
        "s3:PutEncryptionConfiguration",
        "s3:PutBucketPolicy",
    );
    projectPolicy.addResources("*");

    project.addToRolePolicy(projectPolicy);

    if (project.role) {
        project.role.addManagedPolicy(
            ManagedPolicy.fromAwsManagedPolicyName("AmazonSageMakerFullAccess"),
        );
    }
}

function createEndpointCleaningLambda(
    stack: cdk.Stack,
    role: iam.IRole,
    maxEndpointAge: Duration,
): void {
    const func = new lambda.Function(stack, "EndpointCleaningLambda", {
        description: "Clean endpoints created by tests",
        role: role,
        code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/python-functions")),
        handler: "clean_endpoints.lambda_handler",
        runtime: lambda.Runtime.PYTHON_3_6,
        timeout: Duration.minutes(15),
        environment: {
            MAX_ENDPOINT_AGE_IN_MINUTES: maxEndpointAge.toMinutes().toString(),
        },
    });

    const rule = new events.Rule(stack, "ScheduledEndpointCleaning", {
        schedule: Schedule.expression("cron(10,40 * ? * * *)"),
    }); // twice each hr at 10 and 40 mins past
    rule.addTarget(new targets.LambdaFunction(func));
}

function createLogCleaningLambda(
    stack: cdk.Stack,
    role: iam.IRole,
    maxLogGroupAge: Duration,
): void {
    const func = new lambda.Function(stack, "LogCleaningLambda", {
        description: "Clean logs created by tests",
        role: role,
        code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/python-functions")),
        handler: "clean_cw_logs.lambda_handler",
        runtime: lambda.Runtime.PYTHON_3_6,
        timeout: Duration.minutes(5),
        environment: {
            MAX_LOG_GROUP_AGE_IN_MINUTES: maxLogGroupAge.toMinutes().toString(),
        },
    });

    const rule = new events.Rule(stack, "ScheduledLogCleaning", {
        schedule: Schedule.expression("cron(20 * ? * * *)"), // every hour at 20th minute
    });
    rule.addTarget(new targets.LambdaFunction(func));
}

function createResourceCleaningRole(stack: cdk.Stack): iam.Role {
    const role = new iam.Role(stack, "ResourceCleaningRole", {
        assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
    });

    role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName("AmazonSageMakerFullAccess"));
    role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName("CloudWatchFullAccess"));

    return role;
}

export function createResourceCleaningLambdas(
    stack: cdk.Stack,
    maxEndpointAge: Duration,
    maxLogGroupAge: Duration,
): void {
    const role = createResourceCleaningRole(stack);
    createEndpointCleaningLambda(stack, role, maxEndpointAge);
    createLogCleaningLambda(stack, role, maxLogGroupAge);
}

export function gitHubOAuthSecret(): cdk.SecretValue {
    return cdk.SecretValue.secretsManager(Constants.gitHubOAuthSecretId);
}
