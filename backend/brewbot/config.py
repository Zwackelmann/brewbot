import yaml

CONFIG_PATH = 'conf/config.yaml'


def load_config(path=CONFIG_PATH):
    with open(path) as f:
        return yaml.safe_load(f)
