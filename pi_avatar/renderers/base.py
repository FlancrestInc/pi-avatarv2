from typing import Protocol

from pi_avatar.config import Config


class Renderer(Protocol):
    def run(self, config: Config) -> None:
        """Consume shared avatar state and display it."""

