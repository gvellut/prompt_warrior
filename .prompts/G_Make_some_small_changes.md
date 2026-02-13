- done / commit : 
    - if not recursive : log remaining tasks in level ;  indicate the level + if no remaining task (only the relevant) or the number of remaining tasks (in the same level as the one closed)
    - if recursive : log the number of taks closed (like now) + indicate the level for the shallowest level reached in the closing + if no remaining taks at that level or number of remaining tasks at that level
Do not log if recursive or not (the user will know) 
For the term used for the level : Use "Top level" for level 0 (the one with no tabulation ie with no task --sub), Then "Sublevel 1" for level 1, "Sublevel 2" for level 2 and so on

- correction : keep ? with * and ! (prefix) : they should appear as *? and !? (so first the bullet type used now, followed by the ?, if the original task was ?).
Make sure to also change the filtering (for relevant issues), on top of the updating.

- change script name to pwr. Do not change the module name (prompt_warrior). Update the Autocomplete doc for zsh in README

- Implement the ClipboardProvider for Windows and Linux too.

- change __battle.md name to __plan.md 
Also update the README