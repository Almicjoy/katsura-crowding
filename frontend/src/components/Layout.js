import * as React from "react"
import Header from "./Header.js"
import Footer from "./Footer.js"

const Layout = ({ children }) => {
  return (
    <body className="">
      <Header />
      <div className="">
        <main>{children}</main>
      </div>
      <Footer />
    </body>
  )
}

export default Layout
