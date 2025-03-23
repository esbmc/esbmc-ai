---
title: Initial Setup
type: docs
prev: Architecture
weight: 2
# next: Configuration
---

# Introduction

There are two main ways to set up ESBMC-AI, via PyPi as a package, or through source code.



# Setup PyPi

Make sure PyPi is installed on your system:

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

ESBMC-AI is now installed on your system, however, it requires additional components to be setup. Follow the instructions in [Additional Setup](#additional-setup) to complete the setup process.

# Setup Source Code (For Development & Use)

The following steps detail how to set up ESBMC-AI from the source code. After going into the project root folder, the following steps should be followed:

1. Install required Python modules:

```sh
pip install -dr requirements.txt
```
Alternatively, use `pipenv` to install into an environment.

```sh
pipenv shell
pipenv lock -d
pipenv sync -d
```

The following script can be used to launch ESBMC-AI:

```sh
./esbmc-ai
```

## Building Dist Package

Now that the project has been set up. You can install using the build script to generate the files:

```sh
./build.sh
```

Then run `pip install ./dist/<wheel-file-name>`. Alternatively, you can directly run ESBMC-AI from the project instead of installing it, by calling the script `./esbmc-ai`, however, this may yield unexpected behavior if called from a different directory. For non-development usage, it is recommended to install.

**ESBMC-AI is now on your system, however, it requires additional components to be setup. Follow the instructions in [Additional Setup](#additional-setup) to complete the setup process.**

# Additional Setup

* **ESBMC:** ESBMC-AI does not come with the original ESBMC software. In order to use ESBMC-AI you must download ESBMC. Download the [ESBMC](http://esbmc.org/) executable or build from [source](https://github.com/esbmc/esbmc). The location of ESBMC can be customized through the config JSON, however, the default location will be `~/.local/bin` on Linux and macOS, **on Windows it needs to be set explicitly**.

* **Configure ESBMC-AI:** The environment variables need to now be setup that ESBMC-AI uses, along with the JSON config. The details can be accessed in the [Configuration Wiki Page](https://github.com/Yiannis128/esbmc-ai/wiki/Configuration).

# Usage

ESBMC-AI can be invoked from the command-line, it only requires providing a `filename` to a source code file. Arguments provided are position dependent to the `filename` argument. Arguments before the `filename` will be handled by ESBMC-AI, while arguments after will be used by the backend ESBMC. The diagram below visualizes the layout:

![Visualization of the layout](<assets/images/Command line guide.png>)

## Basic Execution

ESBMC-AI can be used to scan a file with default parameters like this:

```bash
esbmc-ai /path/to/source_code.c
```

The execution of the program can be configured from the `config.json`.

## ESBMC-AI Parameters

As mentioned above, any parameters before the filename will be processed and consumed by ESBMC-AI. So in this case `-v` will be consumed by ESBMC-AI, and ESBMC will not get any
arguments.

```bash
esbmc-ai -v /path/to/source_code.c
```

## ESBMC Parameters

Any parameters after the filename will be invoked by the backend ESBMC, they will have no effect on ESBMC-AI.

```bash
esbmc-ai /path/to/source_code.c --nan-check
```

## View Help

Basic help menu can be accessed with the `-h` or `--help` parameter.

```bash
./esbmc-ai -h
```

### In-Chat Commands Help

Type the following command when inside the chat to view the in-chat commands:

```
/help
```

Alternatively, they can be viewed by executing the following command from the command-line:

```bash
esbmc-ai -c help
```

## ESBMC Useful Arguments

Below are some very useful arguments that can be passed to ESBMC, they have been taken from ESBMC's help command:

```
Property checking:
  --compact-trace                  add trace information to output
  --no-assertions                  ignore assertions
  --no-bounds-check                do not do array bounds check
  --no-div-by-zero-check           do not do division by zero check
  --no-pointer-check               do not do pointer check
  --no-align-check                 do not check pointer alignment
  --no-pointer-relation-check      do not check pointer relations
  --no-unlimited-scanf-check       do not do overflow check for scanf/fscanf
                                   with unlimited character width.
  --nan-check                      check floating-point for NaN
  --memory-leak-check              enable memory leak check
  --overflow-check                 enable arithmetic over- and underflow check
  --ub-shift-check                 enable undefined behaviour check on shift
                                   operations
  --struct-fields-check            enable over-sized read checks for struct
                                   fields
  --deadlock-check                 enable global and local deadlock check with
                                   mutex
  --data-races-check               enable data races check
  --lock-order-check               enable for lock acquisition ordering check
  --atomicity-check                enable atomicity check at visible
                                   assignments
  --stack-limit bits (=-1)         check if stack limit is respected
  --error-label label              check if label is unreachable
  --force-malloc-success           do not check for malloc/new failure
```
