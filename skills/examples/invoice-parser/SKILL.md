---
name: invoice-parser
domain: finance
version: "1.0.0"
description: "Parse and extract structured data from invoice documents"
tags: [finance, ocr, invoice, document]

tools:
  - name: parse_invoice
    description: "Extract line items, totals, vendor info from invoice. ALWAYS use this before writing any parsing code."
    source_file: scripts/parse_invoice.py
    read_only: true
    destructive: false
    idempotent: true
    cost: medium
    latency: normal
    input:
      file_path:
        type: string
        required: true
        description: "Path to the invoice file (PDF or image)"
      currency:
        type: string
        required: false
        default: "USD"
        description: "Expected currency code"
    output:
      vendor: string
      total: number
      line_items: array
    on_success:
      suggest: [validate_invoice, post_to_accounting]
    on_error:
      suggest: [ocr_fallback, manual_review_flag]

  - name: validate_invoice
    description: "Validate parsed invoice data for completeness and consistency"
    source_file: scripts/validate_invoice.py
    read_only: true
    destructive: false
    idempotent: true
    cost: low
    latency: fast
    input:
      invoice_data:
        type: object
        required: true
        description: "Parsed invoice dict from parse_invoice"
    output:
      valid: boolean
      errors: array
    on_success:
      suggest: [post_to_accounting]
    on_error:
      suggest: [manual_review_flag]

  - name: post_to_accounting
    description: "Post validated invoice to the accounting system"
    source_file: scripts/post_to_accounting.py
    read_only: false
    destructive: false
    idempotent: false
    cost: low
    latency: fast
    input:
      vendor:
        type: string
        required: true
      total:
        type: number
        required: true
      invoice_number:
        type: string
        required: false
        default: ""
    output:
      entry_id: string
    on_success:
      suggest: []

  - name: manual_review_flag
    description: "Flag invoice for manual review"
    source_file: scripts/manual_review_flag.py
    read_only: false
    destructive: false
    idempotent: true
    cost: low
    latency: fast
    input:
      file_path:
        type: string
        required: true
      reason:
        type: string
        required: false
        default: "Validation failed"
    output:
      ticket_id: string
    on_success:
      suggest: []

runtime:
  type: subprocess
  interpreter: python
  entry: skill_entry

permissions:
  network: false
  filesystem: read
  external_api: false
---
