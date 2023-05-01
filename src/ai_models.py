AI_MODEL_GPT3 = "gpt-3.5-turbo"
AI_MODEL_GPT4 = "gpt-4"


def is_valid_ai_model(name: str) -> bool:
    return name == AI_MODEL_GPT3 or name == AI_MODEL_GPT4
