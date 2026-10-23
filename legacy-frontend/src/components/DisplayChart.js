import React, { useState } from 'react';
import Notice from './Notice';
import PopularityChart from "./PopularityChart"

function MyDropdown() {
  const [selectedOption, setSelectedOption] = useState('AMPM18-KJ016');

  function handleChange(event) {
    setSelectedOption(event.target.value);
  }

  return (
    <div>
      <select value={selectedOption} onChange={handleChange}>
        <option value="AMPM18-KJ008">C Cluster Admnistration Office</option>
        <option value="AMPM18-KJ009">C1 Bldng Entrance</option>
        <option value="AMPM18-KJ011">B Cluster Administration Office</option>
        <option value="AMPM18-KJ012">Katsura Main Student Library</option>
        <option value="AMPM18-KJ013">A4 Rear Entrance</option>
        <option value="AMPM18-KJ014">P3P Parking Mae</option>
        <option value="AMPM18-KJ015">Boulangerie Seri Bakery</option>
        <option value="AMPM18-KJ010">Inside Main Cafeteria</option>
        <option value="AMPM18-KJ016">Main Cafeteria Entrance</option>
        <option value="AMPM18-KJ017">Main Cafeteria Exit</option>
      </select>
      <Notice location={selectedOption}/>
      <PopularityChart location={selectedOption}/>
    </div>
  );
}

export default MyDropdown;
