import logging
import json
import os
from .llm import generate_response, extract_from_response

logger = logging.getLogger("main")

class MemoryDistiller:
    def __init__(self, model_name: str = "gpt-5-mini", prompt_dir: str = "prompt/reasoning_bank"):
        self.model_name = model_name
        self.prompt_dir = prompt_dir
        self.system_prompt_template = self._load_prompt("distill_system.txt")
        self.user_prompt_template = self._load_prompt("distill_user.txt")
        self.success_step_prompt_template = self._load_prompt("success_step.txt")
        self.failure_step_prompt_template = self._load_prompt("failure_step.txt")

    def _load_prompt(self, filename: str) -> str:
        """Load prompt template from file."""
        path = os.path.join(self.prompt_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {path}")
            return ""

    def distill(self, task: str, trajectory: str, outcome: str, domain: str = "", prompt_type: str = "default") -> list[dict]:
        """
        Extracts generalized reasoning strategies (memory items) from a trajectory.

        Args:
            task: The user's task description.
            trajectory: A string representation of the agent's actions and observations.
            outcome: "SUCCESS" or "FAILURE".
            domain: The website domain.
            prompt_type: "default" (task-level), "success" (successful steps), or "failure" (failed steps).

        Returns:
            A list of dicts, each containing {"title": ..., "description": ..., "content": ...}
        """

        # Select appropriate prompt template based on prompt_type
        if prompt_type == "success":
            if not self.success_step_prompt_template:
                logger.error("Success step prompt not loaded. Skipping distillation.")
                return []
            user_prompt = self.success_step_prompt_template.format(
                task=task,
                domain=domain,
                trajectory=trajectory
            )
        elif prompt_type == "failure":
            if not self.failure_step_prompt_template:
                logger.error("Failure step prompt not loaded. Skipping distillation.")
                return []
            user_prompt = self.failure_step_prompt_template.format(
                task=task,
                domain=domain,
                trajectory=trajectory
            )
        else:  # default (task-level)
            if not self.system_prompt_template or not self.user_prompt_template:
                logger.error("Prompts not loaded correctly. Skipping distillation.")
                return []
            user_prompt = self.user_prompt_template.format(
                task=task,
                domain=domain,
                outcome=outcome,
                trajectory=trajectory
            )

        messages = [
            {"role": "system", "content": self.system_prompt_template},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # We don't use stop tokens here as we want the full JSON
            response, _ = generate_response(messages, self.model_name, temperature=0.0)
            
            # Extract JSON from response (handle potential markdown blocks)
            json_str = extract_from_response(response, "```")
            if not json_str:
                json_str = response # Fallback if no code blocks

            # Clean up potentially messy JSON string
            json_str = json_str.strip()
            if json_str.startswith("json"): json_str = json_str[4:]
            
            memory_items = json.loads(json_str)
            
            # Validate structure
            valid_items = []
            if isinstance(memory_items, list):
                for item in memory_items:
                    if all(k in item for k in ["title", "description", "content"]):
                        valid_items.append(item)
            
            return valid_items

        except Exception as e:
            logger.error(f"Failed to distill memory: {e}")
            return []
