# Skill: System Administrator (macOS/Linux)

## Overview
Use this skill when managing local operating system settings, analyzing processes, or writing shell scripts.

## Best Practices
1. **Safe Discovery**: Use safe commands for discovery. Use `ls -la`, `df -h` (disk space), `top` or `ps aux` (processes), and `netstat -tuln` or `lsof -i` (network ports).
2. **Scripting**: When writing bash scripts, always start with `#!/bin/bash` and use `set -e` to make the script exit immediately if a command fails.
3. **Permissions**: Understand `chmod` and `chown`. If a script won't run, check if it is executable (`chmod +x script.sh`).
4. **Killing Processes**: If a port is blocked, find the PID using `lsof -i :<port>` and kill it gracefully with `kill <PID>`. Only use `kill -9` as a last resort.

## Warnings
- Be extremely cautious with `rm -rf`, `chown -R`, and `chmod -R`. 
- Remember that the agent runs on the user's actual host machine. Destructive actions are permanent.