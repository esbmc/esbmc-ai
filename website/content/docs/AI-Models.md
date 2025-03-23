---
title: AI Models
type: docs
prev: /
next: docs/folder/
---

# Introduction

Various different LLMs are supported by ESBMC-AI. The built-in models consist of all the OpenAI models, and [Ollama](https://ollama.com) models. The OpenAI models are dynamically resolved from a few base models that are specified. The Ollama models are defined through the config, this allows for self-hosted large language models to be seamlessly loaded into ESBMC-AI.

# Built-In LLMs

The following section describes the built-in models that are shipped with ESBMC-AI.

## OpenAI

The following models require the `OPENAI_API_KEY` environment variable to be set.

* `gpt-3.5-turbo`
* `gpt-3.5-turbo-16k`
* `gpt-4`
* `gpt-4-32k`
* You can specify any subtypes such as `gpt-3.5-turbo-0125` and the details will be inherited from `gpt-3.5-turbo`. _If a model is not supported and an error is given, please file an issue on GitHub_.

# Custom LLM

ESBMC-AI has support of custom AI. The config supports adding custom AI models that are self-hosted or from a custom source. These are specified in config.json inside the `ai_custom` field. The `ai_model` field selects which AI model to use. If the AI model chosen does not exist in the built in list of models, then the list inside `ai_custom` will be checked. This means that when adding a `custom_ai` entry, all the entries inside `ai_custom` must be unique and not match any of the built-in first class AI. **The name of the AI will be the entry name**. The entry takes the following fields:

* The `server_type`, currently only `ollama` is supported so every entry should have this key/value pair. However, in the future, as more server types are added, this field will be used to determine what server to use.
* The `max_tokens` are the acceptable max tokens that the AI can accept.
* The `url` is the server URL and port where the LLM server is hosted in.

### Example

```json
"ai_model": "mixtral:8x22b",
"ai_custom": {
	"llama3.1:70b": {
	"server_type": "ollama",
	"url": "localhost:11434",
	"max_tokens": 128000
	},
	"falcon2:11b": {
	"server_type": "ollama",
	"url": "localhost:11434",
	"max_tokens": 8192
	},
	"mixtral:8x22b": {
	"server_type": "ollama",
	"url": "localhost:11434",
	"max_tokens": 64000
}
```
