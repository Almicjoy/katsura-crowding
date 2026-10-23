import * as React from "react"
import Header from "./Header.js"
import Footer from "./Footer.js"

const Layout = ({ children }) => {
  return (
    <>
      <Header />
      <div className="">
        <main>{children}</main>
      </div>
      <Footer />
    </>
  )
}

export default Layout
