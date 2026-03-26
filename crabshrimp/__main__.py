import sys
sys.stdout.reconfigure(line_buffering=True)

from crabshrimp.cli.commands import cli

if __name__ == "__main__":
    cli()
