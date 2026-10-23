export const API_BASE = import.meta.env.VITE_API_BASE || "";
export const DAY_ENDPOINT = "/api/history_day_cache"; // file name of your history_day function

// Replace SENSORS in src/config.js with this, and update CAMPUS to the centre of the pins.
export const CAMPUS = { lat: 34.9809, lon: 135.6798 };

export const SENSORS = [
  { id: "AMPM18-KJ008", name: "C Cluster Administration Office", loc: [34.9825981, 135.6771705] },
  { id: "AMPM18-KJ009", name: "C1 Bldng Entrance", loc: [34.982129, 135.677817] },
  { id: "AMPM18-KJ011", name: "B Cluster Administration Office", loc: [34.9806499, 135.6798235] },
  { id: "AMPM18-KJ012", name: "Katsura Main Student Library", loc: [34.9806554, 135.6802679] },
  { id: "AMPM18-KJ013", name: "A4 Rear Entrance", loc: [34.97855, 135.682213] },
  { id: "AMPM18-KJ014", name: "P3P Parking Mae", loc: [34.979094, 135.682951] },
  { id: "AMPM18-KJ015", name: "Boulangerie Seri Bakery", loc: [34.9799707, 135.6808415] },
  // The campus photo labels sensor 10 "ITS Lab", and your ITS Lab coordinates sit up in the C cluster.
  // The old dropdown called it "Inside Main Cafeteria", which doesn't match.
  { id: "AMPM18-KJ010", name: "ITS Lab", loc: [34.9825058, 135.6766929] },
  { id: "AMPM18-KJ016", name: "Main Cafeteria Entrance", loc: [34.981537, 135.680908] },
  { id: "AMPM18-KJ017", name: "Main Cafeteria Exit", loc: [34.981207, 135.6804768] },
];
export const PROFILE_ENDPOINT = "/api/weekday_profile";