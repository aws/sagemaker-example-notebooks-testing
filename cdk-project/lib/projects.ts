import codebuild = require("@aws-cdk/aws-codebuild");

import { Build, Constants, Project } from "./common";
import { Duration } from "@aws-cdk/core";

export const projects: Project[] = [
    new Project({
        repo: Constants.exampleNotebooksRepo,
        computeType: codebuild.ComputeType.LARGE,
        timeout: Duration.minutes(150),
        enableReleaseBuild: false,
        additionalBuildProjects: [
            new Build({
                name: "sagemaker-examples-studio",
                pullRequestBuildSpec: codebuild.BuildSpec.fromSourceFilename(
                    "buildspec-studio.yml",
                ),
                computeType: codebuild.ComputeType.X2_LARGE,
            }),
            new Build({
                name: "sagemaker-examples-best-practices",
                pullRequestBuildSpec: codebuild.BuildSpec.fromSourceFilename(
                    "buildspec-best-practices.yml",
                ),
                computeType: codebuild.ComputeType.LARGE,
            }),
        ],
    }),

    new Project({
        repo: "amazon-sagemaker-examples-staging",
        computeType: codebuild.ComputeType.LARGE,
        timeout: Duration.minutes(150),
        enableReleaseBuild: false,
        additionalBuildProjects: [
            new Build({
                name: "sagemaker-examples-studio",
                pullRequestBuildSpec: codebuild.BuildSpec.fromSourceFilename(
                    "buildspec-studio.yml",
                ),
                computeType: codebuild.ComputeType.X2_LARGE,
            }),
            new Build({
                name: "sagemaker-examples-best-practices",
                pullRequestBuildSpec: codebuild.BuildSpec.fromSourceFilename(
                    "buildspec-best-practices.yml",
                ),
                computeType: codebuild.ComputeType.LARGE,
            }),
        ],
    }),
];
