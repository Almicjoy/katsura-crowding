import * as React from "react"
import { Link } from "gatsby"
import itslablogo from "/src/images/its-lab-logo.png"

const Footer = () => {
  return (
    <body className="relative bg-white max-w-6xl mx-auto p-4 md:p-8 mt-32">
      <main className="grid gap-2 text-sm sm:text-base pt-6 border-t-2 mx-auto">
        <div className="flex justify-between mx-auto">
          <img
            className="flex h-16"
            src={itslablogo}
            alt="Logo"
          />
        </div>
        <div className="mx-auto">
          <p className="text-center">Katsura Campus Crowding Research by ITS Lab, Kyoto University. </p>
          <div className="flex gap-2">
            <p className="text-center">© {new Date().getFullYear()} ITS Lab.</p>
            <Link to="/acknowledgements" className="text-center">Acknowledgments.</Link>
          </div>
        </div>
        
        
      </main>
    </body>
  )
}

export default Footer
