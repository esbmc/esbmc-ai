# Author: Yiannis Charalambous

from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.singleton import SingletonMeta


class VerifierRunner(metaclass=SingletonMeta):
    """Manages all the verifiers that are used. Can get the appropriate one based
    on the config."""

    def __init__(self):
        super().__init__()
        self._verifiers: dict[str, BaseSourceVerifier] = {}
        self._verifier: BaseSourceVerifier | None = None

    @property
    def verfifier(self) -> BaseSourceVerifier:
        """Returns the verifier that is selected."""
        assert self._verifier, "Verifier is not set..."
        return self._verifier

    @verfifier.setter
    def verifier(self, value: BaseSourceVerifier) -> None:
        assert (
            value not in self._verifiers
        ), f"Unregistered verifier set: {value.verifier_name}"
        self._verifier = value

    def add_verifier(self, verifier: BaseSourceVerifier) -> None:
        """Adds a verifier."""
        self._verifiers[verifier.name] = verifier

    def set_verifier_by_name(self, value: str) -> None:
        self.verifier = self._verifiers[value]
