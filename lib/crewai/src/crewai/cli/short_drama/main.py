"""Short drama CLI — crewai short_drama <subcommand>

Top-level `short_drama` click group and entry point.
"""

from __future__ import annotations

import click

from crewai.cli.short_drama.assemble import assemble
from crewai.cli.short_drama.bible import bible
from crewai.cli.short_drama.create import create_short_drama_project
from crewai.cli.short_drama.outline import outline
from crewai.cli.short_drama.run import run
from crewai.cli.short_drama.shots import shots


@click.group(name="short_drama")
@click.version_option(package_name="crewai")
def short_drama():
    """Short drama generation pipeline CLI.

    Subcommands:
        create   Create a new short drama project (optionally from a novel)
        bible    Generate / inspect the short drama bible
        outline  Generate episode outlines from chapters
        shots    Decompose outlines into individual shots
        assemble Assemble shots into final video (via FFmpeg)
        run      Run the full pipeline end-to-end (bible → video → assemble)
    """
    pass


# Register subcommands
short_drama.add_command(create_short_drama_project)
short_drama.add_command(bible)
short_drama.add_command(outline)
short_drama.add_command(shots)
short_drama.add_command(assemble)
short_drama.add_command(run)
