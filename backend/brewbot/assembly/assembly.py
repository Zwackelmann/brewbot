from brewbot.config import AssemblyConfig
from brewbot.util import load_object
from typing import Protocol, Coroutine
from brewbot.can.node_state import NodeState

def from_config(conf: AssemblyConfig):
    cls = load_object(conf.assembly_class)
    return cls(conf.nodes, conf.params)

class Assembly(Protocol):
    name: str

    def coros(self) -> list[Coroutine]:
        ...

def gen_assemblies(assembly_configs: list[AssemblyConfig], node_states: dict[str, NodeState]) -> dict[str, Assembly]:
    assemblies = {}
    for assembly_conf in assembly_configs:
        if assembly_conf.assembly_class is None:
            raise ValueError("assembly class cannot be None")

        assembly_class = load_object(assembly_conf.assembly_class)
        assemblies[assembly_conf.key] = assembly_class.from_config(assembly_conf, node_states)

    return assemblies
