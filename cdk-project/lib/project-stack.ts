import cdk = require("@aws-cdk/core");
import codebuild = require("@aws-cdk/aws-codebuild");
import cp = require("@aws-cdk/aws-codepipeline");
import cpa = require("@aws-cdk/aws-codepipeline-actions");
import cw = require("@aws-cdk/aws-cloudwatch");
import events = require("@aws-cdk/aws-events");
import targets = require("@aws-cdk/aws-events-targets");
import iam = require("@aws-cdk/aws-iam");
import lambda = require("@aws-cdk/aws-lambda");
import s3 = require("@aws-cdk/aws-s3");
import sam = require("@aws-cdk/aws-sam");
import stepfunctions = require("@aws-cdk/aws-stepfunctions");
import changeCase = require("change-case");

import common = require("./common");
import path = require("path");
import { BuildSystemStack } from "./build-system-stack";
import { Duration } from "@aws-cdk/core";
import { Schedule } from "@aws-cdk/aws-events";
import { Environments } from "./common";
import { ManagedPolicy } from "@aws-cdk/aws-iam";

interface ProjectStackProps extends cdk.StackProps {
    project: common.Project;
    pullRequestBuildRole: iam.Role;
    releaseBuildRole: iam.Role;
    artifactBucket: s3.Bucket;
}

export class ProjectStack extends cdk.Stack {
    private readonly buildImage: codebuild.IBuildImage;
    private readonly gitHubToken: cdk.SecretValue;
    private readonly pullRequestBuildRole: iam.IRole;
    private readonly releaseBuildRole: iam.IRole;
    private readonly artifactBucket: s3.IBucket;

    static createProps(
        project: common.Project,
        buildSystemStack: BuildSystemStack,
        env?: cdk.Environment,
    ): ProjectStackProps {
        return {
            project: project,
            pullRequestBuildRole: buildSystemStack.pullRequestBuildRole,
            releaseBuildRole: buildSystemStack.releaseBuildRole,
            artifactBucket: buildSystemStack.artifactBucket,
            env: env,
            terminationProtection: true,
        };
    }

    static stackId(prefix: string, props: ProjectStackProps): string {
        const pascal = changeCase.pascal(props.project.name);
        const base = `${pascal}Stack`;
        return common.stackId(prefix, base, props);
    }

    constructor(scope: cdk.App, prefix: string, props: ProjectStackProps) {
        super(scope, ProjectStack.stackId(prefix, props), props);

        this.pullRequestBuildRole = iam.Role.fromRoleArn(
            this,
            "PullRequestBuildRole",
            props.pullRequestBuildRole.roleArn,
        );
        this.releaseBuildRole = iam.Role.fromRoleArn(
            this,
            "ReleaseBuildRole",
            props.releaseBuildRole.roleArn,
        );
        this.artifactBucket = s3.Bucket.fromBucketArn(
            this,
            "ArtifactBucket",
            props.artifactBucket.bucketArn,
        );
        this.buildImage = common.importBuildImage(this, Environments.prod());
        this.gitHubToken = common.gitHubOAuthSecret();
        this.addProject(props.project);
    }

    createAlarms(p: common.Project): { deployAlarm: cw.Alarm; releaseAlarm: cw.Alarm } {
        const releaseBuildMetric = new cw.Metric({
            metricName: "FailedBuilds",
            namespace: "AWS/CodeBuild",
            unit: cw.Unit.COUNT,
            dimensions: {
                ProjectName: `${p.name}-release`,
            },
        });

        const deployBuildMetric = new cw.Metric({
            metricName: "FailedBuilds",
            namespace: "AWS/CodeBuild",
            unit: cw.Unit.COUNT,
            dimensions: {
                ProjectName: `${p.name}-deploy`,
            },
        });

        const releaseAlarm = new cw.Alarm(this, `${p.name}-release-alarm`, {
            alarmName: `${p.name}-release-alarm`,
            metric: releaseBuildMetric,
            threshold: 1.0,
            evaluationPeriods: 1,
            actionsEnabled: true,
            period: Duration.seconds(60),
            datapointsToAlarm: 1,
            alarmDescription:
                "Indicate status of CodeBuild project: SucceededBuilds or FailedBuilds",
            comparisonOperator: cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            statistic: "sum",
            treatMissingData: cw.TreatMissingData.IGNORE,
        });

        const deployAlarm = new cw.Alarm(this, `${p.name}-deploy-alarm`, {
            alarmName: `${p.name}-deploy-alarm`,
            metric: deployBuildMetric,
            threshold: 1.0,
            evaluationPeriods: 1,
            actionsEnabled: true,
            period: Duration.seconds(60),
            datapointsToAlarm: 1,
            alarmDescription:
                "Indicate status of CodeBuild project: SucceededBuilds or FailedBuilds",
            comparisonOperator: cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            statistic: "sum",
            treatMissingData: cw.TreatMissingData.IGNORE,
        });

        return {
            releaseAlarm: releaseAlarm,
            deployAlarm: deployAlarm,
        };
    }

