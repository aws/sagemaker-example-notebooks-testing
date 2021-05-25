import boto3
from notebooks import parse


def get_latest_image_digest(registry, repository):
    """Get the latest Docker image digest for a given registry ID and ECR repository.

    Args:
        registry (str): The account ID that contains the ECR repository with the relevant image.
        repository (str): The name of the ECR repository for the image.

    Returns:
        str: The latest image digest.

    """
    client = boto3.client("ecr")
    response = client.describe_images(
        registryId=registry,
        repositoryName=repository,
        maxResults=1000,
    )
    images = response["imageDetails"]
    return sorted(images, key=lambda image: image["imagePushedAt"], reverse=True)[0]["imageDigest"]


CI_REGISTRY_ID = "521695447989"
LL_REGISTRY_ID = "236514542706"

BASE_PYTHON_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/base-python@{get_latest_image_digest(CI_REGISTRY_ID, 'base-python')}"
DATA_SCIENCE_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/data-science@{get_latest_image_digest(CI_REGISTRY_ID, 'data-science')}"
MXNET_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/mxnet@{get_latest_image_digest(CI_REGISTRY_ID, 'mxnet')}"
PYTORCH_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/pytorch@{get_latest_image_digest(CI_REGISTRY_ID, 'pytorch')}"
TENSORFLOW_1_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/tensorflow-1@{get_latest_image_digest(CI_REGISTRY_ID, 'tensorflow-1')}"
TENSORFLOW_2_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/tensorflow-2@{get_latest_image_digest(CI_REGISTRY_ID, 'tensorflow-2')}"
SPARK_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/spark@{get_latest_image_digest(CI_REGISTRY_ID, 'spark')}"
R_IMAGE = f"{CI_REGISTRY_ID}.dkr.ecr.us-west-2.amazonaws.com/r-image@{get_latest_image_digest(CI_REGISTRY_ID, 'r-image')}"


def kernel_type_for(notebook):
    """Classify the general kernel type for a given notebook using the kernel information in the metadata.

    Args:
        notebook (Path): The path to the notebook for which to determine the kernel type.

    Returns:
        str: The kernel type (eg. "MXNet", "PyTorch", "TensorFlow 1", "TensorFlow 2", "Spark", or "Data Science")

    """
    kernel_name = parse.kernel_for(notebook)

    if kernel_name:
        if any(
            name in kernel_name
            for name in (
                "MXNet",
                "mxnet",
                "conda_mxnet_latest_p37",
                "conda_mxnet_p27",
                "conda_mxnet_p36",
            )
        ):
            return "MXNet"
        elif any(
            name in kernel_name
            for name in (
                "PyTorch",
                "pytorch",
                "conda_pytorch_latest_p36",
                "conda_pytorch_p27",
                "conda_pytorch_p36",
            )
        ):
            return "PyTorch"
        elif any(
            name in kernel_name
            for name in (
                "TensorFlow 1",
                "conda_tensorflow_p27",
                "conda_tensorflow_p36",
                "tensorflow_p36",
            )
        ):
            return "TensorFlow 1"
        elif any(
            name in kernel_name
            for name in ("TensorFlow 2", "conda_tensorflow2_p36", "tensorflow2_p36")
        ):
            return "TensorFlow 2"
        elif any(name in kernel_name for name in ("SparkMagic", "PySpark", "pysparkkernel")):
            return "Spark"
        elif kernel_name == "R":
            return "R"

    return "Data Science"


def kernel_image_for(notebook):
    """Get the ECR URI for the kernel image to be used to run a given notebook.

    Args:
        notebook (Path): The path to the notebook for which to select the kernel image URI.

    Returns:
        str: The ECR image URI for the kernel to be used to run the notebook.

    """
    kernel_type = kernel_type_for(notebook)

    if kernel_type == "MXNet":
        return MXNET_IMAGE
    elif kernel_type == "PyTorch":
        return PYTORCH_IMAGE
    elif kernel_type == "TensorFlow 1":
        return TENSORFLOW_1_IMAGE
    elif kernel_type == "TensorFlow 2":
        return TENSORFLOW_2_IMAGE
    elif kernel_type == "Spark":
        return SPARK_IMAGE
    elif kernel_type == "R":
        return R_IMAGE

    return DATA_SCIENCE_IMAGE
