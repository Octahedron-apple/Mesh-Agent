from mcp.server.fastmcp import FastMCP
import os
from linerun.main import Code_Runner
from dotdb.main import DataBase, point
from fastembed import TextEmbedding

mcp = FastMCP("PlaneMCP")

class PlaneMCPServer:
    def __init__(self, memory_dir: str = None):
        self.runner = None
        self.model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
        if memory_dir is None:
            import inspect
            try:
                current_file = os.path.abspath(__file__)
                caller_dir = None
                for frame_info in inspect.stack():
                    frame_file = os.path.abspath(frame_info.filename)
                    if frame_file != current_file:
                        caller_dir = os.path.dirname(frame_file)
                        break
                
                if caller_dir is None:
                    caller_dir = os.getcwd()
                memory_path = os.path.join(caller_dir, "facts.db")
            except Exception:
                memory_path = os.path.join(os.getcwd(), "facts.db")
        else:
            memory_path = os.path.join(memory_dir, "facts.db")
            
        try:
            self.db = DataBase(Dimensions=384, Path=memory_path)
            if os.path.exists(memory_path):
                self.db.load()
        except Exception as e:
            self.db = None

server = PlaneMCPServer()

@mcp.tool()
def init_runner(path: str, venv_path: str) -> str:
    """
    Creates a new sandboxed runner. 
    Will throw an error if Path is not empty. Automatically scaffolds the Python virtual environment.
    """
    os.makedirs(path, exist_ok=True)
    server.runner = Code_Runner(path, venv_path)
    return f"Successfully initialized Code_Runner at {path} with venv {venv_path}"

@mcp.tool()
def write_file(name: str, content: str) -> str:
    """Overwrites (or creates) a file with the exact content provided."""
    if not server.runner:
        return "Error: Code_Runner not initialized. Call init_runner first."
    server.runner.Write_File(name, content)
    return f"Successfully wrote to {name}"

@mcp.tool()
def replace_in_file(name: str, target_content: str, replacement_content: str) -> str:
    """
    Finds the first exact match of TargetContent and replaces it. 
    Ideal for surgical patches. Throws an error if the match is not exact.
    """
    if not server.runner:
        return "Error: Code_Runner not initialized."
    server.runner.Replace_In_File(name, target_content, replacement_content)
    return f"Successfully replaced content in {name}"

@mcp.tool()
def read_file(name: str) -> str:
    """Returns the string contents of a file."""
    if not server.runner:
        return "Error: Code_Runner not initialized."
    return server.runner.Read_File(name)

@mcp.tool()
def add_file(name: str) -> str:
    """Creates an empty file."""
    if not server.runner:
        return "Error: Code_Runner not initialized."
    server.runner.Add_File(name)
    return f"Successfully added empty file {name}"

@mcp.tool()
def delete_file(name: str) -> str:
    """Deletes a file."""
    if not server.runner:
        return "Error: Code_Runner not initialized."
    server.runner.Delete_File(name)
    return f"Successfully deleted {name}"

@mcp.tool()
def all_files(regex: str = None) -> list[str]:
    """Returns a list of all files relative to the sandbox path. Supports optional regex filtering."""
    if not server.runner:
        raise ValueError("Code_Runner not initialized.")
    return server.runner.All_files(regex)

@mcp.tool()
def add_module(name: str) -> str:
    """Uses pip to install a package into the virtual environment."""
    if not server.runner:
        return "Error: Code_Runner not initialized."
    server.runner.Add_Module(name)
    return f"Successfully added module {name}"

@mcp.tool()
def remove_module(name: str) -> str:
    """Uninstalls a package."""
    if not server.runner:
        return "Error: Code_Runner not initialized."
    server.runner.Remove_Module(name)
    return f"Successfully removed module {name}"

@mcp.tool()
def list_modules() -> list[str]:
    """Lists all installed pip packages."""
    if not server.runner:
        raise ValueError("Code_Runner not initialized.")
    return server.runner.List_Modules()

@mcp.tool()
def run_code(name: str) -> str:
    """Executes a file using the virtual environment's Python binary. Captures and returns standard output."""
    if not server.runner:
        return "Error: Code_Runner not initialized."
    return server.runner.Run_Code(name)

@mcp.tool()
def remember_fact(fact: str) -> str:
    """Stores a fact into the local dotdb database."""
    if not server.db:
        return "Error: Database not initialized."
    emb = list(server.model.embed([fact]))[0].tolist()
    p = point(fact, 384, emb)
    server.db.insert(p)
    server.db.save()
    return "Successfully remembered fact."

@mcp.tool()
def recall_info(query: str, k: int = 3) -> list[str]:
    """Recalls up to k relevant facts from the local dotdb database based on the query."""
    if not server.db:
        raise ValueError("Database not initialized.")
    emb = list(server.model.embed([query]))[0].tolist()
    p = point(query, 384, emb)
    results = server.db.search(p, k)
    return [res[1].text for res in results]

if __name__ == "__main__":
    mcp.run()