    addProject(p: common.Project): void {
        if (p.enablePullRequestBuild) {
            this.addPullRequestBuild(p);
        }

        if (p.enableReleaseBuild) {
            this.addReleasePipeline(p);
            this.createAlarms(p);
        }
    }

    addPullRequestBuild(p: common.Project): void {
        const defaultProjectBuildImage = this.buildImage;

        const source = codebuild.Source.gitHub({
            owner: p.owner || common.Constants.defaultGitHubOwner,
            repo: p.repo,
            reportBuildStatus: true,
            webhook: false,
        });
        const project = new codebuild.Project(this, "PrProject", {
            projectName: `${p.name}-pr`,
            role: this.pullRequestBuildRole,
            environment: {
                buildImage: p.customImage || defaultProjectBuildImage,
                privileged: true,
                computeType: p.computeType,
            },
            timeout: p.timeout,
            buildSpec: p.pullRequestBuildSpec,
            source: source,
        });

        const buildSource = codebuild.Source.gitHub({
            owner: p.owner || common.Constants.defaultGitHubOwner,
            repo: p.repo,
            reportBuildStatus: true,
            webhook: true,
        });

        for (const build of p.additionalBuildProjects) {
            const defaultAdditionalBuildImage = this.buildImage;

            const buildProject = new codebuild.Project(this, build.name, {
                projectName: build.name,
                role: this.pullRequestBuildRole,
                environment: {
                    buildImage: build.customImage || defaultAdditionalBuildImage,
                    privileged: true,
                    computeType: build.computeType,
                },
                timeout: build.timeout,
                buildSpec: build.pullRequestBuildSpec,
                source: buildSource,
            });

            this.addGitHubCodeBuildLogsSAR(buildProject, `${build.name}-build-logs-sar`);
        }

        common.enableCrossAccountImagePull(project);
        common.enableSageMakerOperation(project);
        this.addGitHubCodeBuildLogsSAR(project);
    }

    addGitHubCodeBuildLogsSAR(project: codebuild.Project, name?: string): void {
        const props: sam.CfnApplicationProps = {
            location: {
                applicationId:
                    "arn:aws:serverlessrepo:us-east-1:277187709615:applications/github-codebuild-logs",
                semanticVersion: "1.4.0",
            },
            parameters: {
                CodeBuildProjectName: project.projectName,
                GitHubOAuthToken: this.gitHubToken.toString(),
            },
        };
        name = name || "GitHubCodeBuildLogsSAR";
        new sam.CfnApplication(this, name, props);
    }

