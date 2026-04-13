---
name: blender-render
domain: blender
version: "1.0.0"
description: "Headless Blender rendering — configure output and render scenes"
tags: [blender, render, dcc, 3d]

tools:
  - name: set_render_output
    description: "Configure render output path and file format"
    source_file: scripts/set_render_output.py
    read_only: false
    destructive: false
    idempotent: true
    cost: low
    latency: fast
    input:
      output_path:
        type: string
        required: true
        description: "Output file path (e.g. /tmp/render/frame_)"
      file_format:
        type: string
        required: false
        default: "PNG"
        description: "Image format: PNG, JPEG, OPEN_EXR"
      resolution_x:
        type: number
        required: false
        default: 1920
      resolution_y:
        type: number
        required: false
        default: 1080
    output:
      filepath: string
      format: string
    on_success:
      suggest: [render_scene]
    on_error:
      suggest: []

  - name: render_scene
    description: "Render the current scene to the configured output path"
    source_file: scripts/render_scene.py
    read_only: false
    destructive: false
    idempotent: false
    cost: high
    latency: slow
    input:
      write_still:
        type: boolean
        required: false
        default: true
        description: "Write a still image (vs. animation frame)"
      animation:
        type: boolean
        required: false
        default: false
        description: "Render full animation"
    output:
      status: string
      filepath: string
    on_success:
      suggest: []
    on_error:
      suggest: []

runtime:
  # type: subprocess  → skn spawns a child process using `interpreter`
  # For real Blender: interpreter: blender  (needs BlenderBridge for --background --python flags)
  # For tests:       interpreter set dynamically to blender_mock.py wrapper
  type: subprocess
  interpreter: blender
  entry: skill_entry

permissions:
  network: false
  filesystem: write
  external_api: false
---
