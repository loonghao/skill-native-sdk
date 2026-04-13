# docker/blender/Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
# Real Blender headless image for skill-native-sdk e2e tests.
#
# Installs Blender from the Ubuntu 22.04 package repository.  A thin Python
# wrapper (/usr/local/bin/blender) shadows the real binary so that callers
# use the same interface as before (script + JSON params).  The wrapper:
#   1. Invokes /usr/bin/blender --background --python <script> -- <params>
#   2. Strips Blender's startup noise from stdout
#   3. Prints only the final JSON result line
#
# Build:
#   docker build -t skill-native-sdk-blender -f docker/blender/Dockerfile .
#
# Run a single tool:
#   docker run --rm skill-native-sdk-blender \
#     /skills/examples/blender-render/scripts/set_render_output.py \
#     '{"output_path":"/tmp/render/","file_format":"PNG"}'
# ─────────────────────────────────────────────────────────────────────────────

FROM ubuntu:22.04

LABEL maintainer="skill-native-sdk" \
      description="Real Blender headless (ubuntu:22.04) for DCC e2e tests"

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        blender \
        python3 \
    && rm -rf /var/lib/apt/lists/*

# Install wrapper: captures real Blender output and extracts only the JSON line.
# /usr/local/bin/blender (this wrapper) shadows /usr/bin/blender in PATH.
# The wrapper explicitly calls /usr/bin/blender to avoid infinite recursion.
COPY docker/blender/blender_runner.py /usr/local/bin/blender
RUN chmod +x /usr/local/bin/blender

# Copy skill scripts
COPY skills/ /skills/

# Smoke-test: real bpy must be importable and set_render_output must succeed
RUN blender /skills/examples/blender-render/scripts/set_render_output.py \
    '{"output_path":"/tmp/render/","file_format":"PNG"}' | python3 -c \
    "import sys,json; d=json.load(sys.stdin); assert d['success'], d; \
     assert '[sim]' not in d['message'], 'still in sim mode: ' + d['message']"

ENTRYPOINT ["blender"]
