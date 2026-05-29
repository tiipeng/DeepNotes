# DeepNotes — frontend

Next.js 14 (App Router, TypeScript) + Tailwind. UI for the DeepNotes "chat with your
sources" workspace. See the [root README](../README.md) for the full project, architecture,
and setup.

```bash
pnpm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
pnpm dev   # http://localhost:3000
```

Requires the backend running (see `../backend`).
