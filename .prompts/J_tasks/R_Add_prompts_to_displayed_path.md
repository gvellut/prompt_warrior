Wherever  build_task_link_path is used
Add to the coommands a flag + Envvar that makes that is passed to that function and makes it show : the .prompts default prompt dir or (PWAR_PROMPTS_DIR envvar oir top arg) if passed followed by the task path as it is shown now and finish with .md
With that flag --full-path / -f :  J_tasks/R_Add_prompts_to_displayed_path becomes .prompts/ J_tasks/R_Add_prompts_to_displayed_path.md (or sthing different from .prompts if set by user)
