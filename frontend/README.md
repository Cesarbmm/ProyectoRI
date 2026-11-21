# FiQA frontend

React + Vite + TypeScript. Buscador real conectado a FastAPI; no incluye resultados
de búsqueda simulados. Instalación, arquitectura, métricas, evidencias y conexión
API: [docs/FRONTEND.md](../docs/FRONTEND.md).

Despliegue Vercel, backend HTTPS y smoke test público:
[docs/DESPLIEGUE.md](../docs/DESPLIEGUE.md).

```powershell
# Desde frontend/; Node 22.12+ (comprobado con Node 24)
npm ci
Copy-Item .env.example .env.local
npm run dev
```

El backend debe estar disponible en `VITE_API_URL`. El valor predeterminado es
`http://127.0.0.1:8000`; el frontend abre en `http://127.0.0.1:5173`.

```powershell
npm test
npx playwright install chromium
npm run test:e2e
npm run build
npm run format:check
```

Playwright inicia Vite y FastAPI si no están ejecutándose. Para las pruebas reales
se requieren los recursos completos de FiQA y el encoder BGE ya descargado. Los
fallos de transporte solo se inyectan desde las pruebas; la aplicación no tiene
un modo demo ni respuestas de respaldo.
