# docker/mayapy/Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
# Real mayapy image for skill-native-sdk e2e tests.
#
# Uses tahv/mayapy:2025 which bundles Autodesk Maya's Python interpreter with
# a valid headless-mode licence stub.  Skill scripts call
# maya.standalone.initialize() before importing maya.cmds, so they work
# without a full interactive Maya session.
#
# Build:
#   docker build -t skill-native-sdk-mayapy -f docker/mayapy/Dockerfile .
#
# Run a single tool:
#   docker run --rm skill-native-sdk-mayapy \
#     /skills/examples/maya-animation/scripts/set_keyframe.py \
#     '{"object":"pCube1","time":24}'
# ─────────────────────────────────────────────────────────────────────────────

FROM tahv/mayapy:2025

LABEL maintainer="skill-native-sdk" \
      description="Real mayapy (tahv/mayapy:2025) for DCC e2e tests"

WORKDIR /app

# Copy skill scripts into the image
COPY skills/ /skills/

# Smoke-test: maya.standalone.initialize() + cmds.setKeyframe must succeed
RUN mayapy /skills/examples/maya-animation/scripts/set_keyframe.py \
    '{"object":"smoketest","time":1}' | mayapy -c \
    "import sys,json; d=json.load(sys.stdin); assert d['success'], d; \
     assert '[sim]' not in d['message'], 'still in sim mode: ' + d['message']"

ENTRYPOINT ["mayapy"]
