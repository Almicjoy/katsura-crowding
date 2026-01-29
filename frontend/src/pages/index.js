import * as React from "react"
import Seo from "../components/seo"

import App from '../components/App';

const IndexPage = () => (
  <App />
)

/**
 * Head export to define metadata for the page
 *
 * See: https://www.gatsbyjs.com/docs/reference/built-in-components/gatsby-head/
 */
export const Head = () => <Seo title="Home" />

export default IndexPage
