import logging
import re
import os
import inspect
import tiktoken
from openai import OpenAI, BadRequestError

logger = logging.getLogger("main")
client = OpenAI()

MODELS_WITHOUT_STOP_SUPPORT = {
    "gpt-5-mini",
    "o1-mini",
    "o1-preview",
}

def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Get embedding from OpenAI."""
    try:
        text = text.replace("\n", " ")
        return client.embeddings.create(input=[text], model=model).data[0].embedding
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        return []

def get_mode(model: str) -> str:
    """Check if the model is a chat model."""
    if model in [
        "GPT-3-5-turbo-chat",
        "GPT-3-5-16k-turbo-chat",
        "gpt-3.5-16k-turbo-chat",
        "gpt-3.5-turbo-0301",
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-1106",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        "gpt-4",
        "gpt-4o",
        "gpt-5-mini",
        "gpt-4-32k-0613",
    ]:
        return "chat"
    elif model in [
        "davinci-002",
        "gpt-3.5-turbo-instruct-0914",
    ]:
        return "completion"
    else:
        # Default to chat if unknown, usually safe for modern models
        return "chat"

def generate_response(
    messages: list[dict[str, str]],
    model: str = "gpt-5-mini",
    temperature: float = 0.0,
    stop_tokens: list[str] | None = None,
    use_tools: bool = False,
) -> tuple[str, dict[str, int]]:
    """Send a request to the OpenAI API."""

    # logger.info(
    #     f"Send a request to the language model from {inspect.stack()[1].function}"
    # )
    gen_kwargs = {}
    if temperature != 0.0:
        gen_kwargs["temperature"] = temperature

    # Proactively remove stop tokens for models that don't support them
    effective_stop = stop_tokens if (stop_tokens and model not in MODELS_WITHOUT_STOP_SUPPORT) else None
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stop=effective_stop,
            **gen_kwargs
        )
    except BadRequestError as e:
        if "Unsupported parameter: 'stop'" in str(e) or "'stop' is not supported" in str(e):
            logger.warning(f"Model {model} does not support 'stop' parameter. Retrying without it.")
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                **gen_kwargs
            )
        else:
            raise e
    
    message = response.choices[0].message.content
    
    info = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    if message is None: message = ""

    return message, info

def extract_from_response(response: str, backtick="```") -> str:
    if backtick == "```":
        # Matches anything between ```<optional label>\n and \n```
        pattern = r"```(?:[a-zA-Z]*)\n?(.*?)\n?```"
    elif backtick == "`":
        pattern = r"`(.*?)`"
    else:
        raise ValueError(f"Unknown backtick: {backtick}")
    match = re.search(
        pattern,
        response,
        re.DOTALL
    )  # re.DOTALL makes . match also newlines
    if match:
        extracted_string = match.group(1)
    else:
        # Fallback: if no backticks found, return the trimmed full response
        # to prevent empty pred_action when model fails to follow formatting rules
        extracted_string = response.strip()

    return extracted_string