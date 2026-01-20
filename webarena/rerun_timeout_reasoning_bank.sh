#!/bin/bash

# Environment setup (same as bulk_run_reasoning_bank.sh)
export WA_SHOPPING="http://10.10.0.120:7770"
export WA_SHOPPING_ADMIN="http://10.10.0.120:7780/admin"
export WA_REDDIT="http://10.10.0.120:9999"
export WA_GITLAB="http://10.10.0.120:8023"
export WA_WIKIPEDIA="http://10.10.0.120:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export WA_MAP="http://10.10.0.120:3000"
export WA_HOMEPAGE="http://10.10.0.120:4399"

# Map WA_ variables to the names expected by browser_env
export SHOPPING=$WA_SHOPPING
export SHOPPING_ADMIN=$WA_SHOPPING_ADMIN
export REDDIT=$WA_REDDIT
export GITLAB=$WA_GITLAB
export WIKIPEDIA=$WA_WIKIPEDIA
export MAP=$WA_MAP
export HOMEPAGE=$WA_HOMEPAGE

export OPENAI_API_KEY=${OPENAI_API_KEY}
export RETRIEVE_TYPE="bm25"

# Timeout task IDs by website
declare -A TIMEOUT_TASKS
TIMEOUT_TASKS[gitlab]="312 317 318 394 396 397 398 416 447 533 534 535 536 537 553 554 555 567 660 662 663 664 791 808"
TIMEOUT_TASKS[map]="237"
TIMEOUT_TASKS[reddit]="404"
# TIMEOUT_TASKS[shopping_admin]="680 697"

# Logging function
log_message() {
    echo "$1" | tee -a rerun_timeout_reasoning_bank.log
}

log_message ""
log_message "=================================================="
log_message "🔄 Rerunning Timeout Tasks with Reasoning Bank"
log_message "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
log_message "=================================================="
log_message ""

# Process each website (same structure as bulk_run_reasoning_bank.sh)
for site in gitlab map reddit shopping_admin; do
    task_ids="${TIMEOUT_TASKS[$site]}"

    if [ -n "$task_ids" ]; then
        log_message ""
        log_message "=================================================="
        log_message "🔄 Starting Reasoning Bank Benchmark for Site: $site"
        log_message "Task IDs: $task_ids"
        log_message "=================================================="

        # Run pipeline for this website's timeout tasks
        # Same as bulk_run_reasoning_bank.sh but with specific task IDs
        # Explicitly pass environment variables
        WA_SHOPPING="$WA_SHOPPING" \
        WA_SHOPPING_ADMIN="$WA_SHOPPING_ADMIN" \
        WA_REDDIT="$WA_REDDIT" \
        WA_GITLAB="$WA_GITLAB" \
        WA_WIKIPEDIA="$WA_WIKIPEDIA" \
        WA_MAP="$WA_MAP" \
        WA_HOMEPAGE="$WA_HOMEPAGE" \
        python pipeline_timeout_tasks.py \
            --website "$site" \
            --task_ids $task_ids \
            --reasoning_bank_path "data/reasoning_bank.json" \
            --retrieve_type "$RETRIEVE_TYPE" 2>&1 | tee -a rerun_timeout_reasoning_bank.log

        sleep 1
    fi
done

log_message ""
log_message "=================================================="
log_message "🎉 All Reasoning Bank Timeout Tasks Completed"
log_message "Finished at: $(date '+%Y-%m-%d %H:%M:%S')"
log_message "=================================================="
