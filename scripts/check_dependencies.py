#!/usr/bin/env python3
"""
Script to check all Python imports in the project and ensure they're in requirements.txt
"""
import os
import re
import sys
import ast


def find_imports(file_path):
    """Find all imports in a Python file"""
    with open(file_path, "r", encoding="utf-8") as file:
        try:
            tree = ast.parse(file.read())
        except SyntaxError:
            print(f"Syntax error in {file_path}")
            return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.append(name.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


def get_requirements():
    """Get all packages from requirements.txt"""
    with open("requirements.txt", "r", encoding="utf-8") as file:
        requirements = file.readlines()

    packages = []
    for req in requirements:
        req = req.strip()
        if not req or req.startswith("#"):
            continue
        # Extract package name (remove version specifiers)
        match = re.match(r"^([a-zA-Z0-9_\-]+)", req)
        if match:
            packages.append(match.group(1).lower())
    return packages


def main():
    """Main function"""
    python_files = []
    for root, _, files in os.walk("."):
        if "env" in root or ".git" in root or "venv" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    all_imports = set()
    for file_path in python_files:
        imports = find_imports(file_path)
        all_imports.update(imports)

    # Standard library modules to ignore
    stdlib_modules = {
        "os",
        "sys",
        "re",
        "datetime",
        "time",
        "json",
        "math",
        "random",
        "collections",
        "functools",
        "itertools",
        "io",
        "pathlib",
        "typing",
        "uuid",
        "hashlib",
        "base64",
        "logging",
        "unittest",
        "argparse",
        "csv",
        "urllib",
        "http",
        "socket",
        "ssl",
        "email",
        "smtplib",
        "tempfile",
        "shutil",
        "subprocess",
        "threading",
        "multiprocessing",
        "asyncio",
        "concurrent",
        "contextlib",
        "copy",
        "enum",
        "fnmatch",
        "glob",
        "gzip",
        "inspect",
        "operator",
        "platform",
        "pickle",
        "string",
        "struct",
        "warnings",
        "weakref",
        "xml",
        "zipfile",
        "ast",
    }

    # Remove standard library imports
    third_party_imports = all_imports - stdlib_modules

    # Get requirements
    requirements = get_requirements()

    # Check if all imports are in requirements
    missing = []
    for imp in third_party_imports:
        if imp.lower() not in requirements and imp.lower() not in ("django", "hirise"):
            missing.append(imp)

    if missing:
        print("Missing packages in requirements.txt:")
        for package in sorted(missing):
            print(f"- {package}")
        return 1

    print("All imports are in requirements.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
