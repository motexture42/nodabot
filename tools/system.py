from tools.base import BaseTool
import psutil
import platform
import json

class SystemMonitorTool(BaseTool):
    """Provides system diagnostics like CPU, RAM, and Disk usage."""
    
    @property
    def name(self) -> str:
        return "system_monitor"

    @property
    def description(self) -> str:
        return "Returns current system metrics (CPU, RAM, Disk usage) and OS information."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "verbose": {
                    "type": "boolean",
                    "description": "If true, includes top 5 active processes."
                }
            },
            "required": []
        }

    def run(self, verbose: bool = False, **kwargs) -> str:
        try:
            uname = platform.uname()
            cpu_usage = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            data = {
                "os": f"{uname.system} {uname.release}",
                "cpu_usage_percent": cpu_usage,
                "ram_total_gb": round(mem.total / (1024**3), 2),
                "ram_used_percent": mem.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            }
            
            if verbose:
                processes = []
                for proc in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']), 
                                   key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:5]:
                    processes.append(proc.info)
                data["top_processes"] = processes
                
            return json.dumps(data, indent=2)
        except Exception as e:
            return f"System Monitor Error: {str(e)}"
