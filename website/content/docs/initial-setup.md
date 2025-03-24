---
title: Initial Setup
type: docs
weight: 1
prev: /docs
---

Setting up ESBMC-AI is easy, you can install it following these steps:

{{% steps %}}

### Install Package

```sh
pip install esbmc-ai
```

Alternatively, PipX can be used to install in an isolated environment:

```sh
pipx install esbmc-ai
```

Now, ESBMC-AI can be invoked with the following command:

```sh
esbmc-ai ...
```

### Setting the Environment Variables

ESBMC-AI expects the following environment variables to be set:

* `ESBMCAI_CONFIG_PATH` - Points to the config file that ESBMC-AI requires to run.
* `OPENAI_API_KEY` - Assuming you want to use OpenAI servers.

By default the envoronment variables are searched in the following locations in the order presented:

1. Exported env vars ie. `export ESBMCAI_CONFIG_PATH="~/.config/esbmc-ai.toml"`
2. `.env` file in the current directory, moving upwards in the directory tree.
3. `esbmc-ai.env` file in the current directory, moving upwards in the directory tree.
4. `esbmc-ai.env` file in `$HOME/.config/` for Linux/macOS and `%userprofile%` for Windows.

If none are found, or they don't contain the variables required, an error will be thrown.

### Creating the Config

Create a TOML file: `esbmc-ai.toml` and save it in a desiarable location. You can save it to `$HOME/.config/` for Linux/macOS and `%userprofile%` for Windows.

ESBMC-AI provides the following command which allows you to view all the editable config fields:

```sh
esbmc-ai help-config
```

You can add those fields and their desired values in the config file.

>[!NOTICE]
>A sample config file can be found [here](https://github.com/esbmc/esbmc-ai/blob/master/config.toml). Keep in mind that it might not work without configuring and it should be used as a template to create your own config file.

### Set Environment Variables

Upon running ESBMC-AI you will notice it gives you warning that some environment variables need to be set. The default location that the config 

```bash
export ESBMCAI_CONFIG_PATH="..."
export OPENAI_API_KEY="..." # If you want to use an OpenAI model
```

### Install a Verifier

ESBMC-AI supports multiple verifiers. There is a built-in verifier, ESBMC. ESBMC-AI does not come with the original ESBMC binary. In order to use ESBMC-AI you must download ESBMC. Download the [ESBMC](http://esbmc.org/) executable or build from [source](https://github.com/esbmc/esbmc).

{{% /steps %}}
