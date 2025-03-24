---
title: User Chat Mode
weight: 1
---


User chat mode is the default interaction mode once ESBMC-AI is started. The user can enter prompts, that the LLM will attempt to answer. During initialization, the LLM is informed of the source code, the ESBMC output, and given instructions to answer questions from the user. The user can also enter chat commands to switch modes of operation.

The following is a normal question that can be asked:

> Can you simplify the explanation you gave for the bug?

The prompt message will be sent to the LLM and a response will be returned, in a messaging styled user experience. To invoke a command, the `/` character can be used. The following will invoke the `fix-code` command.

> `/fix-code`

Once the `fix-code` command is executed, and a solution is found, the user chat mode LLM will be informed of the solution using the message bus system, the LLM can then be asked questions about the solution.

# Command Structure

When a command is invoked, the parser will split the command based on the following rules:

1. The prompt is split by spaces.
2. If there's a double quote, the contents of the double quote are not split by spaces, and are left as a whole.
3. If there's a backslash in front of a double quote, then that's an escape character, and so, it is not counted in rule 2.

ChatGPT was used to generate the REGEX:

> \s+(?=(?:[^\\"]*(?:\\.[^\\"]*)*)$)|(?:(?<!\\)".*?(?<!\\)")|(?:\\.)+|\S+

The following explanation for the REGEX was given:

* `\s+`: Matches one or more whitespace characters (spaces, tabs, etc.).
* `(?=(?:[^\\"]*(?:\\.[^\\"]*)*)$)`: Positive lookahead to ensure that the next match is a non-quoted substring. It allows for escaped characters (e.g., \"), as well as nested quotes. The lookahead now includes the end of the line anchor ($).
* `(?:(?<!\\)".*?(?<!\\)")`: Matches a double-quoted substring while excluding escaped quotes. The negative lookbehind (?<!\\) ensures that the quotes are not preceded by a backslash.
* `(?:\\.)+`: Matches one or more escaped characters (e.g., \", \\).
* `|\S+`: Alternation (the pipe symbol |) matches either non-whitespace characters (one or more) when not inside quotes.

Tests are used to ensure that the REGEX works as intended.