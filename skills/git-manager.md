# Skill: Git Version Control Manager

## Overview
Use this skill when asked to manage repositories, create commits, resolve conflicts, or analyze git history.

## Workflow & Best Practices
1. **Commit Messages**: Always use Conventional Commits format. 
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `refactor:` for code changes that neither fix a bug nor add a feature
   - Example: `feat: add user authentication module`
2. **Branching**: Do not commit directly to `main` or `master` if instructed to create a feature. Use `git checkout -b feature/name`.
3. **Checking Status**: Always run `git status` and `git diff` before committing to ensure you are only staging the intended files.
4. **Undoing**: If you make a mistake, use `git restore <file>` to unstage, or `git reset HEAD~1` to undo the last local commit safely.

## Safety Warnings
- NEVER run `git push --force` unless explicitly authorized by the user.
- NEVER run `git clean -fdx` or `git reset --hard` without confirming what will be deleted.