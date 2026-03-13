from tools.base import BaseTool
import os
import glob
import re
from pathlib import Path

class ActivateSkillTool(BaseTool):
    """
    Tool to list and activate specialized agent skills.
    """
    def __init__(self, emit_cb=None):
        self.emit_cb = emit_cb
        self.skills_dir = Path("skills")
        self.skills_dir.mkdir(exist_ok=True)

    def _emit(self, event_type: str, data: dict):
        if self.emit_cb:
            self.emit_cb(event_type, data)

    @property
    def name(self) -> str:
        return "activate_skill"

    @property
    def description(self) -> str:
        return (
            "Dynamically loads expert knowledge or specific workflows into your current context. "
            "Use this when you recognize a task that matches an available skill (e.g. 'react-expert', 'data-analyst'). "
            "Call without arguments to list available skills, or pass 'name' to load one."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The exact name of the skill to load. If omitted, lists available skills."
                }
            },
            "required": []
        }

    def _list_skills(self) -> str:
        skills = []
        for file_path in self.skills_dir.glob("*.md"):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(1024) # Read start of file for description
                desc = "No description available."
                # Try to find a description block or use the first paragraph
                match = re.search(r'(?i)description:?\s*(.*)', content)
                if match:
                    desc = match.group(1).strip()
                elif content.strip():
                    desc = content.split('\n')[0].strip('# ')
                    
                skills.append(f"- **{file_path.stem}**: {desc}")
                
        if not skills:
            return "No skills currently available in the 'skills/' directory."
            
        return "Available Skills (Call activate_skill with the name to load):\n" + "\n".join(skills)

    def run(self, name: str = None, **kwargs) -> str:
        if not name:
            return self._list_skills()
            
        skill_path = self.skills_dir / f"{name}.md"
        
        if not skill_path.exists():
            return f"Error: Skill '{name}' not found. Use activate_skill without arguments to list available skills."
            
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                skill_content = f.read()
                
            self._emit("system_msg", {"message": f"🧠 Skill Loaded: {name}"})
            
            # We return the skill wrapped in XML tags to instruct the LLM to follow it
            return f"<activated_skill>\n<name>{name}</name>\n<instructions>\n{skill_content}\n</instructions>\n</activated_skill>\n\nCRITICAL: You MUST now follow the specialized instructions above for the remainder of this task."
            
        except Exception as e:
            return f"Error loading skill: {str(e)}"