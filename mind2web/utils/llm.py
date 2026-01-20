import logging
import re
import os
import inspect
import tiktoken

logger = logging.getLogger("main")

import openai
openai.api_key = os.environ["OPENAI_API_KEY"]
from openai import OpenAI, BadRequestError
client = OpenAI()


def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Get embedding from OpenAI."""
    try:
        text = text.replace("\n", " ")
        return client.embeddings.create(input=[text], model=model).data[0].embedding
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        return []


def num_tokens_from_messages(messages, model):
    """Return the number of tokens used by a list of messages.
    Borrowed from https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "GPT-3-5-turbo-chat",
        "GPT-3-5-16k-turbo-chat",
        "gpt-3.5-16k-turbo-chat",
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-3.5-turbo-1106",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        "gpt-4o",
        "gpt-5-mini",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


MAX_TOKENS = {
    "GPT-3-5-turbo-chat": 4097,
    "gpt-3.5-turbo-0301": 4097,
    "gpt-3.5-turbo-0613": 4097,
    "gpt-3.5-turbo-16k-0613": 16385,
    "gpt-3.5-turbo-1106": 16385,
    "gpt-4": 8192,
    "gpt-4-0613": 8192,
    "gpt-4o": 16385,
    "gpt-5-mini": 128000,
    "GPT-3-5-16k-turbo-chat": 16385,
    "gpt-4-32k": 32000,
}

MODELS_WITHOUT_STOP_SUPPORT = {
    "gpt-5-mini",
    "o1-mini",
    "o1-preview",
}


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
        raise ValueError(f"Unknown model: {model}")


# @backoff.on_exception(
#     backoff.constant,
#     (APIError, RateLimitError, APIConnectionError),
#     interval=10,
# )
def generate_response(
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    stop_tokens: list[str] | None = None,
    use_tools: bool = False,
) -> tuple[str, dict[str, int]]:
    """Send a request to the OpenAI API."""

    logger.info(
        f"Send a request to the language model from {inspect.stack()[1].function}"
    )
    gen_kwargs = {}
    if temperature != 0.0:
        gen_kwargs["temperature"] = temperature

    if get_mode(model) == "chat":
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
    else:
        # Proactively remove stop tokens for models that don't support them
        effective_stop = stop_tokens if (stop_tokens and model not in MODELS_WITHOUT_STOP_SUPPORT) else None
        
        prompt = "\n\n".join(m["content"] for m in messages) + "\n\n"
        response = openai.Completion.create(
            prompt=prompt,
            engine=model,
            temperature=temperature,
            stop=effective_stop,
        )
        message = response["choices"][0]["text"]
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
        pattern, response, re.DOTALL
    )  # re.DOTALL makes . match also newlines
    if match:
        extracted_string = match.group(1)
    else:
        # Fallback: if no backticks found, return the trimmed full response
        # to prevent empty pred_action when model fails to follow formatting rules
        extracted_string = response.strip()

    return extracted_string