    addReleasePipeline(p: common.Project): void {
        const pipelineName = `${p.name}`;

        const pipeline = new cp.Pipeline(this, "ReleasePipeline", {
            pipelineName: pipelineName,
            artifactBucket: this.artifactBucket,
        });

        // cdk doesn't let us specify role for codepipeline (yet)
        // so we let codepipeline assume our releaseBuildRole
        const policy = new iam.PolicyStatement();
        policy.addResources(this.releaseBuildRole.roleArn);
        policy.addActions("sts:AssumeRole");

        pipeline.addToRolePolicy(policy);

        const buildProject = this.createReleaseBuildProject(p, pipelineName);
        const deployProject = this.createReleaseDeployProject(p, pipelineName);

        const sourceStage = pipeline.addStage({ stageName: "Source" });
        const projectSource = new cpa.GitHubSourceAction({
            actionName: "DownloadSource",
            owner: p.owner,
            repo: p.repo,
            branch: p.branch, // default: 'master'
            oauthToken: this.gitHubToken,
            trigger: cpa.GitHubTrigger.NONE,
            output: new cp.Artifact("SOURCE"),
        });
        sourceStage.addAction(projectSource);

        // important:
        //   release builds run on a schedule, not on source changes
        //   we need to disable the source polling we configured
        //   when we created the GitHubSourceAction
        const cfnPipeline = pipeline.node.findChild("Resource") as cp.CfnPipeline;
        cfnPipeline.addPropertyOverride(
            "Stages.0.Actions.0.Configuration.PollForSourceChanges",
            false,
        ); // project source

        const sourceOutputArtifact = new cp.Artifact("SOURCE");

        // optionally, add source
        let source = undefined;
        if (p.addSourceToReleasePipeline) {
            source = new cpa.GitHubSourceAction({
                actionName: "Source",
                owner: common.Constants.defaultGitHubOwner,
                repo: common.Constants.exampleNotebooksRepo,
                oauthToken: this.gitHubToken,
                trigger: cpa.GitHubTrigger.NONE,
                output: sourceOutputArtifact,
            });
            sourceStage.addAction(source);

            // prevent source polling
            cfnPipeline.addPropertyOverride(
                "Stages.0.Actions.1.Configuration.PollForSourceChanges",
                false,
            ); // source
        }

        const buildOutputArtifact = new cp.Artifact("ARTIFACT_1");

        const buildStage = pipeline.addStage({ stageName: "Run" });
        const buildAction = new cpa.CodeBuildAction({
            actionName: "RunNotebooks",
            project: buildProject,
            input: sourceOutputArtifact,
            outputs: [buildOutputArtifact],
        });
        buildStage.addAction(buildAction);

        const waitStage = pipeline.addStage({ stageName: "Wait" });

        waitStage.addAction(
            new cpa.StepFunctionInvokeAction({
                actionName: "WaitForProcessingJobs",
                stateMachine: new stepfunctions.StateMachine(this, "WaitStateMachine", {
                    definition: new stepfunctions.Wait(this, "WaitForProcessingJobs", {
                        time: stepfunctions.WaitTime.duration(cdk.Duration.hours(2)),
                    }),
                }),
            }),
        );

        const deployStage = pipeline.addStage({ stageName: "Report" });
        const additionalInputArtifacts =
            source === undefined
                ? [buildOutputArtifact]
                : [sourceOutputArtifact, buildOutputArtifact];

        deployStage.addAction(
            new cpa.CodeBuildAction({
                actionName: "GenerateReport",
                project: deployProject,
                input: sourceOutputArtifact,
                extraInputs: additionalInputArtifacts,
            }),
        );

        const queryStage = pipeline.addStage({ stageName: "Query" });
        const queryAction = new cpa.LambdaInvokeAction({
            actionName: "StartAthenaQuery",
            lambda: this.createAthenaQueryLambda(),
        });
        queryStage.addAction(queryAction);

        if (p.enableAutomaticRelease) {
            const rule = new events.Rule(this, "ScheduledEvent", {
                schedule: Schedule.expression(p.releasePipelineScheduleExpression),
            });
            rule.addTarget(new targets.CodePipeline(pipeline));
        }
    }

    createAthenaQueryLambda(): lambda.Function {
        const role = new iam.Role(this, "AthenaQueryRole", {
            assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
        });

        role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName("AmazonAthenaFullAccess"));
        role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName("CloudWatchFullAccess"));

        return new lambda.Function(this, "AthenaQueryLambda", {
            description: "Start an Athena query on the full repo scan report",
            role: role,
            code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/python-functions")),
            handler: "athena_query.lambda_handler",
            runtime: lambda.Runtime.PYTHON_3_6,
            timeout: Duration.minutes(5),
        });
    }

    createReleaseBuildProject(p: common.Project, pipelineName: string): codebuild.PipelineProject {
        const project = new codebuild.PipelineProject(this, "ReleaseProject", {
            projectName: `${pipelineName}-release`,
            role: this.releaseBuildRole,
            timeout: p.timeout,
            buildSpec: p.releaseBuildSpec,
            environment: {
                buildImage: this.buildImage,
                privileged: true,
                computeType: p.computeType,
                environmentVariables: {
                    RELEASE_BUILD: { value: "1" },
                },
            },
        });

        common.enableCrossAccountImagePull(project);
        common.enableSageMakerOperation(project);
        return project;
    }

    createDeployProjectProperties(p: common.Project) {
        return {
            buildSpec: p.deployBuildSpec,
            timeout: p.timeout,
            environment: {
                buildImage: this.buildImage,
                privileged: true,
            },
        };
    }

    createReleaseDeployProject(p: common.Project, pipelineName: string): codebuild.PipelineProject {
        const sharedProps = {
            projectName: `${pipelineName}-deploy`,
            role: this.releaseBuildRole,
        };

        const projectProps = this.createDeployProjectProperties(p);

        const props = Object.assign(sharedProps, projectProps);
        const project = new codebuild.PipelineProject(this, "DeployProject", props);
        common.enableCrossAccountImagePull(project);
        common.enableSageMakerOperation(project);
        return project;
    }
}
