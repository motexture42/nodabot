# Skill: React Frontend Developer

## Overview
Use this skill when scaffolding or modifying React applications.

## Tools to use
- ALWAYS prefer `vite` for scaffolding. (e.g., `npm create vite@latest my-app -- --template react-ts`)
- NEVER use raw CSS. Always use TailwindCSS for styling.

## Workflow
1. Scaffold using Vite.
2. Install `tailwindcss`, `postcss`, and `autoprefixer`.
3. Initialize tailwind config (`npx tailwindcss init -p`).
4. Modify `tailwind.config.js` to include the `src/` folder: `content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"]`.
5. Add tailwind directives to the main css file.

## Common Errors
- If you see `Uncaught ReferenceError: process is not defined`, you forgot to use `import.meta.env` instead of `process.env`.