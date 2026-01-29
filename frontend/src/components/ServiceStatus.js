import React, { useState, useEffect } from "react";


function ServiceStatus({count, average_count, apiURL, location}) {
	const [status, setStatus] = useState();

  var message;
  var percent_diff = (count - average_count)/average_count

  if (Math.abs(percent_diff) <= 0.05){
    message = "As busy as usual."
  }
  else if (percent_diff > 0.05 && percent_diff <= 0.50) {
    message = "Busier than usual."
  }
  else if (percent_diff > 0.50) {
    message = "Much busier than usual."
  }
  else if (percent_diff < -0.05 && percent_diff >= -0.50){
    message = "Less busier than usual."
  }
  else if (percent_diff < -0.50) {
    message = "Much less busier than usual."
  } else {
    message = " "
  }

  return message
}; 
 
export default ServiceStatus;
