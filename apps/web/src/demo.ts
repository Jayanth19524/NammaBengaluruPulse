// Demo monitored routes. In the product these come from the user's saved routes.
// They are labelled as demo data in the UI.
export interface DemoRoute { id: string; name: string; geometry: [number, number][]; corridor_m: number }

export const DEMO_ROUTES: DemoRoute[] = [
  { id: "demo-a", name: "Demo route A", geometry: [[77.615, 12.9177], [77.635, 12.9177]], corridor_m: 50 },
  { id: "demo-b", name: "Demo route B", geometry: [[77.6245, 12.93], [77.6245, 12.94]], corridor_m: 50 },
];
export const MAP_CENTER: [number, number] = [77.6245, 12.9235]; // lon, lat
