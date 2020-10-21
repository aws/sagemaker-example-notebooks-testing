#!/usr/bin/env node
import cdk = require("@aws-cdk/core");
import common = require("../lib/common");
import { BuildSystemStack } from "../lib/build-system-stack";
import { ProjectStack } from "../lib/project-stack";
import { projects } from "../lib/projects";

function createBuildStacks(
    app: cdk.App,
    prefix: string,
    env?: cdk.Environment,
    projectNames?: string[],
): void {
    // one BuildSystemStack for all projects
    const buildSystemStack = new BuildSystemStack(app, prefix, {
        env: env,
        terminationProtection: true,
    });

    // one ProjectStack for each project
    for (const p of projects) {
        // If projectNames is given only build the projects in the list. Otherwise all projects defined in project.ts will be built.
        if (projectNames === undefined || projectNames.indexOf(p.name) !== -1) {
            const props = ProjectStack.createProps(p, buildSystemStack, env);
            new ProjectStack(app, prefix, props);
        }
    }
}

const app = new cdk.App();
createBuildStacks(app, "Sandbox", common.Environments.sandbox());
createBuildStacks(app, "Prod", common.Environments.prod());

app.synth();
