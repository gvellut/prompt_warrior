In the next command, add a --branch option and a --branch-command  (both also settable from an envvar)
With --branch option : 
- you will print a branching command in last 
eg
Activated task: Change order
Copied task content from L_Change_order.md
gsw -c L_Change_order
- the last line will use the branch-command : by default it will be gsw -c. If set to other value : use that. Put that command in violet and the argument in green
- on top of the content of the md file, you will do an additional copy (not appended to a single copy) : eg in macos 2 calls to pbcopy : the second copy will be the 'gsw -c L_Change_order' (usable with a copy/paste manager)
