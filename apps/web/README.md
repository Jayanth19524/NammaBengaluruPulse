# NammaPulse web

React + TypeScript + Vite. 3D map via MapLibre GL with free OpenFreeMap vector tiles (3D buildings, no API key).
Incident columns are extruded by severity. Currently shows RoadTrust data only.

```bash
# terminal 1: RoadTrust API (see agents/roadtrust/README.md)
uvicorn roadtrust.api:create_app --factory --port 8002
# terminal 2 (TripCast, optional TOMTOM_API_KEY for live traffic): uvicorn tripcast.api:create_app --factory --port 8003
# terminal 3
npm install && npm run dev   # http://127.0.0.1:5173, /api proxies to :8002
```

Routes are demo routes (`src/demo.ts`) and mock incidents are labelled "Demo data".
