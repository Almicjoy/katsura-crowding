import * as React from 'react';

import Layout from "./layout"
import DisplayChart from "./DisplayChart"

const App = () => {
  return (
    <Layout>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.6.0/Chart.min.js"></script>
      <div className="grid grid-cols-1 md:grid-cols-5 p-4 md:py-24 md:px-8 gap-2 md:gap-16 lg:gap-24 items-end max-w-6xl mx-auto">
        <div className="col-span-5 relative grid grid-cols-1 gap-2 content-start">
          <DisplayChart/>
          <div className="flex gap-2">
            <a href="https://docs.google.com/forms/d/e/1FAIpQLScU2ZbhWCi0iWpxQf8SrkZn0OopxQ14FeHZs0MaDCwGQ1qmrg/viewform?usp=sf_link">
              <button className="bg-primary hover:bg-gray-600 text-white text-sm sm:text-md font-medium py-2 px-4 rounded-lg">
                Online survey →
              </button>
            </a>
            <a href="https://west2-univ.jp/sp/index.php?t=650120">
              <button className="hover:bg-gray-100 border-2 border-gray-200 text-primary text-sm sm:text-md font-medium py-2 px-4 rounded-lg">
                Today's menu →
              </button>
            </a>
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default App;