This repository is a Python CLI program that manages prompts for tasks for a LLM. 

The prompts are stored as Markdown (but the format is irrelevant because it is not read by the tool) except as an opaque text.

The prompts are manually managed and passed to the LLM explicitly by the user (it is not a task management tool for autonomous development by the LLM).

There is a table of content of tasks : this links to prompts in Markdown format and has memory of what is being worked on and the order. The tasks can be ordered in a hierarchy.