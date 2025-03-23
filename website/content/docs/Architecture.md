---
title: Architecture
type: docs
weight: 1
prev: /docs
next: Initial-Setup
---

ESBMC-AI is composed of multiple parts, ESBMC-AI is composed of __User Chat Mode__ and __Solution Generation Mode__ (activated by the `fix-code` command) [1]. Each component of ESBMC-AI interacts with ESBMC and the LLM separately and contains its own message history, system message, and initial message to accomplish its requirements [1].

The following figure showcases the design of ESBMC-AI, each system interacts separately with the AI model and contains its own message history, system message, and initial message to accomplish its requirements [1]. While some details are omitted, the diagram shows the essential interactions between each system [1]. Interactions labelled with "__A__" belong to __User Chat Mode__, and interactions labelled with "__B__" belong to __Solution Generation Mode__ [1].


![ESBMC-AI Overview](https://github.com/Yiannis128/esbmc-ai/assets/9535618/8b8168d4-42ef-483e-b203-1a1e8e7d6481)

#### User Chat Mode

In this mode, the AI model answers basic natural language prompt questions to the user queries. The initial setup and workflow are as follows:

* (A1) The source code is checked with ESBMC, if no counterexample is provided, then the program exits, as that means that the verification succeeded. In the case of a counterexample, the ESBMC output is stored for use in later stages [1].

* (A2) ESBMC-AI constructs system messages that describe its functionality [1]. The source code and ESBMC response, along with automated responses to each, are injected into the conversation stack [1]. The automated responses always force the AI model to acknowledge its functionality, the source code, and the ESBMC output [1]. The aforementioned message stack constructed will be used for the user chat mode interactions with the LLM [1].

* (A3) The initial prompt is sent to the AI engine, along with the preconfigured message stack, asking for an initial explanation of the source code, and reason for the security vulnerability using the ESBMC output for context [1]. The initial prompt's response is displayed to the user. At this point, the user can further prompt the AI model for any question desired, or invoke commands such as `fix-code` [1].

#### Solution Generation Mode

This mode of ESBMC-AI is triggered using the `fix-code` user chat mode command [1]. Once this mode is invoked, the AI model will be queried with a different message stack by changing the system and initial messages; as seen in the figure above, which shows the interactions between the _Solution Generation Mode_, and all other components of ESBMC-AI system [1]. As solution generation mode is used within the context of the `fix-code` command, the message stack is recreated at every invocation of the command [1]. The workflow of the command is as follows:

* (B) The `fix-code` command is invoked, so the control changes from _(A) User Chat Mode_ to _(B) Solution Generation Mode_ [1].
* (B1) The source code of the program, along with the ESBMC output, is supplied to the AI engine. The AI engine is tasked with creating a solution such that the verification counterexample would be fixed. The source code is extracted from the response [1].
* (B2) The source code solution is presented to ESBMC and then the fix code command verifies that there is no counterexample provided, in which case the solution is found [1]. If a counterexample is returned by ESBMC, then it is appended to the message stack of the solution generation mode, finally the AI model is asked to generate a solution once more [1]. The process will then repeat until a solution is found, or the maximum number of tries is reached [1].

# References

* [1] [arXiv:2305.14752](https://arxiv.org/abs/2305.14752) [[PDF](https://arxiv.org/pdf/2305.14752), [other](https://arxiv.org/format/2305.14752)]