import * as React from 'react';
import { Chart as ChartJS, ArcElement } from 'chart.js';
import { Doughnut } from 'react-chartjs-2';

ChartJS.register(ArcElement);

export const data = {
 datasets: [
   {
     data: [1, 1, 1, 1, 1],
     backgroundColor: [
        '#059669',
        '#FBBF24',
        '#FF5733',
        '#B91C1C',
        '#F3F4F6',
      ],
      rotation: 210,
      circumference: 300,
      cutout: "90%",
      borderRadius: Number.MAX_VALUE
   },
 ],
};

const PieChart = () => {
 return (
   <div className='flex-1'>
     <Doughnut data={data} className=''/>
   </div>
 );
};

export default PieChart;