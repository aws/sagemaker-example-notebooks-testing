import codebuild = require("@aws-cdk/aws-codebuild");

import { Constants, Project } from "./common";
import { Duration } from "@aws-cdk/core";

export const projects: Project[] = [
    new Project({
        repo: Constants.exampleNotebooksRepo,
        computeType: codebuild.ComputeType.LARGE,
        timeout: Duration.minutes(480),
        enableReleaseBuild: false,
        additionalBuildProjects: [
            // new Build({
            //     name: "sagemaker-examples-notebook-instance",
            //     pullRequestBuildSpec: buildspecs.createNotebookInstanceBuildSpec(),
            //     computeType: codebuild.ComputeType.LARGE,
            // }),
            // new Build({
            //     name: "sagemaker-examples-best-practices",
            //     pullRequestBuildSpec: buildspecs.createBestPracticesBuildSpec(),
            //     computeType: codebuild.ComputeType.LARGE,
            // }),
        ],
    }),

    new Project({
        repo: "amazon-sagemaker-examples-staging",
        computeType: codebuild.ComputeType.LARGE,
        timeout: Duration.minutes(480),
        enableReleaseBuild: false,
        additionalBuildProjects: [
            // new Build({
            //     name: "sagemaker-examples-notebook-instance",
            //     pullRequestBuildSpec: buildspecs.createNotebookInstanceBuildSpec(),
            //     computeType: codebuild.ComputeType.LARGE,
            // }),
            // new Build({
            //     name: "sagemaker-examples-best-practices",
            //     pullRequestBuildSpec: buildspecs.createBestPracticesBuildSpec(),
            //     computeType: codebuild.ComputeType.LARGE,
            // }),
        ],
    }),
];
