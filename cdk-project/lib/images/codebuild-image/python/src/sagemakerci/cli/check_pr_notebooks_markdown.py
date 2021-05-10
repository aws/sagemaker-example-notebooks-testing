#!/usr/bin/env python3
import argparse
import json
import os
import sys

import language_tool_python

from sagemakerci.cli.run_pr_notebooks import notebook_filenames


vocab = {
    "Alexa",
    "Amazon",
    "AWS",
    "Amplify",
    "API",
    "Gateway",
    "App" "AppFlow",
    "AppStream",
    "AppSync",
    "ARN",
    "Athena",
    "A2I",
    "Aurora",
    "Backint",
    "Blockchain",
    "Blox",
    "BYOC",
    "ACM",
    "Chatbot",
    "VPN",
    "CDK",
    "Cloud9",
    "CloudFormation",
    "CloudFront",
    "CloudHSM",
    "CloudSearch",
    "CloudShell",
    "CloudTrail",
    "CloudWatch",
    "CodeArtifact",
    "CodeBuild",
    "CodeCommit",
    "CodeDeploy",
    "CodeGuru",
    "CodePipeline",
    "CodeStar",
    "Cognito",
    "CLI",
    "Comprehend",
    "Config",
    "Corretto",
    "DataSync",
    "DLAMI",
    "DLAMIs",
    "DLC",
    "DLCs",
    "DeepComposer",
    "DeepLens",
    "DeepRacer",
    "DevPay",
    "DMS",
    "DocumentDB",
    "DynamoDB",
    "EC2",
    "EBS",
    "ECR",
    "ECS",
    "Kubernetes",
    "EKS",
    "EFS",
    "Transcoder",
    "Elasticache",
    "ES",
    "EMR",
    "EventBridge",
    "Fargate",
    "FreeRTOS",
    "FSx",
    "Lustre",
    "GameLift",
    "Grafana",
    "Greengrass",
    "GovCloud",
    "GuardDuty",
    "HealthLake",
    "Honeycode",
    "IAM",
    "Import/Export",
    "IoT",
    "LoRaWAN",
    "SiteWise",
    "1-Click",
    "IVS",
    "Kendra",
    "KMS",
    "Keyspaces",
    "Kinesis",
    "Lambda",
    "Lex",
    "Lightsail",
    "Lookout",
    "Lumberyard",
    "Macie",
    "Apache",
    "Kafka",
    "MSK",
    "Airflow",
    "vCenter",
    "MTurk",
    "MediaConnect",
    "MediaConvert",
    "MediaLive",
    "MediaPackage",
    "MediaStore",
    "MediaTailor",
    "Monitron",
    "MQ",
    "OpsWorks",
    "ParallelCluster",
    "Polly",
    "PCA",
    "AMP",
    "QLDB",
    "QuickSight",
    "Redshift",
    "Rekognition",
    "RDS",
    "RAM",
    "RoboMaker",
    "SageMaker",
    "JumpStart",
    "Serverless",
    "SAM",
    "SES",
    "SNS",
    "SQS",
    "S3",
    "SWF",
    "SimpleDB",
    "SSO",
    "Sumerian",
    "Android",
    "C++",
    "iOS",
    "JavaScript",
    ".NET",
    "Boto3",
    "boto3",
    "Python",
    "Textract",
    "Timestream",
    "PowerShell",
    "VPC",
    "WAF",
    "Well-Architected",
    "WorkDocs",
    "WorkLink",
    "WorkMail",
    "WorkSpaces",
    "WAM",
    "X-Ray",
    "Roboschool",
    "utils",
    "Horovod",
    "MXNet",
    "PyTorch",
    "TensorFlow",
    "Keras",
    "Gluon",
    "ONNX",
    "RNN",
    "CNN",
    "LSTM",
    "XGBoost",
    "NumPy",
    "SciPy",
    "hyperparameter",
    "hyperparameters",
    "Hyperparameter",
    "Hyperparameters",
    "csv",
    "CSV",
    "uri",
    "URI",
    "json",
    "JSON",
    "serializers",
    "deserializers",
}

rules_to_ignore = {
    "PUNCTUATION_PARAGRAPH_END",
    "WORD_CONTAINS_UNDERSCORE",
    "DASH_RULE",
    "EN_QUOTES",
    "WRONG_APOSTROPHE",
}


def parse_args(args):
    parser = argparse.ArgumentParser(os.path.basename(__file__))
    parser.set_defaults(func=lambda x: parser.print_usage())
    parser.add_argument("--pr", help="Pull request number", type=int, required=True)

    parsed = parser.parse_args(args)
    if not parsed.pr:
        parser.error("--pr required")

    return parsed


def markdown_cells(notebook):
    with open(notebook) as notebook_file:
        cells = json.load(notebook_file)["cells"]
    md_cells = []
    for cell in cells:
        if cell["cell_type"] == "markdown":
            md_cells.append(cell["source"])
    return md_cells


def check_grammar(notebook):
    tool = language_tool_python.LanguageTool("en-US")

    report = []

    cells = markdown_cells(notebook)
    for cell in cells:
        for line in cell:
            stripped_line = line.rstrip().strip(" #*")
            matches = tool.check(stripped_line)
            report.extend(matches)

    is_correctly_spelled = lambda rule: rule.ruleIssueType == "misspelling" and (
        rule.matchedText in vocab or "-" in rule.matchedText
    )
    report = [rule for rule in report if not is_correctly_spelled(rule)]

    is_ignored_rule = lambda rule: rule.ruleId in rules_to_ignore
    report = [rule for rule in report if not is_ignored_rule(rule)]

    return report


def main():
    args = parse_args(sys.argv[1:])

    failures = {}

    for notebook in notebook_filenames(args.pr):
        report = check_grammar(notebook)
        if report:
            failures[notebook] = report
            basename = os.path.basename(notebook)
            print("\n" * 2)
            print(f"* {basename} " + "*" * (97 - len(basename)))
            print()
            print("\n\n".join([str(match) for match in report]))

    print("\n" * 2)
    print("-" * 100)
    if len(failures) > 0:
        raise Exception(
            "One or more notebooks did not pass the spelling and grammar check. Please see above for error messages. "
            "To fix the text in your notebook, use language_tool_python.utils.correct: https://pypi.org/project/language-tool-python/"
        )


if __name__ == "__main__":
    main()
