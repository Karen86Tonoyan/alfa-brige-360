import subprocess
from pathlib import Path

VERSION_FILE = Path("VERSION")

def run(cmd: list[str]):
    print(">", " ".join(cmd))
    subprocess.check_call(cmd)

def read_version() -> tuple[int, int, int]:
    if not VERSION_FILE.exists():
        return (0, 1, 0)
    text = VERSION_FILE.read_text(encoding="utf-8").strip()
    major, minor, patch = text.split(".")
    return int(major), int(minor), int(patch)

def write_version(v: tuple[int, int, int]):
    VERSION_FILE.write_text("{}.{}.{}\n".format(*v), encoding="utf-8")

def bump(kind: str, v: tuple[int, int, int]) -> tuple[int, int, int]:
    major, minor, patch = v
    if kind == "major":
        return major + 1, 0, 0
    if kind == "minor":
        return major, minor + 1, 0
    if kind == "patch":
        return major, minor, patch + 1
    raise ValueError("Unknown kind: " + kind)

if __name__ == "__main__":
    import sys
    kind = sys.argv[1] if len(sys.argv) > 1 else "patch"
    old_v = read_version()
    new_v = bump(kind, old_v)
    write_version(new_v)
    tag = f"v{new_v[0]}.{new_v[1]}.{new_v[2]}"

    run(["git", "add", "VERSION"])
    run(["git", "commit", "-m", f"Bump version to {tag}"])
    run(["git", "tag", tag])
    run(["git", "push"])
    run(["git", "push", "--tags"])
