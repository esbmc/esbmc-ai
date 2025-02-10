# Author: Yiannis Charalambous

from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.verifiers.esbmc import ESBMC


class VerifierRunner:
    """Manages all the verifiers that are used. Can get the appropriate one based
    on the config."""

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(VerifierRunner, cls).__new__(cls)
            cls.instance._init([ESBMC()])
        return cls.instance

    _builtin_verifiers: dict[str, BaseSourceVerifier]
    """Builtin loaded verifiers"""
    _addon_verifiers: dict[str, BaseSourceVerifier] = {}
    """Additional loaded verifiers"""
    _verifier: BaseSourceVerifier
    """Default verifier"""

    def _init(self, builtin_verifiers: list[BaseSourceVerifier]) -> "VerifierRunner":
        self._builtin_verifiers = {v.verifier_name: v for v in builtin_verifiers}
        self._verifier = builtin_verifiers[0]
        return self

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
