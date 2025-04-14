---
title: Built-in Commands
prev: /docs
---

The following commands are built-in to ESBMC-AI.

* `help`: Print this help message.
* `help-config`: Print information about the config fields.
* `list-models`: Lists all available AI models.
* `exit`: Exit the program (Used by `userchat` command).
* `fix-code`: Generates a solution for this code, and re-evaluates it with ESBMC. Very basic and should only be used for testing/demonstration purposes.
* `userchat`: Allow the user to ask the LLM questions about the vulnerability.Currently only supports 1 file.