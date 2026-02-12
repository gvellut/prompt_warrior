- Write a plan to a PLAN.md at the root of the repo
- Make it coherent : highlight if you had to guess things from the spec
- Write  the small "30 -second workflow" in README to explain the list of commands in order in a typical session. : so I can check we are on the same page

- The cli is managed with click (already installed in venv)
- The cli main  file is in src/prompt_warrior/__main__.py
- This will have to work on macos so if there is some system specific thing : do it for macos only. but try to abstract the syustem-specific code so could implement for other systems later and make the correct call.
- use param -d on the top command for setting up debug mode (that os the logger.debug are output)
- All the options can also be set with env var with prefix PWAR_. Set the env var name for the commands explicitly. Infer then from the param name.
- write a special click command class for all the commands (NOT groups) so that an error is caught and its message printed in red. With debug enabled : also print the stack
- do not use emoji in the output texts
- for the output : use rich (already installed) and colors (eg red for errors). rich_theme = rich.theme.Theme(
    {
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "highlight": "magenta",
        "important": "bold",
    }
)
- add the defaults referred below as constants at the top of the file : so can be easily modified.
- for simple enough class (most of them probalby), you can use attrs @define (already installed)
- for groups of constant : use an enum with auto() for the values and upper case  names If they are one-off : a  variable  in upper case is fine.

- Update the README.md with short explaination of each command + a small "30 -second workflow" to explain the list of commands in order in a typical session.

- add support for autocompletion. Explain in the README how to set it up (with bash and zsh)

- setup common reused options for options / arguments that can be used in multiple settings
- add some help text to the arguments

- the work.md and the status can be updated by the user, outside the commands. So make sure some verification is done (if incoherent) and be tolerant of such edition (if no consequence for the logic), as well as preserve the formatting (for example, the order of lines, newlines, spaces). Be forgiving for the tabulation : they can vary depending on the task : but if incoherent below a single task (multiple tabulation levels between the first and the other), make it an error with sufficient details for the user to correct.

The CLI has a number of subcommands :

- init : this will create a ".prompts" folder (default). 
    - It will also create a work.md file:
    - by default will create a task. The task will be referred to in the work.md by adding a "- [](path to initialization markdown file) Initialization" to the top of the file + newline (\n)
        - the creation of the intial task file can be disabled with --no-init flag
        - the text + name of the initial task can be set with "--init-task" with a value : the valus passed is used for the file name and for the label
        - The name of the md for the initialization is create with a prefix as explained below
    - error if the .prompts folder already exists with error.

- add : this will create a new md inside the .prompts folder. It will also create a new line in the work.md file
    - an argument can be passed : ef "... add Read spec documents later" : no need for surrounding the arg with "" : ie single argument passed. Isntead multiple is fine and all the arguments will be used and concatenated together (with space)
    - the name will be created with a prefix as explained below. the name after the prefix  will be derived from the label by taking the first x characters (make it a constant) + make it safe ASCII (but transforming the accents eg é to e ) + spaces as _. Make that a separate function.
    - the file name can be overriden with param --label/-l (will transform passed value to safe ASCII like explained above) or --raw-label/-r (used as is)
    - the task will be added to work.md as "- [](path to label markdown file) Label" following the last iten with "-" bullet point 
    - the task can be added at the top by passing the --top/-t  flag
    - --sub/-s param : this will create a new md inside the .prompts folder + add a line at the end of the children list for the parent task. Use the "-" bullet
        - it will take as value a reference to the parent task
        - make sure the parent task can be autocompleted : after the autocomplete : the full markdown file name is passed
        - error if the parent task does not exist
    - --corr/-c : this will create a new md inside the .prompts folder. Use the "?" bullet
        - it is a flag 
        - it will be like the sub : except it targets the active task (with a * bullet type : the one with the most depth) and adds a "?" bullet as a child. 
    - --agent/-a : sams as --corr : but with the "~" bullet

- done: this closes the currently active task (the one with the most depth) and mark it as done with a ! bullet.
    - if flag --recursive / -r is passed :  If all its sibling are done : also mark the parent as done, and so on.
    - move the done task and its children if there are any to the bottom of its list (if toplevel, the bottom of the file, if a subtask : below its siblings)

- next : this updates the first line that has a - or ? bullet type below the currently active task (if has children) or the first - or ? task in the top level (if no children)
    - it makes the selected task active with "*" bullet
    - if a parent task is active : this will make active the first - or ? task below it
    - error if there is already an active task at the current level : need to call done first
    - error if all are done (eg modified by the user): need to call done first to close the parent first
    - it will also copy the content of the task (Markdown file) to the copy buffer.

    - exmaple : so if parent is * : and one of its child is * : first call done : mark the child as !. Call next : mark the next child as *. If no other child : error. But call done : mark the parent as !


- delete : one argument : a reference to a task.
    - confirmation if task is active or has children (indicate number of children)
    - this will remove the task from the work.md + remove the MD file for the task + all its children
    - option --keep-children : to move its children as the same level as the task i nthe work.md and keep their files around


    

- display a warning  if the * invariant is broken : that is there are multiple * at one level or the * at different levels are not in a parent-descendant relation.


A task can referred to  either the full markdown file name (without md) or just the prefix or an index number : the 0-based position of the task inside the work.md (only the planned tasks ie -)

The tasks in the work.md can have multiple types of bullet point 
- "-" is the default : means task that is planned
- "*" task that is being worked on : only one inside a level (list of top parent tasks or the children of the active task or ... so on). So a task can be worked on and one of its children can be worked on. Unless it is modified by the user (and this will display a warning when a command is run) : all the active tasks are in a hierarchy.
- "?" correction task
- "!" : task that is done
- "~" : a agent response (to be ignored)

They can be interleaved in the file but the commands will try to make them in order : * as the first, - follow, the ! at the end. For example, when adding a task : it will be added after the last - (but there can be ! after)

For sub tasks : the new task line will be created below a task with a tabulation ie 4 spaces (add as constant). There can only be arbitrary levels.

The task md files are create with a prefix : It will start with a capital letter, in order. When all the capital letters are used (or if a Z_ if found : since the files can be renamed : there can be a Z_ withouth the intermediate). it will add a letter (in this order Aa, , Ca ... then Za, Ab). Finally, a number (1 to 9 ie Aa9)
A _ separates the prefix and the name (ASCII).
This prefix + label is the one generated by the commands : but they can be renamed by the user or even moved to another folder (they have no semantic significance). 
For the subtasks : it is the same : a "." is added after the parent task prefix and followed by capital letter, then small case letter then number. So we have a link to the parent with that (but this is just the default : can be renamed by the user)