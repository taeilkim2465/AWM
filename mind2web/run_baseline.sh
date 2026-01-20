#!/bin/bash

# Run baseline for all websites in test_task benchmark
# This will iterate through all websites and run inference with an empty workflow memory.
# Reasoning Bank (memory) is DISABLED in this baseline run.
# Results will be saved in 'results_baseline/{website}/'

python pipeline.py \
    --setup baseline \
    --benchmark "test_task" \
    --model "gpt-5-mini" \
    --temperature 0.0 \
    --enable_reasoning_bank False

# You can change --benchmark to "test_website" or "test_domain" if needed.
# You can also specify a single website by adding --website "website_name"
