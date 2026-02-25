Add folders : when use add (by itself or with --corr or --sub) : put the new tasks in a folder. Either existing or a new folder (if previous already filled see Param Max Folder Tasks). Exception : Make child tasks in same folder as the (direct) parent (as determined by the folder for the md link in __plan.md : so if edited to non standard folder the child will still be in the same non standard folder).
Generate standard folder names : when creating a new folder : use "<prefix>_tasks" with the prefix being the prefix of the new task.
Param Max Folder Tasks for folder :  to indicate the max tasks in a folder (akthough subtasks / corrr tasks can make the count higher than that value). 0 for no folder (next to .prompts). By default : will be 12.
Param Folder Name : (multiple levels possible).  Will create a folder with that name and will disregard the rule for naming new folders and use the passed value. If already exists the new tasks are put inside.

Add "clean-to-folders" subcommand (sub to main group) for current Tasks : will move the current tasks (directly below .prompts) to subfolders  Same rule as above for for child tasks + same generation of folder names. Take the prefix of the first task in a newly created folder as the prefix for the folder name (If the first does not have one : take the prefix of one of the next tasks in the folder : if none has a prefix use 000x_tasks with x incremented as a nunmber as needed : the user will fix it if he wants)


# Folders (short)

Source prompts:
- `.prompts/K_Folders.md`
- `.prompts/K.A_Clean_take_first_folder.md`

Rules:
- `add` and `clean-to-folders` use the same folder rules.
- `Max Folder Tasks` counts all tasks in a folder (including child tasks).
- Child tasks stay in the direct parent folder, even if this exceeds the max.
- `clean-to-folders`: children are determined by `__plan.md` layout (all tasks under one top-level task stay together).
- `clean-to-folders`: build folder buckets in alphabetical order (not `__plan.md` order).
- prefix of Folder name = same prefix of the alphabetically first task in the bucket. => name is <prefix>_tasks
- If that first task has no standard prefix, use the first later task in the same bucket that has one.
- Use `0001_tasks`, `0002_tasks`, ... only if no task in the bucket has a standard prefix.

Respect those rules.