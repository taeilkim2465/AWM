import os, json, random
import numpy as np
from pathlib import Path
from openai import BadRequestError
from utils.env import *
from utils.llm import (
    generate_response, num_tokens_from_messages,
    MAX_TOKENS, extract_from_response,
)
from utils.reasoning_bank import ReasoningBank
from utils.distiller import MemoryDistiller

import logging
logger = logging.getLogger(__name__)

# Initialize Bank and Distiller
# Note: In a real distributed setting, we might need a more robust singleton or DB
# reasoning_bank = ReasoningBank() # Removed global instantiation
memory_distiller = MemoryDistiller()


def get_relevant_memories(args, task_query: str, domain: str, retrieve_type: str, reasoning_bank: ReasoningBank) -> str:
    """Retrieve relevant memories from Reasoning Bank and format them for the prompt."""
    memories = reasoning_bank.retrieve(task_query, top_k=3, domain=domain, retrieve_type=retrieve_type)

    if not memories:
        return ""

    # Format memories for the prompt
    formatted_memories = "\n\n### Relevant Experience from Past Tasks:\n"
    for i, item in enumerate(memories):
        formatted_memories += f"Memory {i+1}:\n"
        formatted_memories += f"- Title: {item.get('title', 'N/A')}\n"
        formatted_memories += f"- Description: {item.get('description', 'N/A')}\n"
        formatted_memories += f"- Content: {item.get('content', 'N/A')}\n"

    return formatted_memories


def get_exemplars(args) -> list:
    """Get exemplar workflows in the prompt."""
    # workflow memory
    memory = []
    workflow_text = open(args.workflow_path, 'r').read().strip()
    if len(workflow_text):
        memory = [[{"role": "user", "content": workflow_text}]]

    # concrete examples
    with open(os.path.join(args.memory_path, "exemplars.json"), "r") as f:
        concrete_examples = json.load(f)
    if any([args.website in cex[0].get("specifier", "") for cex in concrete_examples]):
        concrete_examples = [
            cex for cex in concrete_examples 
            if all([tag in cex[0].get("specifier", "") for tag in [args.domain, args.subdomain, args.website] if tag is not None])
        ]
    elif args.subdomain and any([args.subdomain in cex[0].get("specifier", "") for cex in concrete_examples]):
        concrete_examples = [
            cex for cex in concrete_examples 
            if all([tag in cex[0].get("specifier", "") for tag in [args.domain, args.subdomain] if tag is not None])
        ]

    memory += random.sample(concrete_examples, 
        min(args.retrieve_top_k, len(concrete_examples)))
    memory = [[{k:v for k,v in m.items() if k!="specifier"} for m in e] for e in memory]
    return memory


import os, json, random
import numpy as np
from pathlib import Path
from openai import BadRequestError
from utils.env import *
from utils.llm import (
    generate_response, num_tokens_from_messages,
    MAX_TOKENS, extract_from_response,
)
from utils.reasoning_bank import ReasoningBank
from utils.distiller import MemoryDistiller

import logging
logger = logging.getLogger(__name__)

# Initialize Bank and Distiller
# Note: In a real distributed setting, we might need a more robust singleton or DB
# reasoning_bank = ReasoningBank() # Removed global instantiation
memory_distiller = MemoryDistiller()


def get_relevant_memories(args, task_query: str, domain: str, retrieve_type: str, reasoning_bank: ReasoningBank) -> str:
    """Retrieve relevant memories from Reasoning Bank and format them for the prompt."""
    memories = reasoning_bank.retrieve(task_query, top_k=3, domain=domain, retrieve_type=retrieve_type)

    if not memories:
        return ""

    # Format memories for the prompt
    formatted_memories = "\n\n### Relevant Experience from Past Tasks:\n"
    for i, item in enumerate(memories):
        formatted_memories += f"Memory {i+1}:\n"
        formatted_memories += f"- Title: {item.get('title', 'N/A')}\n"
        formatted_memories += f"- Description: {item.get('description', 'N/A')}\n"
        formatted_memories += f"- Content: {item.get('content', 'N/A')}\n"

    return formatted_memories


def get_exemplars(args) -> list:
    """Get exemplar workflows in the prompt."""
    # workflow memory
    memory = []
    workflow_text = open(args.workflow_path, 'r').read().strip()
    if len(workflow_text):
        memory = [[{"role": "user", "content": workflow_text}]]

    # concrete examples
    with open(os.path.join(args.memory_path, "exemplars.json"), "r") as f:
        concrete_examples = json.load(f)
    if any([args.website in cex[0].get("specifier", "") for cex in concrete_examples]):
        concrete_examples = [
            cex for cex in concrete_examples 
            if all([tag in cex[0].get("specifier", "") for tag in [args.domain, args.subdomain, args.website] if tag is not None])
        ]
    elif args.subdomain and any([args.subdomain in cex[0].get("specifier", "") for cex in concrete_examples]):
        concrete_examples = [
            cex for cex in concrete_examples 
            if all([tag in cex[0].get("specifier", "") for tag in [args.domain, args.subdomain] if tag is not None])
        ]

    memory += random.sample(concrete_examples, 
        min(args.retrieve_top_k, len(concrete_examples)))
    memory = [[{k:v for k,v in m.items() if k!="specifier"} for m in e] for e in memory]
    return memory


