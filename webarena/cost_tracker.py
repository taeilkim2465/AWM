import json
import os
from datetime import datetime

LOG_FILE = "total_cost_log.jsonl"

def log_usage(model: str, prompt_tokens: int, completion_tokens: int, step_name: str = ""):
    """API 사용량을 파일에 기록합니다."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "step": step_name,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens
    }
    
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")

def calculate_total_cost():
    """기록된 로그를 읽어 총 비용을 계산합니다."""
    
    PRICING = {
        "gpt-5-mini": {"input": 0.25, "output": 2.00}, 
        "gpt-4o":     {"input": 2.50, "output": 10.00},
    }
    
    total_cost = 0.0
    input_tokens_sum = 0
    output_tokens_sum = 0
    
    if not os.path.exists(LOG_FILE):
        print(f"Log file {LOG_FILE} not found.")
        return 0.0

    print(f"\n--- Cost Calculation (Default: gpt-5-mini) ---")
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                
                model_name = record.get("model", "gpt-5-mini")
                
                p_tok = record.get("prompt_tokens", 0)
                c_tok = record.get("completion_tokens", 0)
                
                price_key = next((k for k in PRICING if k in model_name), "gpt-5-mini")
                
                cost = (p_tok / 1_000_000 * PRICING[price_key]["input"]) + \
                       (c_tok / 1_000_000 * PRICING[price_key]["output"])
                
                total_cost += cost
                input_tokens_sum += p_tok
                output_tokens_sum += c_tok
                
            except Exception as e:
                continue
    
    print(f"Total Tokens: {input_tokens_sum + output_tokens_sum:,} (In: {input_tokens_sum:,} / Out: {output_tokens_sum:,})")
    print(f"Total Estimated Cost: ${total_cost:.4f}")
    
    return total_cost