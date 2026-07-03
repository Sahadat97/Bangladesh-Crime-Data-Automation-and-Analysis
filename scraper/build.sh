#!/bin/bash
# Compiles the macOS Vision OCR helper. Run once (or whenever ocr.swift changes).
set -e
cd "$(dirname "$0")"
swiftc ocr.swift -o bin/ocr
echo "Built scraper/bin/ocr"
