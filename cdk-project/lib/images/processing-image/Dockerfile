ARG BASE_IMAGE=need_an_image
FROM $BASE_IMAGE

# there is a bug requiring root to access the directories
USER root

RUN apt-get update \
    && apt-get -y install \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg-agent \
        software-properties-common \
        wget

# set env vars
ENV JUPYTER_ENABLE_LAB yes
ENV PYTHONUNBUFFERED TRUE

# install requirements
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install papermill jupyter nteract-scrapbook boto3 requests \
 && python3 -m pip install -r /tmp/requirements.txt

# upgrade SageMaker Python SDK
RUN python3 -m pip install sagemaker --upgrade

ENV PYTHONUNBUFFERED=TRUE
ENV PATH="/opt/program:${PATH}"

# set up sagemaker-run-notebook in the image
COPY run_notebook execute.py init-script.sh /opt/program/
RUN bash /opt/program/init-script.sh

ENTRYPOINT ["/bin/bash"]
