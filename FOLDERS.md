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
- Folder name = prefix of the alphabetically first task in the bucket.
- If that first task has no standard prefix, use the first later task in the same bucket that has one.
- Use `0001_tasks`, `0002_tasks`, ... only if no task in the bucket has a standard prefix.
