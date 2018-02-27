from IPython.core.magic import register_cell_magic


@register_cell_magic
def infile(args: str, cell):
    args_list = args.split(':')
    if len(args_list) == 2:
        line_count = int(args_list[1])
        newlines = "\n" * (line_count - 1)
    elif len(args_list) == 1:
        newlines = ""
    else:
        raise Exception("usage: %%infile foo.py:5")
    exec(compile(newlines + cell, args_list[0], 'exec'))
