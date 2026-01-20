import os
import json
import random
import argparse

import openai
openai.api_key = os.environ["OPENAI_API_KEY"]
from openai import OpenAI
client = OpenAI()
from cost_tracker import log_usage
# from autoeval.clients import GPT5_LM_Client

# %% load examples
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
#             try:
#                 if type(eval(arg)) == str and type(eval(arg[1:-1])) == int:
#                     valid_actions.append(a)
#             except:
#                 continue
#         elif "fill(" in a:
#             arg = a[a.index("(")+1: a.index(",")].strip()
#             if type(eval(arg)) == str:
#                 valid_actions.append(a)
#         elif "scroll(" in a or "noop(" in a:
#             continue
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


def format_trajectory(think_list: list[str], action_list: list[list[str]]) -> str:
    trajectory = []
    for t, a in zip(think_list, action_list):
        acts = '\n'.join(a)
        trajectory.append(f"<think>\n{t}\n</think>\n<action>\n{acts}\n</action>")
    return '\n\n'.join(trajectory)

def random_group_sample(d: dict, n) -> list:
    """Randomly sample n groups from the dictionary."""
    return [ex for v in d.values() for ex in random.sample(v, min(n, len(v)))]

# %% prompt model
def format_examples(examples: list[dict]) -> str:
    """Format examples to the prompt."""
    formatted_examples = []
    for ex in examples:
        trajectory = format_trajectory(ex["think_list"], ex["action_list"])
        formatted_examples.append(f"Query: {ex['query']}\nActions:\n{trajectory}")
    return '\n\n'.join(["## Concrete Examples"] + formatted_examples + ["## Summary Workflows"])

def llm_generate(examples: list[dict], args, verbose: bool = False):
    """Call gpt model to generate workflows."""
    prompt = format_examples(examples)
    prompt = '\n\n'.join([args.INSTRUCTION, args.ONE_SHOT, prompt])
    if verbose: print("Prompt:\n", prompt, '\n\n')
    response = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0,
        max_completion_tokens=8192, 
    )
    if response.usage:
        log_usage(
            model=response.model,
            step_name="induce_prompt",
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens
        )

    response = response.choices[0].message.content

    # llm_client = GPT5_LM_Client(model_name=args.model, max_tokens=8192)
    # messages = [{"role": "user", "content": prompt}]
    # response, _ = llm_client.chat(messages, json_mode=False)
    
    if verbose: print(response)
    return response


def main():
    # collect result directories, e.g., ["results/webarena.0", ...]
    args.result_dir = args.result_dir.split()
    if args.criteria == "gt":
        file_dirs = [
            os.path.join(res_dir, f) for res_dir in args.result_dir for f in os.listdir(res_dir) 
            if json.load(
                open(os.path.join(res_dir, f, "summary_info.json"))
            )["cum_reward"]
        ]
    elif args.criteria == "autoeval":
        file_dirs = []
        for res_dir in args.result_dir:
            for f in os.listdir(res_dir):
                record_path = os.path.join(res_dir, f, f"{args.model}_autoeval.json")
                if not os.path.exists(record_path): continue
                record = json.load(open(record_path))
                if record[0]["rm"]:
                    file_dirs.append(os.path.join(res_dir, f))
    else:
        raise ValueError(f"Invalid criteria: {args.criteria}.")
    
    print(f"Collected {len(file_dirs)} result directories.")

    # template id based deduplication
    template_dict = {}
    for f in file_dirs:
        # get query -> task objective
        task_id = f.split('/')[-1].split("_")[0].split(".")[1]
        config_path = os.path.join("config_files", f"{task_id}.json")
        config = json.load(open(config_path))
        query = config["intent"]

        template_id = config["intent_template_id"] # for deduplication

        # parse trajectory
        log_path = os.path.join(f, "experiment.log")
        try:
            think_list, action_list = extract_think_and_action(log_path)
        except:
            continue

        # add to template dict
        wdict = {"query": query, "think_list": think_list, "action_list": action_list}
        if template_id not in template_dict: template_dict[template_id] = []
        template_dict[template_id].append(wdict)
    selected_examples = random_group_sample(template_dict, args.num_samples)
    print(f"#{len(selected_examples)} result dirs after template dedup..")
    
    # prompt model to induce workflows
    workflows = llm_generate(selected_examples, args, True)
    workflows += "\n\nclick('id') # input string id value for all actions\n\nselect_option('id', 'value') # for dropdown menu"

    if args.output_path is None:
        website = config["sites"][0]  # assumes all results are about the same website
        args.output_path = f"workflow/{website}_neural.txt"
        print(f"[Warning] no output path specified, using '{args.output_path}' by default")
        
    with open(args.output_path, 'w') as fw:
        fw.write(workflows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result_dir", type=str, default="results",
                        help="Path to the result directory. Support multiple directories separated by space.")
    parser.add_argument("--output_path", type=str, default=None,
                        help="Path to the output file.")
    parser.add_argument("--criteria", type=str, default="autoeval", 
                        choices=["gt", "autoeval"],
                        help="'gt': only use examples with gold reward, 'autoeval': use examples with autoeval reward.")
    parser.add_argument("--model", type=str, default="gpt-5-mini",
                        choices=["gpt-3.5", "gpt-4", "gpt-4o", "gpt-5-mini"])
    parser.add_argument("--num_samples", type=int, default=1, help="Max number of samples to input per template.")
    args = parser.parse_args()

    args.INSTRUCTION = open("prompt/instruction.txt", 'r').read()
    args.ONE_SHOT = open("prompt/one_shot.txt", 'r').read()

    main()
