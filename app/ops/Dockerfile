# The on-call "jump box": every agent's shell commands run in here, never on the host.
FROM docker:29-cli
RUN apk add --no-cache bash curl jq coreutils grep sed procps postgresql17-client redis
WORKDIR /
CMD ["sleep", "infinity"]
