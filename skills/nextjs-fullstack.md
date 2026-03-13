# Skill: Next.js Fullstack Developer

## Overview
Use this skill when scaffolding or building React applications using the Next.js framework (App Router).

## Best Practices
1. **App Router**: Always use the modern `app/` directory paradigm, not the legacy `pages/` directory, unless explicitly told otherwise.
2. **Server Components**: By default, components in the `app/` directory are React Server Components (RSC). Do not use hooks like `useState`, `useEffect`, or event listeners (`onClick`) in them.
3. **Client Components**: If you need interactivity or state, add the `"use client"` directive at the very top of the file. Keep client components as leaves in the component tree.
4. **Routing**: Create routes by adding `page.tsx` files inside folders (e.g., `app/dashboard/page.tsx` creates the `/dashboard` route).

## Scaffolding
Use the standard initialization command:
`npx create-next-app@latest my-app --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"`

## Styling
Always use Tailwind CSS. Rely on standard utility classes instead of writing custom CSS modules.