---
name: maya-animation
domain: maya
version: "1.0.0"
description: "Keyframe animation tools for Autodesk Maya — set, query, and bake keyframes"
tags: [maya, animation, keyframe, dcc]

tools:
  - name: set_keyframe
    description: "Set a keyframe on an object at the given time"
    source_file: scripts/set_keyframe.py
    read_only: false
    destructive: false
    idempotent: false
    cost: low
    latency: fast
    input:
      object:
        type: string
        required: true
        description: "Maya object name (e.g. pCube1)"
      time:
        type: number
        required: true
        description: "Frame number to set keyframe at"
      attribute:
        type: string
        required: false
        default: "translateX"
        description: "Attribute to key (default: translateX)"
    output:
      result: string
    on_success:
      suggest: [get_keyframes, bake_simulation]
    on_error:
      suggest: [get_keyframes]

  - name: get_keyframes
    description: "Query all keyframe times on an object"
    source_file: scripts/get_keyframes.py
    read_only: true
    destructive: false
    idempotent: true
    cost: low
    latency: fast
    input:
      object:
        type: string
        required: true
        description: "Maya object name"
    output:
      keyframes: array
    on_success:
      suggest: []

  - name: bake_simulation
    description: "Bake simulation to keyframes on an object for a frame range"
    source_file: scripts/bake_simulation.py
    read_only: false
    destructive: false
    idempotent: false
    cost: high
    latency: slow
    input:
      object:
        type: string
        required: true
      start_frame:
        type: number
        required: true
      end_frame:
        type: number
        required: true
    output:
      baked_frames: number
    on_success:
      suggest: [get_keyframes]

runtime:
  # type: subprocess  → skn 會以獨立子進程呼叫 interpreter
  # 有 Maya 時改為: interpreter: mayapy
  # 或者完整路徑: interpreter: "C:/Program Files/Autodesk/Maya2025/bin/mayapy.exe"
  type: subprocess
  interpreter: python
  entry: skill_entry

permissions:
  network: false
  filesystem: none
  external_api: false
---
