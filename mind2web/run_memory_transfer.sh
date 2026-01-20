#!/bin/bash
python pipeline.py \
    --setup baseline \
    --benchmark "test_task" \
    --model "gpt-5-mini" \
    --results_dir "results_memory_transfer" \
    --temperature 0.0 \
    --enable_reasoning_bank True \
    --reasoning_bank_path "/c2/taeil/AWM/webarena/data/reasoning_bank.json" \
    --reasoning_bank_embeddings_path "/c2/taeil/AWM/webarena/data/reasoning_bank_embeddings.json"