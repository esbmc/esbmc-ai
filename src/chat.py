# Author: Yiannis Charalambous 2023

import openai
from tiktoken import get_encoding, encoding_for_model

# SYSTEM_MSG = [
#     {
#         "role": "system",
#         "content": "You are a helpful assistant. If you understand, reply OK",
#     },
#     {"role": "assistant", "content": "OK"},
# ]

SYSTEM_MSG_DEFAULT = [
    {
        "role": "system",
        "content": "You are an security focused assistant that parses output from a program called ESBMC and explains the output to the user. ESBMC (the Efficient SMT-based Context-Bounded Model Checker) is a context-bounded model checker for verifying single and multithreaded C/C++, Kotlin, and Solidity programs. It can automatically verify both predefined safety properties (e.g., bounds check, pointer safety, overflow) and user-defined program assertions. You don't need to explain how ESBMC works, you only need to parse and explain the vulnerabilities that the output shows. For each line of code explained, say what the line number is as well. Do not answer any questions outside of these explicit parameters. If you understand, reply OK.",
    },
    {"role": "assistant", "content": "OK"},
]

MAX_TOKENS_GPT3TURBO: int = 4096


def num_tokens_from_messages(messages, model="gpt-3.5-turbo"):
    """Returns the number of tokens used by a list of messages.
    Source: https://platform.openai.com/docs/guides/chat/introduction"""
    try:
        encoding = encoding_for_model(model)
    except KeyError:
        encoding = get_encoding("cl100k_base")
    # note: future models may deviate from this
    if model.startswith("gpt-3.5-turbo") or model.startswith("gpt-4"):
        num_tokens = 0
        for message in messages:
            # every message follows <im_start>{role/name}\n{content}<im_end>\n
            num_tokens += 4
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                # if there's a name, the role is omitted
                if key == "name":
                    # role is always required and always 1 token
                    num_tokens += -1
        # every reply is primed with <im_start>assistant
        num_tokens += 2
        return num_tokens
    else:
        # See https://github.com/openai/openai-python/blob/main/chatml.md for
        # information on how messages are converted to tokens.
        raise NotImplementedError(
            f"num_tokens_from_messages() is not presently implemented for model {model}."
        )


class ChatInterface(object):
    max_tokens = MAX_TOKENS_GPT3TURBO

    system_messages: list
    messages: list
    model_name: str
    temperature: float

    def __init__(
        self,
        system_messages: list = SYSTEM_MSG_DEFAULT,
        model: str = "gpt-3.5-turbo",
        temperature: float = 1.0,
    ) -> None:
        super().__init__()
        self.system_messages = system_messages
        self.messages = self.system_messages
        self.model_name = model
        self.temperature = temperature

    def push_to_message_stack(self, role: str, message: str) -> None:
        self.messages.append({"role": role, "content": message})

    def send_message(self, message: str) -> str:
        self.push_to_message_stack("user", message)

        # Check if necessary to shorten.
        msg_tokens: int = num_tokens_from_messages(self.messages, self.model_name)
        if msg_tokens > self.max_tokens:
            print("Max tokens reached... Exiting...")
            exit(2)

        completion = openai.ChatCompletion.create(
            model=self.model_name,
            messages=self.messages,
            temperature=self.temperature,
        )

        response_role = completion.choices[0].message.role
        response_message = completion.choices[0].message.content
        self.push_to_message_stack(response_role, response_message)

        return completion
