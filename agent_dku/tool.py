import dspy


class Tool(dspy.Module):
    def __init__(self, name: str, desc: str, param_specs: dict[str, str]):
        super().__init__()
        self.name = name
        self.desc = desc
        self.param_specs = param_specs

    def to_string(self, indent: str = ""):
        s = ""
        s += indent + f"- Name: {self.name}\n"
        s += indent + f"- Description: {self.desc}\n"
        if self.param_specs:
            s += indent + "- Parameters:\n"
            for j, (pn, pd) in enumerate(self.param_specs.items()):
                s += indent + f"  - Parameter {j}\n"
                s += indent + f"  - Name: {pn}\n"
                s += indent + f"  - Description: {pd}\n"
        return s
