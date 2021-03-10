#!/bin/bash

pushd python >/dev/null
python3 setup.py sdist
popd >/dev/null

docker build -t sagemaker-codebuild:cpu -f Dockerfile .
