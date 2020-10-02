import cdk = require("@aws-cdk/core");
import ecr = require("@aws-cdk/aws-ecr");
import iam = require("@aws-cdk/aws-iam");
import s3 = require("@aws-cdk/aws-s3");
import lambda = require("@aws-cdk/aws-lambda");
import apig = require("@aws-cdk/aws-apigateway");

import path = require("path");
import common = require("./common");
import { Duration } from "@aws-cdk/core";
import { ManagedPolicy } from "@aws-cdk/aws-iam";

type BuildSystemStackProps = cdk.StackProps;

export class BuildSystemStack extends cdk.Stack {
    readonly pullRequestBuildRole: iam.Role;
    readonly releaseBuildRole: iam.Role;
    readonly gitHubWebhookLambda: lambda.Function;
    readonly startPipelineLambda: lambda.Function;
    readonly ec2TestRole: iam.Role;
    readonly pullRequestBuildEcrRepo: ecr.Repository;
    readonly artifactBucket: s3.Bucket;

    constructor(scope: cdk.App, prefix: string, props: BuildSystemStackProps) {
        super(scope, common.stackId(prefix, "BuildSystemStack", props), props);

        this.artifactBucket = this.createArtifactBucket();
        this.releaseBuildRole = this.createReleaseBuildRole();
        this.pullRequestBuildRole = this.createPullRequestBuildRole();
        this.ec2TestRole = this.createEc2TestRole();
        this.pullRequestBuildEcrRepo = this.createPullRequestBuildEcrRepo();
        this.gitHubWebhookLambda = this.createGitHubWebhookLambda();
        this.startPipelineLambda = this.createStartPipelineLambda();

        // Keep endpoints for 45 mins, logs for 3 days
        common.createResourceCleaningLambdas(this, Duration.minutes(45), Duration.days(3));
    }

    createArtifactBucket(): s3.Bucket {
        return new s3.Bucket(this, "ArtifactBucket", {
            versioned: true,
        });
    }

    createGitHubWebhookLambda(): lambda.Function {
        const func = new lambda.Function(this, "GitHubWebhookLambda", {
            description: "Receives pull request webhooks from GitHub and starts a CodeBuild job",
            code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/python-functions")),
            handler: "github_webhook_receiver.handler",
            runtime: lambda.Runtime.PYTHON_3_6,
            timeout: Duration.minutes(5),
        });

        const policy = new iam.PolicyStatement();
        policy.addActions(
            "codebuild:StartBuild",
            "codebuild:StopBuild",
            "codebuild:BatchGetBuilds",
            "codebuild:ListBuildsForProject",
        );
        policy.addResources("*");

        func.addToRolePolicy(policy);

        new apig.LambdaRestApi(this, "GitHubWebhookApi", {
            handler: func,
        });

        return func;
    }

    createStartPipelineLambda(): lambda.Function {
        const func = new lambda.Function(this, "StartPipelineLambda", {
            description: "Receives Cloudwatch Scheduled Event and starts a CodePipeline pipeline",
            code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/python-functions")),
            handler: "start_pipeline.handler",
            runtime: lambda.Runtime.PYTHON_3_6,
            timeout: Duration.minutes(5),
        });

        func.addPermission("AllowCloudWatchInvocation", {
            principal: new iam.ServicePrincipal("events.amazonaws.com"),
        });

        const policy = new iam.PolicyStatement();
        policy.addActions("codepipeline:StartPipelineExecution", "secretsmanager:GetSecretValue");
        policy.addAllResources();

        func.addToRolePolicy(policy);

        return func;
    }

    createPullRequestBuildRole(): iam.Role {
        // important to limit privileges of this role,
        // because it is used to run tests
        // that include untrusted code

        const role = new iam.Role(this, "PullRequestBuildRole", {
            assumedBy: new iam.ServicePrincipal("codebuild.amazonaws.com"),
        });

        this.addPullRequestBuildPermissions(role);

        return role;
    }

    createEc2TestRole(): iam.Role {
        const role = new iam.Role(this, "Ec2TestRole", {
            assumedBy: new iam.ServicePrincipal("ec2.amazonaws.com"),
            roleName: "Ec2TestRole",
        });

        this.addPullRequestBuildPermissions(role);

        return role;
    }

