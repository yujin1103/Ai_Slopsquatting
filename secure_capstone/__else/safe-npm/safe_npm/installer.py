import subprocess
from typing import Sequence


def run_npm_install(package_name: str, extra_args: Sequence[str] | None = None) -> int:
    cmd = ["npm", "install", package_name]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd)
    return result.returncode