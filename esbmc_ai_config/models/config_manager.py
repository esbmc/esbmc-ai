# Author: Yiannis Charalambous


from typing import Optional


from esbmc_ai_config.models.env_config_loader import EnvConfigLoader
from esbmc_ai_config.models.json_config_loader import JsonConfigLoader


class ConfigManager(object):
    env_config: EnvConfigLoader
    json_config: JsonConfigLoader

    def __init__(self) -> None:
        raise NotImplementedError("Cannot instantiate an abstract class.")

    @classmethod
    def init(
        cls, env_path: Optional[str] = None, config_path: Optional[str] = None
    ) -> None:
        cls.load_env(env_path)
        # TODO
        # cls.load_json(config_path)

    @classmethod
    def load_json(cls, file_path: Optional[str] = None) -> None:
        if file_path:
            cls.json_config = JsonConfigLoader(
                file_path=file_path,
                create_missing_fields=True,
            )
        else:
            cls.json_config = JsonConfigLoader(
                create_missing_fields=True,
            )

    @classmethod
    def load_env(cls, file_path: Optional[str] = None) -> None:
        if file_path:
            cls.env_config = EnvConfigLoader(
                file_path,
                create_missing_fields=True,
            )
        else:
            cls.env_config = EnvConfigLoader(
                create_missing_fields=True,
            )
