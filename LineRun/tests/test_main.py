import os
import re
import pytest
from unittest.mock import patch
from linerun.main import Code_Runner

@pytest.fixture
def Runner(tmp_path):
    Sandbox_Dir = tmp_path / "sandbox"
    Venv_Dir = tmp_path / "venv"
    os.makedirs(Sandbox_Dir, exist_ok=True)
    r = Code_Runner(Path=str(Sandbox_Dir), Venv_Path=str(Venv_Dir))
    yield r

def test_Get_Safe_Path(Runner, tmp_path):
    Safe = Runner.Get_Safe_Path("test.py")
    assert Safe == os.path.realpath(os.path.join(Runner.Path, "test.py"))
    with pytest.raises(ValueError):
        Runner.Get_Safe_Path("/absolute/path")
    with pytest.raises(ValueError):
        Runner.Get_Safe_Path("../outside.py")
        
    # Symlink Test
    Outside_Dir = tmp_path / "outside"
    os.makedirs(Outside_Dir, exist_ok=True)
    Outside_File = Outside_Dir / "secret.txt"
    with open(Outside_File, 'w') as f:
        f.write("secret")
    
    Symlink_Path = os.path.join(Runner.Path, "symlink")
    os.symlink(str(Outside_Dir), Symlink_Path)
    
    with pytest.raises(ValueError):
        Runner.Get_Safe_Path("symlink/secret.txt")

def test_Add_Delete_File(Runner):
    Runner.Add_File("script.py")
    assert os.path.exists(os.path.join(Runner.Path, "script.py"))
    Runner.Delete_File("script.py")
    assert not os.path.exists(os.path.join(Runner.Path, "script.py"))

def test_All_Files(Runner):
    Runner.Add_File("a.txt")
    Runner.Add_File("b.py")
    Runner.Add_File("dir/c.txt")
    Files = Runner.All_Files()
    assert len(Files) == 3
    Txt_Files = Runner.All_Files(r"\.txt$")
    assert len(Txt_Files) == 2
    
    with pytest.raises(ValueError, match="Invalid Regex"):
        Runner.All_Files(r"[A-Z")

def test_Read_Write_Replace(Runner):
    Runner.Write_File("test.txt", "hello world\nhello world\nhello world")
    assert "hello world" in Runner.Read_File("test.txt")
    Runner.Replace_In_File("test.txt", "world", "universe", End_Line=1)
    assert Runner.Read_File("test.txt") == "hello universe\nhello world\nhello world"
    Runner.Replace_In_File("test.txt", "world", "galaxy", Start_Line=3, End_Line=3)
    assert Runner.Read_File("test.txt") == "hello universe\nhello world\nhello galaxy"
    Runner.Write_File("test2.txt", "a b c\na b c")
    Runner.Replace_In_File("test2.txt", "b", "z", Allow_Multiple=True)
    assert Runner.Read_File("test2.txt") == "a z c\na z c"
    Runner.Write_File("test3.txt", "duplicate duplicate")
    with pytest.raises(ValueError, match="Found 2 Occurrences"):
        Runner.Replace_In_File("test3.txt", "duplicate", "single")
        
    # Negative Start_Line test
    Runner.Write_File("test4.txt", "line1\nline2\nline3\nline4")
    Runner.Replace_In_File("test4.txt", "line1", "new1", Start_Line=-5, End_Line=2)
    assert Runner.Read_File("test4.txt") == "new1\nline2\nline3\nline4"

def test_Run_Code(Runner, tmp_path):
    Runner.Write_File("run_test.py", "print('success')")
    Out = Runner.Run_Code("run_test.py")
    assert "success" in Out["stdout"]
    assert Out["Exit_Code"] == 0
    
    # Environment Isolation Test: relative paths should resolve to sandbox
    Runner.Write_File("iso_test.py", "open('data.json', 'w').write('isolated')")
    Runner.Run_Code("iso_test.py")
    assert os.path.exists(os.path.join(Runner.Path, "data.json"))
    
    # Shell Injection Test
    Runner.Write_File("echo.py", "print('hacked')")
    Runner.Write_File("script.py; python echo.py", "print('Safe')")
    Out = Runner.Run_Code("script.py; python echo.py")
    assert "hacked" not in Out["stdout"]

@patch('linerun.main.subprocess.run')
def test_Modules(Mock_Run, Runner):
    Mock_Run.return_value.stdout = "six"
    Mock_Run.return_value.returncode = 0
    
    Runner.Add_Module("six")
    # Verify pip install was called
    args, kwargs = Mock_Run.call_args
    assert "install" in args[0]
    assert "six" in args[0]
    
    Modules = Runner.List_Modules()
    assert Modules == "six"
    
    Runner.Remove_Module("six")
    args, kwargs = Mock_Run.call_args
    assert "uninstall" in args[0]
    assert "six" in args[0]

def test_Git_Commit_And_Reset(Runner):
    Runner.Write_File("file1.txt", "v1")
    Hash_1 = Runner.Commit("First commit")
    
    Runner.Write_File("file1.txt", "v2")
    Runner.Write_File("file2.txt", "new file")
    Hash_2 = Runner.Commit("Second commit")
    
    assert Runner.Read_File("file1.txt") == "v2"
    assert "file2.txt" in Runner.All_Files()
    assert Runner.Commit_Hashes == [Hash_1, Hash_2]
    
    Runner.Reset(Hash_1)
    
    assert Runner.Read_File("file1.txt") == "v1"
    assert "file2.txt" not in Runner.All_Files()
    assert Runner.Commit_Hashes == [Hash_1]
    
    Runner.Write_File("file1.txt", "dirty")
    Runner.Reset()
    assert Runner.Read_File("file1.txt") == "v1"
