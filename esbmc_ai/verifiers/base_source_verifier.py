# Author: Yiannis Charalambous

"""This module holds the code for the base source code verifier."""

from pathlib import Path
import re
from typing import Any, override
from hashlib import sha512
import pickle

from platformdirs import user_cache_dir

from esbmc_ai.__about__ import __version__ as esbmc_ai_version
from esbmc_ai.base_component import BaseComponent
from esbmc_ai.log_utils import LogCategories
from esbmc_ai.solution import Solution
from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.program_trace import ProgramTrace


class SourceCodeParseError(Exception):
    """Error that means that SolutionGenerator could not parse the source code
    to return the right format."""


class VerifierTimedOutException(Exception):
    """Error that means that ESBMC timed out and so the error could not be
    determined."""


class BaseSourceVerifier(BaseComponent):
    """The base class for creating a source verifier for ESBMC-AI. In order for
    this class to work with ESBMC-AI, the constructor must have default values
    to all arguments because it will be invoked without passing anything.

    Loading from the config will be permitted but it would be preferred if you
    use the base class method `get_config_value`. The fields of the config that
    are going to be loaded need to be declared and returned by the
    `get_config_fields` method. The config loader will automatically preppend
    the verifier_name declared to each key so that there are no clashes in the
    config. So the verifier "esbmc" will have for key "timeout" the following
    field in the config: "esbmc.timeout"."""

    @override
    @classmethod
    def create(cls) -> "BaseComponent":
        obj: BaseComponent = super().create()
        obj._logger = obj.logger.bind(category=LogCategories.VERIFIER)
        return obj

    def __init__(self, verifier_name: str, authors: str) -> None:
        """Verifier name needs to be a valid TOML key."""
        super().__init__()
        self._name = verifier_name
        self._authors = authors

    @property
    def verifier_name(self) -> str:
        """Alias for name"""
        return self.name

    def _cache_name_pack(self, properties: Any) -> Any:
        """Packs additional version properties to the cache name in order to ensure
        it only functions in the current version of ESBMC-AI."""
        return [esbmc_ai_version, properties]

    def _save_cached(self, properties: Any, result: Any) -> None:
        """Saves the verification results to a cached directory to be loaded
        later. Properties are going to be hashed to form the name of the file,
        they should be anything that defines the file."""
        properties = self._cache_name_pack(properties)
        data_dump: bytes = pickle.dumps(obj=properties, protocol=-1)
        file_id: str = str(sha512(data_dump).hexdigest())
        self.logger.info("Saving result to cache")
        self.logger.info(f"Cache ID: {file_id}")

        cache: Path = Path(user_cache_dir("esbmc-ai", "Yiannis Charalambous"))
        cache.mkdir(parents=True, exist_ok=True)
        with open(cache / file_id, "wb") as file:
            pickle.dump(obj=result, file=file, protocol=-1)

    def _load_cached(self, properties: Any) -> Any:
        """Loads the verification results from a cached directory."""
        properties = self._cache_name_pack(properties)
        data_dump: bytes = pickle.dumps(obj=properties, protocol=-1)
        file_id: str = str(sha512(data_dump).hexdigest())
        self.logger.info(f"Searching cache ID: {file_id}")

        cache: Path = Path(user_cache_dir("esbmc-ai", "Yiannis Charalambous"))
        filename: Path = cache / file_id
        if cache.exists() and filename.exists() and filename.is_file():
            with open(filename, "rb") as file:
                data: bytes = pickle.load(file=file)
                self.logger.info("Using cached result")
                return data

        self.logger.info("Cache not found...")
        return None

    def verify_source(
        self,
        *,
        solution: Solution,
    ) -> VerifierOutput:
        """Verifies source_file."""
        _ = solution
        raise NotImplementedError()
