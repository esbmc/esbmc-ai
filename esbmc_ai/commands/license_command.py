# Author: Yiannis Charalambous

"""Contains the license command."""

from typing import Any
from typing_extensions import override

from esbmc_ai.chat_command import ChatCommand


class LicenseCommand(ChatCommand):
    """Command that displays license and contribution information for ESBMC-AI."""

    def __init__(self) -> None:
        super().__init__(
            command_name="license",
            help_message="Display license and contribution information.",
        )

    @override
    def execute(self) -> Any:
        print(
            """
╔════════════════════════════════════════════════════════════════╗
║                  ESBMC-AI License Information                  ║
╚════════════════════════════════════════════════════════════════╝

ESBMC-AI is offered under a DUAL-LICENSE model:

📖 Open Source License - AGPL-3.0
    You are free to use, modify, and distribute this software under the GNU 
    Affero General Public License v3.0, provided you:
    • Disclose the source code of your application
    • Distribute under the same AGPL-3.0 license
    • Make source available to all network users

💼 Commercial License

    For projects where the terms of the AGPL-3.0 are not suitable, such as in 
    proprietary or closed-source applications, we offer a separate commercial 
    license.

    Contact: contact@uominnovationfactory.com

📝 Contributing
    All contributions require signing our Contributor License Agreement (CLA) 
    based on the Apache Software Foundation CLA.

For full details:
    • License: https://github.com/esbmc/esbmc-ai/blob/master/LICENSE
    • CLA: https://github.com/esbmc/esbmc-ai/blob/master/CLA.md
    • Wiki: https://esbmc.github.io/esbmc-ai/contributing
"""
        )
