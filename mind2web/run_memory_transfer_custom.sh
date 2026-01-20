#!/bin/bash

# Default retrieve_type to bm25 if not provided
RETRIEVE_TYPE=${1:-bm25}

# Validate retrieve_type argument
if [[ "$RETRIEVE_TYPE" != "bm25" && "$RETRIEVE_TYPE" != "embedding" ]]; then
    echo "Error: retrieve_type must be either 'bm25' or 'embedding'"
    echo "Usage: $0 [bm25|embedding]"
    exit 1
fi

echo "Running with retrieve_type: $RETRIEVE_TYPE"

python pipeline_memory_transfer_custom.py \
    --setup memory_transfer_custom \
    --benchmark "test_task" \
    --model "gpt-5-mini" \
    --results_dir "results_memory_transfer_custom" \
    --temperature 0.0 \
    --private_memory_path "/c2/taeil/AWM/mind2web/data/reasoning_bank.json" \
    --private_memory_embeddings_path "/c2/taeil/AWM/mind2web/data/reasoning_bank_embeddings.json" \
    --transfer_memory_path "/c2/taeil/AWM/webarena/data/reasoning_bank.json" \
    --transfer_memory_embeddings_path "/c2/taeil/AWM/webarena/data/reasoning_bank_embeddings.json" \
    --retrieve_type "$RETRIEVE_TYPE"