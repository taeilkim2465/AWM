import os
import re
import ast
import json
import argparse
import traceback
from autoeval.evaluator import Evaluator
from autoeval.clients import CLIENT_DICT


# def load_blocks(path: str) -> list[list[str]]:
#     """Load blank-line separated blocks from the log file."""
#     blocks, block = [], []
#     for line in open(path, 'r'):
#         if line.strip() == "":
#             blocks.append(block)
#             block = []
#         else:
#             if line.strip():
#                 block.append(line.strip())
#     assert len(blocks) % 2 == 0
#     return blocks

# def remove_invalid_steps(actions: list[str]) -> list[str]:
#     """Remove invalid steps from the action sequence."""
#     valid_actions = []
#     for a in actions:
#         if "click(" in a:
#             arg = a[a.index("(")+1: a.index(")")]
#             if type(eval(arg)) == str:
#                 valid_actions.append(a)
#         elif "fill(" in a:
#             arg = a[a.index("(")+1: a.index(",")].strip()
#             if type(eval(arg)) == str:
#                 valid_actions.append(a)
#         else:
#             valid_actions.append(a)
#     return valid_actions


# def extract_think_and_action(path: str) -> tuple[list[str], list[str]]:
#     """Extract the task trajectory from the log file."""
#     blocks = load_blocks(path)
#     think_list, action_list = [], []
#     for i in range(1, len(blocks), 2):
#         # action
#         b = blocks[i]
#         actions = remove_invalid_steps(b[1:])
#         if len(actions) == 0: continue
#         action_list.append(actions)
#         # think
#         b = blocks[i-1]
#         idx = b[-1].index("browsergym.experiments.loop - INFO -")
#         think_list.append(b[-1][idx+36: ].strip())
    
#     assert len(think_list) == len(action_list)
    
#     # TODO: merge same actions
#     return think_list, action_list

def remove_invalid_steps(actions: list[str]) -> list[str]:
    """
    Remove invalid steps from the action sequence securely.
    Ensures arguments for specific commands are strings.
    """
    valid_actions = []
    for a in actions:
        try:
            # Parse the function call string like "click('42')"
            # We look for the first parenthesis to identify the function name
            if "(" not in a or not a.endswith(")"):
                # If it's not a function call format, decide whether to keep or drop.
                # Usually purely python code lines might appear here.
                # For safety, let's skip if it doesn't look like a call.
                continue

            func_name = a[:a.index("(")].strip()
            args_str = a[a.index("(")+1 : -1].strip() # content inside ()

            # Commands that require string arguments (selectors/text)
            if func_name in ["click", "fill", "hover", "type"]:
                # If fill, it has multiple args, we usually care about the first one (locator)
                first_arg = args_str.split(",")[0].strip()
                
                # Use ast.literal_eval for safe evaluation instead of eval()
                try:
                    parsed_arg = ast.literal_eval(first_arg)
                    if isinstance(parsed_arg, str):
                        valid_actions.append(a)
                except (ValueError, SyntaxError):
                    # If it cannot be evaluated (e.g. variable name instead of literal), skip
                    continue
            else:
                # Commands like scroll(x, y), go_back(), etc. are passed through
                valid_actions.append(a)
                
        except Exception:
            # If parsing fails drastically, skip this line
            continue
            
    return valid_actions


def extract_think_and_action(path: str) -> tuple[list[str], list[list[str]]]:
    """
    Extract the task trajectory from the log file by parsing raw lines.
    Matches the 'think' from the logger info with the subsequent 'action'.
    """
    think_list = []
    action_list = []
    
    # Regex to capture the timestamp and log prefix to identify new log entries
    # e.g., "2025-12-31 06:52:51,763 - 72660 - browsergym.experiments.loop - INFO -"
    log_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - .*? - (.*?)(?: - (.*))?$')
    
    current_think = None
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 1. Parse Log Headers to find "Think"
        match = log_pattern.match(lines[i])
        if match:
            logger_name = match.group(1)
            content = match.group(2) if match.group(2) else ""
            
            # BrowserGym loop INFO typically contains the reasoning
            if "browsergym.experiments.loop" in logger_name and "INFO" in lines[i]:
                # Filter out system messages that are not thoughts
                if content and not any(x in content for x in [
                    "Running experiment", 
                    "Overriding the task", 
                    "Query failed", 
                    "Saving summary"
                ]):
                    current_think = content.strip()

        # 2. Parse Actions
        # Actions strictly follow the line "action:"
        if line == "action:":
            extracted_actions = []
            j = i + 1
            
            # Read subsequent lines until next timestamp or empty block end
            while j < len(lines):
                next_line = lines[j].strip()
                # Stop if we hit a new log timestamp
                if re.match(r'^\d{4}-\d{2}-\d{2}', next_line):
                    break
                if next_line:
                    extracted_actions.append(next_line)
                j += 1
            
            # Validate and clean actions
            valid_actions = remove_invalid_steps(extracted_actions)
            
            # Only append if we have a valid action pair
            # (If multiple thinks occurred before this action, we take the most recent one)
            if valid_actions and current_think:
                # TODO Logic: Check if this action is identical to the previous one (merging)
                if not (action_list and action_list[-1] == valid_actions and think_list[-1] == current_think):
                    think_list.append(current_think)
                    action_list.append(valid_actions)
                
                # Reset current_think to ensure 1:1 mapping for the next step
                # (unless you want to reuse the thought for multiple separate actions)
                current_think = None
            
            # Move index forward
            i = j - 1
            
        i += 1

    assert len(think_list) == len(action_list), f"Mismatch: {len(think_list)} thinks vs {len(action_list)} actions"
    return think_list, action_list



