# Custom CodeBuild Image

This docker image is used as a custom build image in SageMaker Frameworks' CodeBuild projects.

## Key features

- ubuntu:18.04 base
- python 2.7, python 3.6, python 3.7, python 3.8
- docker 18.09.1
- docker build support (when run with --privileged)

## Useful commands

```
# build the image (as sagemaker-codebuild:latest)
./build.sh

# publish to ECR (in current aws account and region)
./publish.sh
```

## In-container utilities

The container includes utilities that can be used from buildspecs.

- `start-dockerd.sh` Launches dockerd. Docker build projects should call this during `pre_build` phase.
