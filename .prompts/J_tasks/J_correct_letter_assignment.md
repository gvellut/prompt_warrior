src/prompt_warrior/core.py choose_task_stem

When choosing the next stem, do not consider only the top level tasks in the plan.md. Consider all the taks even the subtasks : they can have been created as a top level task then moved by the user as subtask. In that case, the procedure will create the same stem twice (since it cannot see the subtask) 