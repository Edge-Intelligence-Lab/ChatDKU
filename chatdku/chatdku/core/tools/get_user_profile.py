import dspy
from chatdku.core.dspy_classes.user_profiler import get_user_profile

class ProfileRetriever(dspy.Module):
    def __init__(self, profile_path: str, encoding: str = "utf-8"):
        super().__init__()
        self.profile_path = profile_path
        self.encoding = encoding

    def forward(self, **kwargs):
        # Optionally accept profile_path/encoding from kwargs for flexibility
        profile_path = kwargs.get("profile_path", self.profile_path)
        encoding = kwargs.get("encoding", self.encoding)
        return {"user_profile": get_user_profile(profile_path, encoding=encoding)}
