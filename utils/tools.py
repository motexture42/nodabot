import importlib
import inspect
import pkgutil
import tools as tools_pkg
from tools.base import BaseTool
from core.llm import LLMProvider
from tools.spawn import SpawnTool
from tools.scheduler import SchedulerTool
from tools.watcher import SystemWatcherTool
from tools.browser import BrowserControllerTool

def get_tools(emit_cb=None):
    """
    Dynamically discovers and initializes all tool classes 
    defined in the 'tools/' directory.
    """
    llm = LLMProvider()
    tools = []
    
    for _, module_name, _ in pkgutil.iter_modules(tools_pkg.__path__):
        # Skip base classes and specific tools handled separately
        if module_name in ['base', 'spawn', 'scheduler', 'watcher', 'browser']:
            continue
            
        try:
            module = importlib.import_module(f"tools.{module_name}")
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseTool) and obj is not BaseTool:
                    sig = inspect.signature(obj.__init__)
                    kwargs = {}
                    if 'llm_provider' in sig.parameters:
                        kwargs['llm_provider'] = llm
                    if 'emit_cb' in sig.parameters:
                        kwargs['emit_cb'] = emit_cb
                    tools.append(obj(**kwargs))
        except Exception as e:
            print(f"Error loading tool module {module_name}: {e}")
            
    # Add singleton/orchestrator tools
    tools.append(SchedulerTool())
    tools.append(SystemWatcherTool(emit_cb=emit_cb))
    tools.append(BrowserControllerTool(emit_cb=emit_cb))
    tools.append(SpawnTool(tools_factory=lambda: get_tools(emit_cb), emit_cb=emit_cb))
    
    return tools
