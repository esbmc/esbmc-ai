---
title: Configuring ESBMC-AI
type: docs
weight: 3
prev: /docs/usage
next: /docs/commands
---

>[!INFO]
>You can find the default config [here](https://raw.githubusercontent.com/esbmc/esbmc-ai/refs/heads/master/config.toml). You can start configuring ESBMC-AI after this.

The command `esbmc-ai help-config` will list all of the config fields along with help messages that explain what each one does.

>[!NOTICE]
>The `help-config` command does not list the help message of addons currently, this is a limitation.

## Configuration Sources and Precedence

ESBMC-AI accepts configuration from multiple sources with the following precedence (highest to lowest):

**CLI arguments > Environment variables > .env file > TOML config file > Defaults**

This means CLI arguments will override environment variables, which override values in the `.env` file, and so on.

### Setting Nested Configuration Values

Nested configuration fields can be set via environment variables using double underscores (`__`):

```sh
# Set verifier.esbmc.path
export ESBMCAI_VERIFIER__ESBMC__PATH=/usr/bin/esbmc

# Set verifier.esbmc.timeout
export ESBMCAI_VERIFIER__ESBMC__TIMEOUT=30
```

All environment variables must use the `ESBMCAI_` prefix.

## Configuring AI Models

ESBMC-AI supports all LangChain-compatible LLM providers through the universal `init_chat_model` interface. Built-in support includes OpenAI, Anthropic, Ollama, and any provider supported by `langchain-community`.

>[!NOTICE]
>Set a model by specifying its name in the config:
>```toml {filename="config.toml"}
>ai_model = "gpt-4"
>```

### Supported Providers

**Built-in (no extra packages needed):**
- OpenAI: `gpt-4`, `gpt-3.5-turbo`, etc.
- Anthropic: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`, etc.
- Ollama: Custom models via `ai_custom` (see below)

**Additional providers** (require extra packages):
- Google: Install `langchain-google-genai` for Gemini models
- Others: Any LangChain-supported provider with the appropriate package

### API Keys

Set the appropriate environment variable for your provider:

```sh
# OpenAI
export OPENAI_API_KEY="..."

# Anthropic
export ANTHROPIC_API_KEY="..."

# Google Gemini
export GOOGLE_API_KEY="..."
```

### Custom/Self-Hosted Models (Ollama)

For self-hosted models like Ollama, define them in `ai_custom`:

```toml
[ai_custom."llama3.1:70b"]
server_type = "ollama"
url = "localhost:11434"
max_tokens = 128000
```

Then use it:

```toml
ai_model = "llama3.1:70b"
```

### Installing Extra Provider Packages

```sh
# Local installation
pip install langchain-google-genai

# With pipx
pipx inject esbmc-ai langchain-google-genai

# In containers (at build time)
hatch run podman-build "langchain-google-genai"
```
