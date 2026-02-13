You have made : 
def register(cli: click.Group) -> None:
    @cli.command(
        cls=RichErrorCommand, help="Create a new task and add it to battle.md."
    )
    @pass_app_context
    def add(

Do not do that. Keep the function / command at the top level. Instead, import the commands and do cli.add_command in register_command
In src/prompt_warrior/commands/__init__.py, define a __all__