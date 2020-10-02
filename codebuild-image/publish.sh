#!/bin/bash

function get_default_region() {
    if [ -n "$AWS_DEFAULT_REGION" ]; then
        echo "$AWS_DEFAULT_REGION"
    else
        aws configure get region
    fi
}

function get_aws_account() {
    aws --endpoint-url 'https://sts.us-west-2.amazonaws.com' --region 'us-west-2' sts get-caller-identity --query 'Account' --output text
}

aws_region=$(get_default_region)
aws_account=$(get_aws_account)
ecr_password=$(aws ecr get-login-password --region $aws_region)
docker login --username AWS --password $ecr_password $aws_account.dkr.ecr.$aws_region.amazonaws.com

docker tag sagemaker-codebuild:cpu $aws_account.dkr.ecr.$aws_region.amazonaws.com/sagemaker-codebuild:cpu
docker push $aws_account.dkr.ecr.$aws_region.amazonaws.com/sagemaker-codebuild:cpu

docker logout https://$aws_account.dkr.ecr.$aws_region.amazonaws.com
