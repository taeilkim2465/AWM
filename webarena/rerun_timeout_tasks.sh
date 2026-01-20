#!/bin/bash

# Environment setup
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

# Timeout task IDs by website (excluding already completed: 103, 105, 293, 297, 309, 310)
declare -A TIMEOUT_TASKS
TIMEOUT_TASKS[gitlab]="310 312 317 318 394 396 397 398 416 447 533 534 535 536 537 553 554 555 567 660 662 663 664 791 808"
TIMEOUT_TASKS[map]="237"
TIMEOUT_TASKS[reddit]="404"
TIMEOUT_TASKS[shopping_admin]="680 697"

# Counters
total_tasks=0
completed_tasks=0
failed_tasks=0

# Calculate total tasks
for site in "${!TIMEOUT_TASKS[@]}"; do
    for tid in ${TIMEOUT_TASKS[$site]}; do
        ((total_tasks++))
    done
done

echo ""
echo "=================================================="
echo "🔄 Rerunning Timeout Tasks"
echo "=================================================="
echo "Total timeout tasks to rerun: $total_tasks"
echo ""

# Function to run a single task
run_task() {
    local tid=$1
    local site=$2
    local TASK_TIMEOUT=900  # 15 minutes

    echo ""
    echo "============================================"
    echo "▶️  Starting task $tid (website: $site)"
    echo "   Progress: $((completed_tasks + failed_tasks + 1))/$total_tasks"
    echo "============================================"

    local start_time=$(date +%s)

    # Step 1: Run inference with reasoning bank
    echo "🔹 Step 1/3: Running inference..."
    timeout $TASK_TIMEOUT python run.py \
        --task_name "webarena.${tid}" \
        --enable_reasoning_bank "True" \
        --reasoning_bank_path "data/reasoning_bank.json" \
        --retrieve_type "$RETRIEVE_TYPE"

    if [ $? -eq 124 ]; then
        echo "⏱️  Task $tid timed out during inference"
        echo "{\"task_id\": $tid, \"status\": \"timeout\", \"stage\": \"inference\"}" >> rerun_timeout_log.jsonl
        ((failed_tasks++))
        return 1
    elif [ $? -ne 0 ]; then
        echo "❌ Task $tid failed during inference"
        echo "{\"task_id\": $tid, \"status\": \"failed\", \"stage\": \"inference\"}" >> rerun_timeout_log.jsonl
        ((failed_tasks++))
        return 1
    fi

    # Calculate remaining time
    local elapsed=$(($(date +%s) - start_time))
    local time_left=$((TASK_TIMEOUT - elapsed))

    if [ $time_left -le 0 ]; then
        echo "⏱️  Task $tid ran out of time after inference"
        echo "{\"task_id\": $tid, \"status\": \"timeout\", \"stage\": \"post_inference\"}" >> rerun_timeout_log.jsonl
        ((failed_tasks++))
        return 1
    fi

    # Step 2: Run evaluation
    echo "🔹 Step 2/3: Running evaluation..."
    timeout $time_left python -m autoeval.evaluate_trajectory \
        --result_dir "results/webarena.${tid}"

    if [ $? -eq 124 ]; then
        echo "⏱️  Task $tid timed out during evaluation"
        echo "{\"task_id\": $tid, \"status\": \"timeout\", \"stage\": \"evaluation\"}" >> rerun_timeout_log.jsonl
        ((failed_tasks++))
        return 1
    elif [ $? -ne 0 ]; then
        echo "⚠️  Task $tid evaluation failed (continuing anyway)"
    fi

    # Calculate remaining time
    elapsed=$(($(date +%s) - start_time))
    time_left=$((TASK_TIMEOUT - elapsed))

    if [ $time_left -le 0 ]; then
        echo "⏱️  Task $tid ran out of time after evaluation"
        echo "{\"task_id\": $tid, \"status\": \"timeout\", \"stage\": \"post_evaluation\"}" >> rerun_timeout_log.jsonl
        ((failed_tasks++))
        return 1
    fi

    # Step 3: Update reasoning bank
    echo "🔹 Step 3/3: Updating reasoning bank..."
    timeout $time_left python -m utils.reasoning_bank \
        --result_dir "results/webarena.${tid}" \
        --reasoning_bank_path "data/reasoning_bank.json"

    if [ $? -eq 124 ]; then
        echo "⏱️  Task $tid timed out during reasoning bank update"
        echo "{\"task_id\": $tid, \"status\": \"timeout\", \"stage\": \"reasoning_bank\"}" >> rerun_timeout_log.jsonl
        ((failed_tasks++))
        return 1
    elif [ $? -ne 0 ]; then
        echo "⚠️  Task $tid reasoning bank update failed (continuing anyway)"
    fi

    # Move result to website directory
    if [ -d "results/webarena.${tid}" ]; then
        mkdir -p "results/${site}"
        mv "results/webarena.${tid}" "results/${site}/"
        echo "📁 Moved result to results/${site}/"
    fi

    echo "✅ Task $tid completed successfully"
    echo "{\"task_id\": $tid, \"status\": \"success\"}" >> rerun_completed_log.jsonl
    ((completed_tasks++))
    return 0
}

# Process tasks by website
for site in gitlab map reddit shopping_admin; do
    if [ -n "${TIMEOUT_TASKS[$site]}" ]; then
        echo ""
        echo "##################################################"
        echo "📍 Processing site: $site"
        echo "##################################################"

        # Create a temporary task ID file for this site
        temp_file=$(mktemp)
        for tid in ${TIMEOUT_TASKS[$site]}; do
            echo "$tid" >> "$temp_file"
        done

        # Run each task for this site
        while read -r tid; do
            run_task "$tid" "$site"
        done < "$temp_file"

        rm -f "$temp_file"
    fi
done

# Final summary
echo ""
echo "=================================================="
echo "🎉 All Timeout Tasks Processed"
echo "=================================================="
echo "Total: $total_tasks"
echo "Completed: $completed_tasks"
echo "Failed/Timeout: $failed_tasks"
echo "Success rate: $(awk "BEGIN {printf \"%.1f\", ($completed_tasks/$total_tasks)*100}")%"
echo "=================================================="
echo ""

# Show completed tasks
if [ -f rerun_completed_log.jsonl ]; then
    echo "Completed tasks:"
    cat rerun_completed_log.jsonl
    echo ""
fi

# Show failed/timeout tasks
if [ -f rerun_timeout_log.jsonl ]; then
    echo "Failed/Timeout tasks:"
    cat rerun_timeout_log.jsonl
fi
