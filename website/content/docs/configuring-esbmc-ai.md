---
title: Configuring ESBMC-AI
type: docs
weight: 2
---

Various different LLMs are supported by ESBMC-AI. The built-in models consist of ~~all~~ most of the OpenAI models. Additional models can be added through the config.

>[!NOTICE]
>Setting a model can be done by entering its name in the following config field:
>```toml {filename="esbmc_ai.toml"}
>ai_model = "gpt-3.5-turbo"
>```

## OpenAI

The OpenAI models are dynamically resolved from a few base models that are specified. Along with their context lengths. You can use any LLM specified in the [OpenAI models list](https://platform.openai.com/docs/models) by entering its name.

>[!WARNING]
>If a model is not supported and an error is given, please file an issue on GitHub.

## Custom AI

The config supports adding custom AI models that are self-hosted or from a custom source. These are specified in the config using the `ai_custom` field. The `ai_model` field selects which AI model to use. If the AI model chosen does not exist in the built in list of models, then the list inside `ai_custom` will be checked. This means that when adding a `custom_ai` entry, all the entries inside `ai_custom` must be unique and not match any of the built-in first class AI. **The name of the AI will be the entry name**. The entry takes the following fields:

* The `server_type`, currently only `ollama` is supported so every entry should have this key/value pair. However, in the future, as more server types are added, this field will be used to determine what server to use.
* The `max_tokens` are the acceptable max tokens that the AI can accept.
* The `url` is the server URL and port where the LLM server is hosted in.

{{% details title="Example" closed="true" %}}

```toml
[ai_custom."llama3.1:70b"]
server_type = "ollama"
url = "localhost:11434"
max_tokens = 128000
```

Then to use this model:

```toml
ai_model = "llama3.1:70b"
```

{{% /details %}}
