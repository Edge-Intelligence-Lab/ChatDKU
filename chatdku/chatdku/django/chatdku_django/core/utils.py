import re

def slugify(name: str) -> str:
    name = name.replace(" ", "-").strip()
    name=name.replace("-","_").strip("_")
    clean_text = re.sub(r'[^a-zA-Z0-9\s_]', '', name)
    return clean_text
