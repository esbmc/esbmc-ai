# Author: Yiannis Charalambous

from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.singleton import SingletonMeta


class VerifierRunner(metaclass=SingletonMeta):
    """Manages all the verifiers that are used. Can get the appropriate one based
    on the config."""

    def __init__(self, builtin_verifiers: list[BaseSourceVerifier] = []):
        super().__init__()
        self._builtin_verifiers: dict[str, BaseSourceVerifier] = {v.verifier_name: v for v in builtin_verifiers}
        self._verifier: BaseSourceVerifier = builtin_verifiers[0]
        _addon_verifiers: dict[str, BaseSourceVerifier] = {}

    @property
    def verfifier(self) -> BaseSourceVerifier:
        """Returns the verifier that is selected."""
        return self._verifier

    @verfifier.setter
    def verifier(self, value: BaseSourceVerifier) -> None:
        assert (
            value not in self.verifiers
        ), f"Unregistered verifier set: {value.verifier_name}"
        self._verifier = value

    @property
    def builtin_verifier_names(self) -> list[str]:
        """Gets the names of the builtin verifiers"""
        return list(self._builtin_verifiers.keys())

    @property
    def verifiers(self) -> dict[str, BaseSourceVerifier]:
        """Gets all verifiers"""
        return self._builtin_verifiers | self._addon_verifiers

    @property
    def addon_verifiers(self) -> dict[str, BaseSourceVerifier]:
        return self._addon_verifiers

    @addon_verifiers.setter
    def addon_verifiers(self, vers: dict[str, BaseSourceVerifier]) -> None:
        self._addon_verifiers = vers

    @property
    def addon_verifier_names(self) -> list[str]:
        """Gets all addon verifier names"""
        return list(self._addon_verifiers.keys())

    def set_verifier_by_name(self, value: str) -> None:
        self.verifier = self.verifiers[value]
