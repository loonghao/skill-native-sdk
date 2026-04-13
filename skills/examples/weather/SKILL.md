---
name: weather
domain: utility
version: "1.0.0"
description: "Current conditions and multi-day forecast — simulation mode without API key"
tags: [weather, forecast, utility]

tools:
  - name: get_current
    description: "Get current weather conditions for a city"
    source_file: scripts/get_current.py
    read_only: true
    destructive: false
    idempotent: true
    cost: low
    latency: fast
    input:
      city:
        type: string
        required: true
        description: "City name (e.g. Tokyo, New York)"
      units:
        type: string
        required: false
        default: "metric"
        description: "Units: metric (°C) or imperial (°F)"
    output:
      temperature: number
      condition: string
      humidity: number
    on_success:
      suggest: [get_forecast]
    on_error:
      suggest: []

  - name: get_forecast
    description: "Get a multi-day weather forecast for a city"
    source_file: scripts/get_forecast.py
    read_only: true
    destructive: false
    idempotent: true
    cost: low
    latency: fast
    input:
      city:
        type: string
        required: true
        description: "City name"
      days:
        type: number
        required: false
        default: 3
        description: "Number of forecast days (1-7)"
      units:
        type: string
        required: false
        default: "metric"
    output:
      forecast: array
    on_success:
      suggest: []
    on_error:
      suggest: []

runtime:
  type: subprocess
  interpreter: python
  entry: skill_entry

permissions:
  network: false
  filesystem: none
  external_api: false
---
