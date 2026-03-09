from tools.base import BaseTool
import subprocess
import sys
import tempfile
import os

class CodeExecutorTool(BaseTool):
    """Executes Python code safely."""
    
    @property
    def name(self) -> str:
        return "execute_python"

    @property
    def description(self) -> str:
        return "Executes a Python code string and returns the standard output (stdout) and standard error (stderr). Useful for complex math, data manipulation, or testing."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute. Do not wrap in markdown blocks, just the raw code string."
                }
            },
            "required": ["code"]
        }

    def run(self, code: str, **kwargs) -> str:
        # Create a temporary file to run the code
        fd, path = tempfile.mkstemp(suffix=".py")
        home_dir = os.path.expanduser("~")
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(code)
            
            # Execute it using the current Python interpreter
            result = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                timeout=30,  # Hard timeout to prevent infinite loops
                cwd=home_dir
            )
            
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
                
            if not output:
                output = "(Code executed successfully with no output)"
                
            return output
            
        except subprocess.TimeoutExpired:
            return "Execution timed out after 30 seconds."
        except Exception as e:
            return f"Execution Error: {str(e)}"
        finally:
            os.remove(path)
