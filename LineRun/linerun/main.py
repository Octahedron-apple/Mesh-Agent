import os
import re
import sys
import subprocess
import shlex

def Is_Nixos():
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            if "nixos" in f.read().lower():
                return True
    if os.path.exists("/etc/nixos"):
        return True
    return False

class Code_Runner:
    def __init__(self, Path, Venv_Path):
        self.Path = Path
        self.Venv_Path = Venv_Path   
        self.Is_Nixos_Flag = Is_Nixos()
        if os.path.exists(Path) and os.listdir(Path):
            raise ValueError(f"Directory '{Path}' is not empty.")       
        os.makedirs(self.Path, exist_ok=True)
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", self.Venv_Path],
                check=True,
                capture_output=True
            )
            subprocess.run(["git", "init"], cwd=self.Path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "AI"], cwd=self.Path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "AI@AI.AI"], cwd=self.Path, check=True, capture_output=True)
            self.Commit_Hashes = []
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Initialization failed: {e.stderr.decode('utf-8')}")
    def Get_Safe_Path(self, Name):
        if os.path.isabs(Name):
            raise ValueError("Input must be a relative path.")
        if not Name:
            raise ValueError("Path cannot be empty.")
        Base = os.path.realpath(self.Path)
        Target = os.path.realpath(os.path.join(Base, Name))
        if not Target.startswith(Base + os.sep):
            raise ValueError("Path traversal is not allowed.")
        Rel_Path = os.path.relpath(Target, Base)
        if Rel_Path == ".git" or Rel_Path.startswith(".git" + os.sep):
            raise ValueError("Access to the .git directory is forbidden.")
        return Target
    def Add_File(self, Name):
        File_Path = self.Get_Safe_Path(Name)
        os.makedirs(os.path.dirname(File_Path), exist_ok=True)
        with open(File_Path, 'w'):
            pass
    def All_Files(self, Regex=None):
        All_Files_List = []
        try:
            pattern = re.compile(Regex) if Regex else None
        except re.error as e:
            raise ValueError(f"Invalid Regex: {e}")
        if not os.path.exists(self.Path):
            return []
        for root, dirs, Files in os.walk(self.Path):
            if '.git' in dirs:
                dirs.remove('.git')
            for file in Files:
                Rel_Path = os.path.relpath(os.path.join(root, file), self.Path)
                if pattern is None or pattern.search(Rel_Path):
                    All_Files_List.append(Rel_Path)
        return All_Files_List
    def Delete_File(self, Name):
        File_Path = self.Get_Safe_Path(Name)
        if os.path.exists(File_Path) and os.path.isfile(File_Path):
            os.remove(File_Path)
    def Add_Module(self, Name):
        if Name.startswith("-"):
            raise ValueError("Package name cannot start with a hyphen.")
        PATH = os.path.join(self.Venv_Path, "bin", "pip")
        try:
            subprocess.run(
                [PATH, "install", Name],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to install module {Name}: {e.stderr.decode('utf-8')}")
    def List_Modules(self):
        PATH = os.path.join(self.Venv_Path, "bin", "pip")
        try:
            result = subprocess.run(
                [PATH, "list"],
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to list Modules: {e.stderr}")
    def Remove_Module(self, Name):
        if Name.startswith("-"):
            raise ValueError("Package name cannot start with a hyphen.")
        PATH = os.path.join(self.Venv_Path, "bin", "pip")
        try:
            subprocess.run(
                [PATH, "uninstall", "-y", Name],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to remove module {Name}: {e.stderr.decode('utf-8')}")
    def Run_Code(self, Name):
        import threading
        File_Path = self.Get_Safe_Path(Name)
        Python_Path = os.path.join(self.Venv_Path, "bin", "python")
        if self.Is_Nixos_Flag:
            Shell_Nix_Path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shell.nix"))
            Command = ["nix-shell", Shell_Nix_Path, "--run", f"{shlex.quote(Python_Path)} {shlex.quote(File_Path)}"]
        else:
            Command = [Python_Path, File_Path]  
        
        Process = subprocess.Popen(
            Command,
            cwd=self.Path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        Limit_Bytes = 1024 * 1024  # 1MB
        Out_Data = bytearray()
        Err_Data = bytearray()
        
        def Read_Stream(Stream, Buffer):
            while True:
                Chunk = Stream.read(4096)
                if not Chunk:
                    break
                Buffer.extend(Chunk)
                if len(Buffer) > Limit_Bytes:
                    try:
                        Process.terminate()
                    except Exception:
                        pass
                    break
                    
        T_Out = threading.Thread(target=Read_Stream, args=(Process.stdout, Out_Data))
        T_Err = threading.Thread(target=Read_Stream, args=(Process.stderr, Err_Data))
        T_Out.start()
        T_Err.start()
        
        Timeout_Occurred = False
        try:
            Process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            Process.terminate()
            Process.wait()
            Timeout_Occurred = True
            
        T_Out.join()
        T_Err.join()
        
        Stdout_Str = Out_Data.decode('utf-8', errors='replace')
        Stderr_Str = Err_Data.decode('utf-8', errors='replace')
        
        if len(Out_Data) > Limit_Bytes:
            Stdout_Str += "\n...[Output truncated due to excessive length]..."
        if len(Err_Data) > Limit_Bytes:
            Stderr_Str += "\n...[Output truncated due to excessive length]..."
            
        if Timeout_Occurred:
            Stderr_Str += "\nExecution timed Out after 30 seconds."
            Exit_Code = 124
        else:
            Exit_Code = Process.returncode
            
        return {
            "stdout": Stdout_Str,
            "stderr": Stderr_Str,
            "Exit_Code": Exit_Code
        }
    def Read_File(self, Name):
        File_Path = self.Get_Safe_Path(Name)
        if not os.path.exists(File_Path):
            raise FileNotFoundError(f"File {Name} does not exist.")
        with open(File_Path, 'r') as f:
            return f.read()
    def Write_File(self, Name, Content):
        File_Path = self.Get_Safe_Path(Name)
        os.makedirs(os.path.dirname(File_Path), exist_ok=True)
        with open(File_Path, 'w') as f:
            f.write(Content)
    def Replace_In_File(self, Name, Target_Content, Replacement_Content, Start_Line=1, End_Line=None, Allow_Multiple=False):
        File_Path = self.Get_Safe_Path(Name)
        if not os.path.exists(File_Path):
            raise FileNotFoundError(f"File {Name} does not exist.")  
        with open(File_Path, 'r') as f:
            Lines = f.readlines() 
        Start_Line = max(1, Start_Line)
        if End_Line is None or End_Line > len(Lines):
            End_Line = len(Lines)  
        Range_Content = "".join(Lines[Start_Line-1:End_Line])
        if Target_Content not in Range_Content:
            raise ValueError(f"Target content not found between Lines {Start_Line} and {End_Line}.")
        Occurrences = Range_Content.count(Target_Content)
        if Occurrences > 1 and not Allow_Multiple:
            raise ValueError(f"Found {Occurrences} Occurrences of Target_Content. Specify Allow_Multiple=True to replace all, or narrow Start_Line/End_Line.") 
        New_Range_Content = Range_Content.replace(Target_Content, Replacement_Content, -1 if Allow_Multiple else 1)
        New_Content = "".join(Lines[:Start_Line-1]) + New_Range_Content + "".join(Lines[End_Line:])
        with open(File_Path, 'w') as f:
            f.write(New_Content)
    def Commit(self, Message):
        try:
            subprocess.run(["git", "add", "."], cwd=self.Path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", Message], cwd=self.Path, check=True, capture_output=True)
            res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.Path, check=True, capture_output=True, text=True)
            Commit_Hash = res.stdout.strip()
            self.Commit_Hashes.append(Commit_Hash)
            return Commit_Hash
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git commit failed: {e.stderr if isinstance(e.stderr, str) else e.stderr.decode('utf-8')}")
    def Reset(self, Commit_Hash=None):
        if Commit_Hash is None:
            if not self.Commit_Hashes:
                raise ValueError("No commits to reset to.")
            Commit_Hash = self.Commit_Hashes[-1]
        elif Commit_Hash not in self.Commit_Hashes:
            raise ValueError("Commit hash not found in history.")
        try:
            subprocess.run(["git", "reset", "--hard", Commit_Hash], cwd=self.Path, check=True, capture_output=True)
            subprocess.run(["git", "clean", "-fd"], cwd=self.Path, check=True, capture_output=True)
            idx = self.Commit_Hashes.index(Commit_Hash)
            self.Commit_Hashes = self.Commit_Hashes[:idx+1]
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git reset failed: {e.stderr if isinstance(e.stderr, str) else e.stderr.decode('utf-8')}")