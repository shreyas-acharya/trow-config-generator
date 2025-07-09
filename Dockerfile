ARG WORKDIR="/app"

FROM cgr.dev/chainguard/python:latest-dev AS builder
USER 0
ARG WORKDIR
WORKDIR ${WORKDIR}
COPY poetry.lock .
COPY pyproject.toml .
RUN pip3 install poetry && \
    poetry self add poetry-plugin-export && \
    poetry export --format requirements.txt --output requirements.txt --without-hashes && \
    pip3 install -r requirements.txt -t ./packages
RUN find . -regex '^.*\(__pycache__\|\.py[co]\)$' -delete

FROM cgr.dev/chainguard/python:latest
ARG WORKDIR
WORKDIR ${WORKDIR}
COPY --from=builder ${WORKDIR}/packages/ .
COPY registry_auth/ registry_auth/
COPY main.py .
ENTRYPOINT ["python3", "main.py"]

