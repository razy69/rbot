# External modules
import yaml


def get_config(path: str = "./rbot-config.yaml") -> dict:
    """Opens, reads and returns content of yaml rbot config file."""
    with open(path, "r+", encoding="utf-8") as _file:
        return yaml.safe_load(_file)