    addPullRequestBuildPermissions(role: iam.Role): void {
        const policy = new iam.PolicyStatement();
        policy.addActions(
            "ec2:AssociateRouteTable",
            "ec2:AttachInternetGateway",
            "ec2:AuthorizeSecurityGroupIngress",
            "ec2:CreateInternetGateway",
            "ec2:CreateKeyPair",
            "ec2:CreateRoute",
            "ec2:CreateSubnet",
            "ec2:CreateVpc",
            "ec2:DescribeKeyPairs",
            "ec2:DescribeImages",
            "ec2:DescribeInstances",
            "ec2:DescribeVpcEndpointServices",
            "ec2:DescribeAvailabilityZones",
            "ec2:DeleteKeyPair",
            "ec2:DeleteNetworkInterface",
            "ec2:DeleteSubnet",
            "ec2:DescribeInstanceStatus",
            "ec2:DescribeKeyPairs",
            "ec2:DescribeRouteTables",
            "ec2:ModifyVpcAttribute",
            "ec2:RunInstances",
            "ec2:TerminateInstances",
            "ecr:GetAuthorizationToken",
            "ecr:BatchCheckLayerAvailability",
            "ecr:BatchGetImage",
            "ecr:GetDownloadUrlForLayer",
            "elasticfilesystem:CreateFileSystem",
            "elasticfilesystem:CreateMountTarget",
            "elasticfilesystem:DeleteFileSystem",
            "elasticfilesystem:DeleteMountTarget",
            "fsx:CreateFileSystem",
            "fsx:DeleteFileSystem",
            "iam:GetRole",
            "iam:GetInstanceProfile",
            "iam:CreateInstanceProfile",
            "iam:AddRoleToInstanceProfile",
            "kms:CreateKey",
            "kms:DescribeKey",
            "kms:CreateAlias",
            "kms:CreateGrant",
            "kms:GetKeyPolicy",
            "kms:PutKeyPolicy",
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:DeleteLogGroup",
            "logs:FilterLogEvents",
            "logs:PutLogEvents",
            "sts:GetCallerIdentity",
            "s3:CreateBucket",
            "s3:ListAllMyBuckets",
            "s3:ListBucket",
            "s3:ListBucketMultipartUploads",
            "s3:GetBucketLocation",
            "s3:GetObject",
            "s3:PutObject",
            "s3:PutObjectAcl",
            "kms:Encrypt",
            "kms:Decrypt",
            "kms:GenerateDataKey",
            "secretsmanager:GetSecretValue",
        );
        policy.addAllResources();
        role.addToPolicy(policy);

        const fsxPolicy = new iam.PolicyStatement();
        fsxPolicy.addActions("iam:CreateServiceLinkedRole");
        fsxPolicy.addResources(
            "arn:aws:iam::*:role/aws-service-role/fsx.amazonaws.com/AWSServiceRoleForAmazonFSx",
        );
        role.addToPolicy(fsxPolicy);

        const bucketArn = this.artifactBucket.bucketArn;
        const s3Policy = new iam.PolicyStatement();
        s3Policy.addActions("s3:ListBucket", "s3:GetObject", "s3:PutObject");
        s3Policy.addResources(bucketArn, `${bucketArn}/*`);
        role.addToPolicy(s3Policy);

        role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName("AmazonSageMakerFullAccess"));
        role.addManagedPolicy(
            ManagedPolicy.fromAwsManagedPolicyName("AmazonElasticMapReduceFullAccess"),
        );
        role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName("AWSCodeBuildReadOnlyAccess"));
    }

    createReleaseBuildRole(): iam.Role {
        const role = new iam.Role(this, "ReleaseBuildRole", {
            assumedBy: new iam.CompositePrincipal(
                new iam.ServicePrincipal("codepipeline.amazonaws.com"),
                new iam.ServicePrincipal("codebuild.amazonaws.com"),
            ),
        });

        this.addPullRequestBuildPermissions(role);
        this.addReleaseBuildPermissions(role);

        return role;
    }

    addReleaseBuildPermissions(role: iam.Role): void {
        const policy = new iam.PolicyStatement();
        policy.addActions(
            "ecr:CompleteLayerUpload",
            "ecr:DescribeImages",
            "ecr:InitiateLayerUpload",
            "ecr:PutImage",
            "ecr:UploadLayerPart",
            "codepipeline:GetPipeline",
            "sts:AssumeRole",
        );
        policy.addAllResources();

        role.addToPolicy(policy);
    }

    createPullRequestBuildEcrRepo(): ecr.Repository {
        const repo = new ecr.Repository(this, "sagemaker-test", {
            repositoryName: "sagemaker-test",
        });

        const policy = new iam.PolicyStatement();
        policy.addServicePrincipal("sagemaker.amazonaws.com");
        policy.addActions(
            "ecr:BatchCheckLayerAvailability",
            "ecr:BatchGetImage",
            "ecr:CompleteLayerUpload",
            "ecr:DescribeImages",
            "ecr:GetDownloadUrlForLayer",
            "ecr:InitiateLayerUpload",
            "ecr:ListImages",
            "ecr:PutImage",
            "ecr:UploadLayerPart",
        );

        repo.addToResourcePolicy(policy);

        return repo;
    }
}