def eval_sample(task_id, args, sample):
    # initialize metrics
    element_acc, action_f1, step_success, success = [], [], [], []
    token_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    conversation = []
    episode_length = len(sample["action_reprs"])

    exemplars = get_exemplars(args)
    # print(exemplars)

    # --- Reasoning Bank Injection ---
    relevant_memories = ""
    reasoning_bank_for_update = None # This will be the bank used for updates/additions
    if args.enable_reasoning_bank:
        current_domain = sample.get('domain', args.domain if args.domain else "")
        
        if args.is_memory_transfer_custom:
            # Custom logic to retrieve from two separate banks and combine
            # Private bank for current task's domain
            private_bank = ReasoningBank(
                storage_path=args.private_memory_path,
                embedding_path=args.private_memory_embeddings_path
            )
            # Transfer bank for other domains
            transfer_bank = ReasoningBank(
                storage_path=args.transfer_memory_path,
                embedding_path=args.transfer_memory_embeddings_path
            )

            # Retrieve from private bank (top 3)
            private_mems = private_bank.retrieve(sample['confirmed_task'], top_k=3, domain=current_domain, retrieve_type=args.retrieve_type)
            # Retrieve from transfer bank (top 3) - here we allow retrieval from any domain as it's "transfer"
            transfer_mems = transfer_bank.retrieve(sample['confirmed_task'], top_k=3, domain=None, retrieve_type=args.retrieve_type) # No domain filter for transfer

            combined_mems = private_mems + transfer_mems
            
            # Format combined memories for the prompt
            if combined_mems:
                formatted_memories = "\n\n### Relevant Experience from Past Tasks:\n"
                for i, item in enumerate(combined_mems):
                    formatted_memories += f"Memory {i+1}:\n"
                    formatted_memories += f"- Title: {item.get('title', 'N/A')}\n"
                    formatted_memories += f"- Description: {item.get('description', 'N/A')}\n"
                    formatted_memories += f"- Content: {item.get('content', 'N/A')}\n"
                relevant_memories = formatted_memories
            
            # For the update loop later, we'll use the private bank to store new memories
            reasoning_bank_for_update = private_bank

        else:
            # Standard logic: use a single reasoning bank
            standard_reasoning_bank = ReasoningBank(
                storage_path=args.private_memory_path, # Using private_memory_path for consistency
                embedding_path=args.private_memory_embeddings_path
            )
            relevant_memories = get_relevant_memories(args, sample['confirmed_task'], current_domain, args.retrieve_type, standard_reasoning_bank)
            reasoning_bank_for_update = standard_reasoning_bank
    
    base_system_prompt = "You are a large language model trained to navigate the web. Output the next action and wait for the next observation. Here is the action space:\n1. `CLICK [id]`: Click on an HTML element with its id.\n2. `TYPE [id] [value]`: Type a string into the element with the id.\n3. `SELECT [id] [value]`: Select a value for an HTML element by its id."
    
    full_system_content = base_system_prompt + relevant_memories
    # --------------------------------

    sys_message = [
        {
            "role": "system",
            "content": full_system_content,
        }
    ]

    prev_actions, prev_obs = [], []
    previous_k = 5

    for s, act_repr in zip(sample["actions"], sample["action_reprs"]):
        _, target_act = get_target_obs_and_act(s)
        pos_candidates = [
            c for c in s["pos_candidates"] if c["rank"] < args.top_k_elements
        ]

        # get query, obs, act
        target_obs, _ = get_top_k_obs(s, args.previous_top_k_elements)
        # Continue next loop if the ground truth element is not in the cleaned html
        if len(pos_candidates) == 0:
            element_acc.append(0)
            action_f1.append(0)
            step_success.append(0)
            prev_obs.append("Observation: `" + target_obs + "`")
            prev_actions.append("Action: `" + target_act + "` (" + act_repr + ")")
            conversation.append("The ground truth element is not in cleaned html")
            continue

        # construct query
        query = []
        for o, a in zip(prev_obs, prev_actions):
            if len(query) == 0:
                query.append({
                    "role": "user",
                    "content": f"Task: {sample['confirmed_task']}\nTrajectory:\n" + o,
                })
            else:
                query.append({"role": "user", "content": o})
            query.append({"role": "assistant", "content": a})
        
        obs, _ = get_top_k_obs(s, args.top_k_elements, use_raw=False)
        if len(query) == 0:
            query.append({
                "role": "user",
                "content": f"Task: {sample['confirmed_task']}\nTrajectory:\n"
                + "Observation: `" + obs + "`",
            })
        else:
            query.append({"role": "user", "content": "Observation: `" + obs + "`"})
        
        prev_obs.append("Observation: `" + target_obs + "`")
        prev_actions.append("Action: `" + target_act + "` (" + act_repr + ")")
        
        # token limit
        total_num_tokens = num_tokens_from_messages(sys_message + query, args.model)
        if total_num_tokens > MAX_TOKENS[args.model]:
            logger.info(
                f"Too many tokens in acting ({total_num_tokens} / {MAX_TOKENS[args.model]}), skipping..."
            )
            element_acc.append(0)
            action_f1.append(0)
            step_success.append(0)
            conversation.append(
                {
                    "input": sys_message + query,
                    "output": f"FAILED DUE TO THE CONTEXT LIMIT: {total_num_tokens}",
                }
            )
            continue

        # message
        demo_message = []
        for e_id, e in enumerate(exemplars):
            total_num_tokens = num_tokens_from_messages(
                sys_message + demo_message + e + query, args.model
            )
            if total_num_tokens > MAX_TOKENS[args.model]:
                logger.info(
                    f"Using {e_id} / {len(exemplars)} exemplars due to context limit"
                )
                break
            else:
                demo_message.extend(e)

        message = sys_message + demo_message + query
        try:
            response, info = generate_response(
                messages=message,
                model=args.model,
                temperature=args.temperature,
                stop_tokens=["Task:", "obs:"],
            )
        except Exception as e:
            print(f"LLM Error: {e}") # Print the specific error
            response = ""
            info = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
        conversation.append({"input": message, "output": response, "token_stats": info})
        for k, v in info.items():
            token_stats[k] += v
        pred_act = extract_from_response(response, "`")
        pred_op, pred_id, pred_val = parse_act_str(pred_act)
        target_op, _, target_val = parse_act_str(target_act)

        # calculate metrics
        pos_ids = [c["backend_node_id"] for c in s["pos_candidates"]][:1]
        if pred_id in pos_ids:
            element_acc.append(1)
        else:
            element_acc.append(0)
        action_f1.append(
            calculate_f1(
                construct_act_str(pred_op, pred_val),
                construct_act_str(target_op, target_val),
            )
        )
        conversation.append({"pred_act": pred_act, "target_act": target_act})
        if pred_act == target_act:
            step_success.append(1)
        else:
            step_success.append(0)

    # check the last episode_length of step_success, if all 1, then success = 1
    outcome_str = "FAILURE"
    if np.sum(step_success[-episode_length:]) == episode_length:
        success.append(1)
        outcome_str = "SUCCESS"
    else:
        success.append(0)

    conversation.append(
        {
            "element_acc": element_acc,
            "action_f1": action_f1,
            "step_success": step_success,
            "success": success,
        }
    )
    # log_dir = Path(f"{args.log_dir}/{args.model}/{args.benchmark}/{args.website}/{args.suffix}")
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(os.path.join(log_dir, f"{task_id}.json"), "w") as f:
        json.dump(conversation, f, indent=2)

    # --- Reasoning Bank Update Loop ---
    # According to the paper, we distill insights from both Success and Failure.
    # Use reasoning_bank_for_update which is the private bank in custom memory transfer mode
    if args.enable_reasoning_bank and reasoning_bank_for_update: # Make sure bank was instantiated
        try:
            # Group steps by success/failure for separate distillation
            success_steps = []
            failure_steps = []

            for i, (act, obs, s_success) in enumerate(zip(prev_actions, prev_obs, step_success)):
                step_str = f"Step {i+1}:\n{obs}\n{act}\n\n"
                if s_success:
                    success_steps.append(step_str)
                else:
                    failure_steps.append(step_str)

            # Distill successful steps separately
            if success_steps:
                success_traj = "".join(success_steps)
                success_memory_items = memory_distiller.distill(
                    task=sample['confirmed_task'],
                    trajectory=success_traj,
                    outcome="SUCCESS",
                    domain=args.domain if args.domain else "",
                    prompt_type="success"
                )

                # Store each memory item as a separate entry with its own embedding
                if success_memory_items:
                    for item in success_memory_items:
                        reasoning_bank_for_update.add_memory_item(
                            task_query=sample['confirmed_task'],
                            memory_item=item,
                            outcome="SUCCESS",
                            domain=args.domain if args.domain else "",
                            context=f"Successful steps from task (Total: {len(success_steps)} steps)"
                        )
                    logger.info(f"Distilled and saved {len(success_memory_items)} success memory items for task {task_id}")

            # Distill failed steps separately
            if failure_steps:
                failure_traj = "".join(failure_steps)
                failure_memory_items = memory_distiller.distill(
                    task=sample['confirmed_task'],
                    trajectory=failure_traj,
                    outcome="FAILURE",
                    domain=args.domain if args.domain else "",
                    prompt_type="failure"
                )

                # Store each memory item as a separate entry with its own embedding
                if failure_memory_items:
                    for item in failure_memory_items:
                        reasoning_bank_for_update.add_memory_item(
                            task_query=sample['confirmed_task'],
                            memory_item=item,
                            outcome="FAILURE",
                            domain=args.domain if args.domain else "",
                            context=f"Failed steps from task (Total: {len(failure_steps)} steps)"
                        )
                    logger.info(f"Distilled and saved {len(failure_memory_items)} failure memory items for task {task_id}")

        except Exception as e:
            logger.error(f"Error during Reasoning Bank update: {e}")

