# LineRun

LineRun is an isolated Python execution environment ("sandbox") tailored specifically for autonomous AI agents. It provides a clean, path-traversal-protected interface for writing code, managing dependencies via virtual environments, and executing Python scripts safely.

## Features

* **Virtual Environment Isolation**: Automatically creates a dedicated `venv` for each runner instance.
* **Path Traversal Protection**: Enforces strict boundaries to ensure agents cannot read, edit, or execute files outside the designated sandbox directory.
* **AI-Friendly File I/O**: Provides methods specifically designed to reduce LLM token usage and formatting hallucinations, including full-file overwrites and exact-string replacements.
* **Dependency Management**: Native API for pip installing and managing external modules within the sandbox.
* **NixOS Compatibility**: Automatically detects NixOS and wraps execution in a `nix-shell` configured to properly link dynamic C/C++ libraries (like `libstdc++`, OpenGL, X11) when installing binary wheels from PyPI.

## Installation

LineRun is built using standard Python libraries and can be packaged via PyPI. 

```bash
git clone 
cd LineRun
pip install -e .
```

If you intend to run this in a production environment with untrusted AI code, it is **highly recommended** to install and run LineRun inside an isolated Docker container. Directory separation alone does not prevent malicious OS-level system calls or network access.

## Quick Start

```python
from linerun.main import Code_Runner

# 1. Initialize the sandbox
# This automatically creates the venv
runner = Code_Runner(Path="./my_sandbox", Venv_Path="./my_venv")

# 2. Add dependencies
runner.Add_Module("requests")

# 3. Write code
script = '''
import requests
resp = requests.get("https://api.github.com")
print("Status Code:", resp.status_code)
'''
runner.Write_File("fetch.py", script)

# 4. Execute the code
output = runner.Run_Code("fetch.py")
print("Agent Output:", output)
```

## API Reference

### Initialization
* `Code_Runner(Path, Venv_Path)`: Creates a new sandboxed runner. Will throw an error if `Path` is not empty. Automatically scaffolds the Python virtual environment.

### File Operations
* `Write_File(Name, Content)`: Overwrites (or creates) a file with the exact content provided.
* `Replace_In_File(Name, TargetContent, ReplacementContent)`: Finds the first exact match of `TargetContent` and replaces it. Ideal for surgical patches. Throws an error if the match is not exact.
* `Read_File(Name)`: Returns the string contents of a file.
* `Add_File(Name)`: Creates an empty file.
* `Delete_File(Name)`: Deletes a file.
* `All_files(regex=None)`: Returns a list of all files relative to the sandbox path. Supports optional regex filtering.

### Dependency Management
* `Add_Module(Name)`: Uses pip to install a package into the virtual environment.
* `Remove_Module(Name)`: Uninstalls a package.
* `List_Modules()`: Lists all installed pip packages.

### Execution
* `Run_Code(Name)`: Executes a file using the virtual environment's Python binary. Captures and returns standard output.
