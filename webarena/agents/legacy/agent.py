"""
WARNING DEPRECATED WILL BE REMOVED SOON
"""

import os
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import traceback
from warnings import warn
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from browsergym.core.action.base import AbstractActionSet
from browsergym.utils.obs import flatten_axtree_to_str, flatten_dom_to_str, prune_html
from browsergym.experiments import Agent, AbstractAgentArgs

from ..legacy import dynamic_prompting
from .utils.llm_utils import ParseError, retry
from .utils.chat_api import ChatModelArgs

try:
    from utils.reasoning_bank import ReasoningBank
except ImportError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
    from utils.reasoning_bank import ReasoningBank


@dataclass
class GenericAgentArgs(AbstractAgentArgs):
    chat_model_args: ChatModelArgs = None
    flags: dynamic_prompting.Flags = field(default_factory=lambda: dynamic_prompting.Flags())
    max_retry: int = 4

    def make_agent(self):
        return GenericAgent(
            chat_model_args=self.chat_model_args, flags=self.flags, max_retry=self.max_retry
        )


class GenericAgent(Agent):

    def obs_preprocessor(self, obs: dict) -> dict:
        """
        Augment observations with text HTML and AXTree representations, which will be stored in
        the experiment traces.
        """

        obs = obs.copy()
        obs["dom_txt"] = flatten_dom_to_str(
            obs["dom_object"],
            with_visible=self.flags.extract_visible_tag,
            with_center_coords=self.flags.extract_coords == "center",
            with_bounding_box_coords=self.flags.extract_coords == "box",
            filter_visible_only=self.flags.extract_visible_elements_only,
        )
        # if len(obs["dom_txt"]) > 131072:
        #      obs["dom_txt"] = obs["dom_txt"][:131072] + " ... [TRUNCATED]"

        obs["axtree_txt"] = flatten_axtree_to_str(
            obs["axtree_object"],
            with_visible=self.flags.extract_visible_tag,
            with_center_coords=self.flags.extract_coords == "center",
            with_bounding_box_coords=self.flags.extract_coords == "box",
            filter_visible_only=self.flags.extract_visible_elements_only,
        )
        obs["pruned_html"] = prune_html(obs["dom_txt"])

        return obs

    def __init__(
        self,
        chat_model_args: ChatModelArgs = None,
        flags: dynamic_prompting.Flags = None,
        max_retry: int = 4,
    ):
        self.chat_model_args = chat_model_args if chat_model_args is not None else ChatModelArgs()
        self.flags = flags if flags is not None else dynamic_prompting.Flags()
        self.max_retry = max_retry

        self.chat_llm = chat_model_args.make_chat_model()
        self.action_set = dynamic_prompting._get_action_space(self.flags)
        

        # consistency check
        if self.flags.use_screenshot:
            is_vision = self.chat_model_args.has_vision() or "gpt-5-mini" in self.chat_model_args.model_name
            if not is_vision:
                warn(
                    """\

Warning: use_screenshot is set to True, but the chat model \
does not support vision. Disabling use_screenshot."""
                )
                self.flags.use_screenshot = False

        # reset episode memory
        self.obs_history = []
        self.actions = []
        self.memories = []
        self.thoughts = []
        self.images = []
        self.goal = ""

        # Initialize Reasoning Bank
        self.reasoning_bank = None
        self.reasoning_memories_str = ""
        if self.flags.enable_reasoning_bank:
            rb_path = self.flags.reasoning_bank_path or "data/reasoning_bank.json"
            # Assuming ReasoningBank constructor can handle None or default embedding path
            # The one we copied uses "data/reasoning_bank.json" as default storage
            # and "data/reasoning_bank_embeddings.json" as default embedding
            # If path is provided, we might need to adjust both.
            # For now, let's assume standard paths or passed path.
            # If passed path is "data/my_bank.json", we might want "data/my_bank_embeddings.json"
            # But the constructor takes both arguments.
            # Here we only pass flags.reasoning_bank_path if it exists, otherwise use defaults.
            
            kwargs = {}
            if self.flags.reasoning_bank_path:
                 kwargs["storage_path"] = self.flags.reasoning_bank_path
                 # heuristic for embedding path
                 base, ext = os.path.splitext(self.flags.reasoning_bank_path)
                 kwargs["embedding_path"] = f"{base}_embeddings{ext}"

            self.reasoning_bank = ReasoningBank(**kwargs)

    def _format_memories(self, memories):
        if not memories:
            return ""
        formatted_memories = ""
        for i, item in enumerate(memories):
            formatted_memories += f"Memory {i+1}:\n"
            formatted_memories += f"- Title: {item.get('title', 'N/A')}\n"
            formatted_memories += f"- Description: {item.get('description', 'N/A')}\n"
            formatted_memories += f"- Content: {item.get('content', 'N/A')}\n"
        return formatted_memories

    def get_action(self, obs):

        self.obs_history.append(obs)

        if "screenshot" in obs and obs["screenshot"] is not None:
            self.images.append(obs["screenshot"])
        else:
            self.images.append(None)

        # --- Store Goal (only once) ---
        if not self.goal:
            self.goal = obs.get("goal", "")
            if not self.goal and obs.get("chat_messages"):
                 # Try to find user message
                 for msg in obs["chat_messages"]:
                     if msg["role"] == "user":
                         self.goal = msg["message"]
                         break
        # -------------------------------

        # --- Reasoning Bank Retrieval ---
        if self.flags.enable_reasoning_bank and self.reasoning_bank and not self.reasoning_memories_str:
            if self.goal:
                memories = self.reasoning_bank.retrieve(self.goal, top_k=3, retrieve_type=self.flags.retrieve_type) # Provide top 3, let LLM choose which to use
                self.reasoning_memories_str = self._format_memories(memories)
        # --------------------------------

        # Current step is len(actions) because we haven't added the next action yet
        current_step = len(self.actions)

        # Extract task number from obs (if available)
        if not hasattr(self, 'task_number'):
            self.task_number = self._extract_task_number(obs)

        main_prompt = dynamic_prompting.MainPrompt(
            obs_history=self.obs_history,
            actions=self.actions,
            memories=self.memories,
            thoughts=self.thoughts,
            flags=self.flags,
            reasoning_memories=self.reasoning_memories_str,
            current_step=current_step,
            max_steps=10,  # Default value, matches run.py default
        )

        # Determine the minimum non-None token limit from prompt, total, and input tokens, or set to None if all are None.
        maxes = (
            self.flags.max_prompt_tokens,
            self.chat_model_args.max_total_tokens,
            self.chat_model_args.max_input_tokens,
        )
        maxes = [m for m in maxes if m is not None]
        max_prompt_tokens = min(maxes) if maxes else None

        prompt = dynamic_prompting.fit_tokens(
            main_prompt,
            max_prompt_tokens=max_prompt_tokens,
            model_name=self.chat_model_args.model_name,
        )

        sys_msg = dynamic_prompting.SystemPrompt().prompt
        if self.flags.workflow_path is not None:
            sys_msg += '\n\n' + open(self.flags.workflow_path).read()

        chat_messages = [
            SystemMessage(content=sys_msg),
            HumanMessage(content=prompt),
        ]

        def parser(text):
            try:
                ans_dict = main_prompt._parse_answer(text)
            except ParseError as e:
                # these parse errors will be caught by the retry function and
                # the chat_llm will have a chance to recover
                return None, False, str(e)

            return ans_dict, True, ""

        try:
            ans_dict = retry(self.chat_llm, chat_messages, n_retry=self.max_retry, parser=parser)
            # inferring the number of retries, TODO: make this less hacky
            ans_dict["n_retry"] = (len(chat_messages) - 3) / 2
        except ValueError as e:
            # Likely due to maximum retry. We catch it here to be able to return
            # the list of messages for further analysis
            ans_dict = {"action": None}
            ans_dict["err_msg"] = str(e)
            ans_dict["stack_trace"] = traceback.format_exc()
            ans_dict["n_retry"] = self.max_retry

        self.actions.append(ans_dict["action"])
        self.memories.append(ans_dict.get("memory", None))
        self.thoughts.append(ans_dict.get("think", None))

        ans_dict["chat_messages"] = [m.content for m in chat_messages]
        ans_dict["chat_model_args"] = asdict(self.chat_model_args)

        # Store prompt details for logging
        ans_dict["prompt_details"] = {
            "current_step": current_step,
            "max_steps": 10,
            "system_prompt": sys_msg,
            "user_prompt": prompt if isinstance(prompt, str) else "multimodal_prompt",
            "reasoning_memories": self.reasoning_memories_str,
        }

        # Save prompts and responses to files
        self._save_prompt_logs(current_step, sys_msg, prompt, ans_dict, chat_messages)

        return ans_dict["action"], ans_dict

    def _extract_task_number(self, obs):
        """Extract task number from observation or environment."""
        import re
        import os

        try:
            # Method 1: Check all string values in obs for webarena pattern
            for key, value in obs.items():
                if isinstance(value, str) and "webarena." in value.lower():
                    match = re.search(r'webarena\.(\d+)', value.lower())
                    if match:
                        print(f"[Task extraction] Found task number in obs['{key}']: {match.group(1)}")
                        return match.group(1)

            # Method 2: Try to get from current working directory
            # (experiment.py creates dirs like "results/webarena.144/")
            cwd = os.getcwd()
            match = re.search(r'webarena\.(\d+)', cwd)
            if match:
                print(f"[Task extraction] Found task number in cwd: {match.group(1)}")
                return match.group(1)

            # Method 3: Check environment variable (if set)
            if 'WEBARENA_TASK' in os.environ:
                env_task = os.environ['WEBARENA_TASK']
                match = re.search(r'webarena\.(\d+)', env_task)
                if match:
                    print(f"[Task extraction] Found task number in env var: {match.group(1)}")
                    return match.group(1)
                # If it's just a number
                if env_task.isdigit():
                    print(f"[Task extraction] Found task number in env var (digit): {env_task}")
                    return env_task

            # Method 4: Look for results directory pattern nearby
            for results_path in ['results', '../results', '../../results']:
                if os.path.exists(results_path):
                    # Get the most recently modified webarena.* directory
                    try:
                        webarena_dirs = [d for d in os.listdir(results_path) if d.startswith('webarena.')]
                        if webarena_dirs:
                            # Sort by modification time, get the latest
                            latest = max(webarena_dirs, key=lambda d: os.path.getmtime(os.path.join(results_path, d)))
                            match = re.search(r'webarena\.(\d+)', latest)
                            if match:
                                print(f"[Task extraction] Found task number in results dir: {match.group(1)}")
                                return match.group(1)
                    except Exception:
                        pass

            # Debug: print available obs keys
            print(f"[Task extraction] DEBUG: Available obs keys: {list(obs.keys())}")

            # Default fallback
            return "unknown"
        except Exception as e:
            print(f"Warning: Failed to extract task number: {e}")
            return "unknown"

    def _save_prompt_logs(self, step, system_prompt, user_prompt, ans_dict, chat_messages):
        """Save prompt input/output to separate files for analysis."""
        try:
            # Create logs directory
            log_dir = Path("prompt_logs")
            log_dir.mkdir(exist_ok=True)

            # Get task number
            task_num = getattr(self, 'task_number', 'unknown')

            # Save input prompt with task number in filename
            input_file = log_dir / f"task_{task_num}_step_{step:02d}_input.txt"
            with open(input_file, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write(f"STEP {step} INPUT\n")
                f.write("=" * 80 + "\n\n")
                f.write("=" * 80 + "\n")
                f.write("SYSTEM PROMPT\n")
                f.write("=" * 80 + "\n")
                f.write(system_prompt + "\n\n")
                f.write("=" * 80 + "\n")
                f.write("USER PROMPT\n")
                f.write("=" * 80 + "\n")

                if isinstance(user_prompt, str):
                    f.write(user_prompt + "\n")
                elif isinstance(user_prompt, list):
                    for i, item in enumerate(user_prompt):
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                f.write(item.get("text", "") + "\n")
                            elif item.get("type") == "image_url":
                                # Truncate base64 image data for readability
                                url = item.get("image_url", {}).get("url", "")
                                if url.startswith("data:image"):
                                    f.write(f"[IMAGE_{i}: {url[:50]}...]\n")
                                else:
                                    f.write(f"[IMAGE_{i}: {url}]\n")
                        else:
                            f.write(str(item) + "\n")
                else:
                    f.write(str(user_prompt) + "\n")

            # Save output response
            output_file = log_dir / f"task_{task_num}_step_{step:02d}_output.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write(f"STEP {step} OUTPUT\n")
                f.write("=" * 80 + "\n\n")

                # Get the last assistant message (the actual response)
                for msg in reversed(chat_messages):
                    if isinstance(msg, AIMessage):
                        f.write("### LLM RESPONSE ###\n")
                        f.write(msg.content + "\n\n")
                        break

                f.write("### PARSED ACTION ###\n")
                f.write(f"Action: {ans_dict.get('action', 'None')}\n")
                f.write(f"Memory: {ans_dict.get('memory', 'None')}\n")
                f.write(f"Think: {ans_dict.get('think', 'None')}\n")

                if ans_dict.get("err_msg"):
                    f.write(f"\n### ERROR ###\n")
                    f.write(ans_dict["err_msg"] + "\n")

            # Save summary JSON
            summary_file = log_dir / f"task_{task_num}_step_{step:02d}_summary.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                summary = {
                    "step": step,
                    "action": ans_dict.get("action"),
                    "memory": ans_dict.get("memory"),
                    "think": ans_dict.get("think"),
                    "has_reasoning_memories": bool(self.reasoning_memories_str),
                    "n_retry": ans_dict.get("n_retry", 0),
                    "error": ans_dict.get("err_msg"),
                }
                json.dump(summary, f, indent=2, ensure_ascii=False)

        except Exception as e:
            # Don't fail the agent if logging fails
            print(f"Warning: Failed to save prompt logs: {e}")

