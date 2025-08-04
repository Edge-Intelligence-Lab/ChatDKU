import tomllib
import tomli_w
import subprocess

TOML_PATH = "pyproject.toml"

# Get installed packages from pip freeze
installed = {}
for line in subprocess.check_output(["pip", "freeze"], text=True).splitlines():
    if "@" not in line and "===" not in line:
        try:
            pkg, ver = line.strip().split("==")
            installed[pkg.lower()] = ver
        except ValueError:
            continue

# Read pyproject.toml
with open(TOML_PATH, "rb") as f:
    data = tomllib.load(f)

deps = data["project"]["dependencies"]
updated_deps = []

for dep in deps:
    # Handle inline comments
    comment = ""
    if "#" in dep:
        dep, comment = dep.split("#", 1)
        dep = dep.strip()
        comment = "  # " + comment.strip()

    name_part = dep.split("==")[0].split("~=")[0].strip()
    name_lower = name_part.lower()

    if name_lower in installed:
        updated = f"{name_part}=={installed[name_lower]}{comment}"
        updated_deps.append(updated)
    else:
        # keep original line if not found
        updated_deps.append(f"{dep}{comment}")

data["project"]["dependencies"] = updated_deps

# Write back the updated pyproject.toml
with open(TOML_PATH, "wb") as f:
    tomli_w.dump(data, f)

print("✅ pyproject.toml dependencies updated to reflect current virtualenv.")
