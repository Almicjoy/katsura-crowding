import * as React from 'react';

import Exclamation from "../images/exclamation.svg"

const notice_sensors = ["AMPM18-KJ010", "AMPM18-KJ016", "AMPM18-KJ017"];

const Notice = ({ location }) => {
  const time = new Date();
  var hourNow = time.getHours();
  var message = null;

  if (notice_sensors.includes(location)){
    message = "Cafeteria Selene is open for lunch from 11:00AM to 2:00PM"
  } else if (location == "AMPM18-KJ008") {
    message = "C CLUSTER Admnistration Office is open from 9:00AM TO 5:00PM"
  } else if (location == "AMPM18-KJ009") {
    message = "C1 Bldng. Entrance is open from 6:00AM and can be acessed with the University Student card after 6:00PM"
  } else if (location == "AMPM18-KJ011") {
    message = "B Cluster Admnistration Office is Open from 9:00AM to 5:00PM"
  } else if (location == "AMPM18-KJ012") {
    message = "Katsura Mani Student Library is open from 9:00AM to 9:00PM"
  } else if (location == "AMPM18-KJ013") {
    message = "P3P Parking at A Cluster Between Buildings A3 and A4 is open 24 Hours"
  } else if (location == "AMPM18-KJ014") {
    message = "A4 Rear Entrance is a 24HourOpen short route Access from Katsura Innovation Park Mae Bus Stop at A Cluster"
  } else if (location == "AMPM18-KJ015") {
    message = "Boulangerie Seri Bakery is open from 8:00AM to 3:00PM from Monday to Saturday"
  }

  console.log("Message: ", message)
  if (message != null) {
    return (
      <div className="flex gap-1 p-2 bg-yellow-200 rounded-lg items-center">
        <img
          className="inline h-4"
          src={Exclamation}
          alt="Exclamation"
        />
        <p className="text-xs text-gray-800 font-medium">{message}</p>
      </div>
    )
  } else {
    return (
      <div></div>
    )
  } 
};
 
export default Notice;
