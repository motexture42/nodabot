from tools.base import BaseTool
import subprocess
import sys
import tempfile
import os
import venv
import shutil

class CodeExecutorTool(BaseTool):
    """Executes Python code safely, optionally in an isolated virtual environment."""
    
    @property
    def name(self) -> str:
        return "execute_python"

    @property
    def description(self) -> str:
        return "Executes a Python code string. Can optionally install dependencies before running. Useful for complex math, data manipulation, charting, or testing without polluting the main environment."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute. Do not wrap in markdown blocks, just the raw code string."
                },
                "dependencies": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Optional list of pip packages to install before running (e.g. ['pandas', 'matplotlib'])."
                }
            },
            "required": ["code"]
        }

    def run(self, code: str, dependencies: list = None, **kwargs) -> str:
        # Create a temporary directory to act as our sandbox workspace
        sandbox_dir = tempfile.mkdtemp(prefix="nodabot_sandbox_")
        script_path = os.path.join(sandbox_dir, "script.py")
        
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            python_executable = sys.executable
            output = ""
            
            # If dependencies are requested, create an isolated venv
            if dependencies and len(dependencies) > 0:
                venv_dir = os.path.join(sandbox_dir, "venv")
                output += f"Creating isolated environment and installing: {', '.join(dependencies)}...\n"
                
                # Create venv
                venv.create(venv_dir, with_pip=True)
                
                # Determine venv python path (works for UNIX and Windows)
                if os.name == 'nt':
                    python_executable = os.path.join(venv_dir, "Scripts", "python.exe")
                    pip_executable = os.path.join(venv_dir, "Scripts", "pip.exe")
                else:
                    python_executable = os.path.join(venv_dir, "bin", "python")
                    pip_executable = os.path.join(venv_dir, "bin", "pip")
                
                # Install dependencies
                pip_result = subprocess.run(
                    [pip_executable, "install", "--quiet"] + dependencies,
                    capture_output=True,
                    text=True,
                    cwd=sandbox_dir
                )
                
                if pip_result.returncode != 0:
                    output += f"Failed to install dependencies:\n{pip_result.stderr}\n"
                    return output
                    
                output += "Dependencies installed successfully.\n---\n"
            
            # Execute the code
            result = subprocess.run(
                [python_executable, script_path],
                capture_output=True,
                text=True,
                timeout=60,  # 60s timeout for complex operations
                cwd=sandbox_dir
            )
            
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
                
            if not result.stdout and not result.stderr:
                output += "(Code executed successfully with no output)"
                
            return output
            
        except subprocess.TimeoutExpired:
            return "Execution timed out after 60 seconds."
        except Exception as e:
            return f"Execution Error: {str(e)}"
        finally:
            # Clean up the sandbox
            shutil.rmtree(sandbox_dir, ignore_errors=True)
