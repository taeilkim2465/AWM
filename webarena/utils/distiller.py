import logging
import json
import os
import re
from .llm import generate_response

logger = logging.getLogger("main")

class MemoryDistiller:
    def __init__(self, model_name: str = "gpt-5-mini", prompt_dir: str = "prompt/reasoning_bank"):
        self.model_name = model_name
        self.prompt_dir = prompt_dir
        # Pre-load prompts if possible, or load on demand. 
        # Since input prompt is common, we can load it here.
        self.input_prompt_template = self._load_prompt("distill_input.txt")
        self.success_system_prompt = self._load_prompt("success_system.txt")
        self.failure_system_prompt = self._load_prompt("failure_system.txt")

    def _load_prompt(self, filename: str) -> str:
        """Load prompt template from file."""
        path = os.path.join(self.prompt_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {path}")
            return ""

    def distill(self, task: str, trajectory: str, outcome: str, domain: str = "") -> list[dict]:
        """
        Extracts generalized reasoning strategies (memory items) from a trajectory.
        
        Args:
            task: The user's task description.
            trajectory: A string representation of the agent's actions and observations.
            outcome: "SUCCESS" or "FAILURE" (case-insensitive).
            domain: The website domain (unused in current prompts but kept for interface compatibility).

        Returns:
            A list of dicts, each containing {"title": ..., "description": ..., "content": ...}
        """
        
        is_success = outcome.strip().upper() == "SUCCESS"
        
        if is_success:
            system_prompt = self.success_system_prompt
        else:
            system_prompt = self.failure_system_prompt
            
        if not system_prompt or not self.input_prompt_template:
            logger.error("Prompts not loaded correctly. Skipping distillation.")
            return []

        # Format input prompt
        # The template expects {task_query} and {trajectory}
        user_prompt = self.input_prompt_template.replace("{task_query}", task).replace("{trajectory}", trajectory)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # We don't use stop tokens here
            response_text, _ = generate_response(messages, self.model_name, temperature=0.0)
            
            # Parse Markdown Response
            # Expected format:
            # # Memory Item <n>
            # ## Title
            # <title>
            # ## Description
            # <desc>
            # ## Content
            # <content>
            
            memory_items = []
            item_blocks = re.split(r'# Memory Item \d+', response_text)
            
            for block in item_blocks:
                if not block.strip():
                    continue
                
                title_match = re.search(r'## Title\s*\n(.*?)\n', block, re.DOTALL)
                desc_match = re.search(r'## Description\s*\n(.*?)\n', block, re.DOTALL)
                content_match = re.search(r'## Content\s*\n(.*)', block, re.DOTALL)
                
                if title_match and desc_match and content_match:
                    title = title_match.group(1).strip()
                    desc = desc_match.group(1).strip()
                    content = content_match.group(1).strip()
                    
                    # Cleanup markdown code blocks if present
                    title = title.replace('`', '')
                    desc = desc.replace('`', '')
                    content = content.replace('```', '')
                    
                    memory_items.append({
                        "title": title,
                        "description": desc,
                        "content": content
                    })
            
            return memory_items

        except Exception as e:
            logger.error(f"Failed to distill memory: {e}")
            return []