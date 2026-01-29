// Importing modules
import React, { useState, useEffect } from "react";

function App() {
	// usestate for setting a javascript
	// object for storing and using data
	const [data, setdata] = useState({
		time: "",
		count: 0,
	});

	// Using useEffect for single rendering
	useEffect(() => {
		// Using fetch to fetch the api from
		// flask server it will be redirected to proxy
		fetch("http://127.0.0.1:5000/api").then((res) =>
			res.json().then((data) => {
				// Setting a data from api
				setdata({
					time: data.time,
					count: data.count
				});
			})
		);
	}, []);

	return (
		<div className="App">
			<header className="App-header">
				<h1>React and flask</h1>
				{/* Calling a data from setdata for showing */}
				<p>{data.time}</p>
				<p>{data.count}</p>

			</header>
		</div>
	);
}

export default App;