def extract_response(action: str) -> str:
    s, e = action.index("(")+1, action.index(")")
    return action[s: e]


def process_sample(
    idx: str, traj_info: dict, log_save_path,
    model: str, eval_version: str,
) -> list[dict]:
    clients = {model: CLIENT_DICT[model](model_name=model)}
    evaluator = Evaluator(clients, log_save_path=log_save_path + "/trajs")
    try:
        out, _ = evaluator(traj_info, model, eval_version)
        eval_result = None
        if out["status"].lower() == "success": eval_result = True
        else: eval_result = False
        return [{
                "idx": idx,
                "gt": traj_info["eval"],
                "rm": eval_result,
                "thoughts": out["thoughts"], 
                "uid": traj_info["traj_name"],
        }]
    except Exception as e:
        print(f"Error on {idx}, {e}")
        print(traceback.format_exc())
        return {
            "idx": idx,
            "gt": traj_info["eval"],
            "rm": None,
            "thoughts": None, 
            "uid": traj_info["traj_name"],
        }


def main():
    # load task config
    task_id = args.result_dir.split('/')[-1].split(".")[1]
    config_path = os.path.join("config_files", f"{task_id}.json")
    config = json.load(open(config_path))

    # load trajectory log
    log_path = os.path.join(args.result_dir, "experiment.log")
    think_list, action_list = extract_think_and_action(log_path)
    actions = [act for acts in action_list for act in acts]
    if action_list and len(action_list) > 0 and "send_msg_to_user" in action_list[-1][0]:
        response = extract_response(action_list[-1][0])
    else:
        response = ""
    
    # load summary info
    summary_path = os.path.join(args.result_dir, "summary_info.json")
    summary = json.load(open(summary_path, 'r'))

    # collect traj info
    image_paths = [
        os.path.join(args.result_dir, f) for f in os.listdir(args.result_dir) 
        if f.startswith("screenshot_step_") and f.endswith(".png")
    ]
    image_paths = sorted(image_paths, key=lambda x: int(x.split('/')[-1].split("_")[-1].split(".")[0]))
    traj_info = {
        "intent": config["intent"],
        "response": response,
        "captions": think_list,
        "actions": actions,
        "traj_name": config["task_id"],
        "image_paths": image_paths,
        "images": image_paths,
        "eval": summary["cum_reward"]
    }

    # evaluate trajectory
    log_save_path = os.path.join("autoeval/log", args.result_dir.split('/')[-1])
    print("Log Save Path:", log_save_path)
    if not os.path.exists(log_save_path):
        os.makedirs(log_save_path)
        os.makedirs(log_save_path + "/trajs")
    eval_info = process_sample(
        idx=config["task_id"], traj_info=traj_info,
        log_save_path=log_save_path, 
        model=args.model, eval_version=args.prompt,
    )
    output_eval_path = os.path.join(args.result_dir, f"{args.model}_autoeval.json")
    json.dump(eval_info, open(output_eval_path, 'w'))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result_dir", type=str, required=True,
                        help="Path to the result directory, e.g., 'webarena.0'.")
    # autoeval
    parser.add_argument("--model", type=str, default="gpt-5-mini",
                        choices=["gpt-3.5", "gpt-4", "gpt-4o", "gpt-5-mini"])
    parser.add_argument("--prompt", type=str, default="text",
                        choices=["text", "vision"])

    args = parser.parse_args()

    if (args.model == "gpt-4o" or args.model == "gpt-5-mini") and args.prompt != "vision":
        print(f"Waring: use vision prompt by default for {args.model}.")
        args.prompt = "vision"

    main()
