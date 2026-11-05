export const API_BASE = import.meta.env.VITE_API_BASE || "";
export const DAY_ENDPOINT = "/api/history_day_cache"; // file name of your history_day function

// Replace SENSORS in src/config.js with this, and update CAMPUS to the centre of the pins.
export const CAMPUS = { lat: 34.9809, lon: 135.6798 };

export const SENSORS = [
  { id: "AMPM18-KJ008", name: "C Cluster: C1 Building Entrance", loc: [34.983057583684726, 135.67695960623746] },
  { id: "AMPM18-KJ009", name: "C Cluster: Main Entrance", loc: [34.982365611695265, 135.67769630947933] },
  { id: "AMPM18-KJ010", name: "C Cluster: ITS Lab", loc: [34.98256451490079, 135.67690280655785] },
  { id: "AMPM18-KJ011", name: "C Cluster: Cenatio Silva (Cafeteria)", loc: [34.983145597638725, 135.67798288938803] },
  { id: "AMPM18-KJ012", name: "B Cluster: Main Student Library", loc: [34.980936467837076, 135.68078092815006] },
  { id: "AMPM18-KJ013", name: "A Cluster: A4 Building Rear Entrance", loc: [34.9788878321967, 135.6822687797368] },
  { id: "AMPM18-KJ014", name: "A Cluster: P3P Parking Mae", loc: [34.979145821124455, 135.6831683957342] },
  { id: "AMPM18-KJ015", name: "B Cluster: Boulangerie Seri Bakery", loc: [34.9798260907664, 135.68112695453104] },
  { id: "AMPM18-KJ016", name: "B Cluster: Cafeteria Entrance", loc: [34.98149432442253, 135.68061977226762] },
  { id: "AMPM18-KJ017", name: "B Cluster: Cafeteria Exit", loc: [34.981525640697285, 135.68085379499442] },
];
export const PROFILE_ENDPOINT = "/api/weekday_profile";