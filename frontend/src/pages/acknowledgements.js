import * as React from "react"

import Layout from "../components/layout"
import Seo from "../components/seo"

const Acknowledgements = () => (
  <Layout>
    <h1 className="max-w-6xl mx-auto md:text-4xl text-3xl text-black font-bold m-8 py-4 border-b-2">
      Acknowledgements
    </h1>
    <div className="grid max-w-6xl mx-auto gap-4">
      <p>
      (日本語) 本プロジェクトは、桂キャンパス実証研究促進ファンドの助成を受けたものです。ここに感謝の意を表します。また、株式会社社会システム総合研究所には、WiFiセンサーの運用にあたり、様々なサポートをいただきました。心より感謝申し上げます。
      </p>

      <ul>
        <li>
        株式会社社会システム総合研究所：https://www.jriss.jp/
        </li>
        <li>
        本プロジェクト動画：https://www.youtube.com/watch?v=5fvl1YeWqZE
        </li>
        <li>
        問い合わせメールアドレス：its-katsura-wifi@trans.kuciv.kyoto-u.ac.jp
        </li>
      </ul>

      <p className="mt-12">
      (English)
      This project was funded by ”Katsura Campus Empirical Research Promotion Fund".  We wish to express our deep appreciation for the financial support. We would also like to thank JRISS (Japan Research Institute for Social Systems) for their support in operating the Wi-Fi sensors. 
      </p>

      <ul>
        <li>
        JRISS: https://www.jriss.jp/
        </li>
        <li>
        Project movie: https://www.youtube.com/watch?v=5fvl1YeWqZE
        </li>
        <li>
        Contact e-mail for questions or comments: its-katsura-wifi@trans.kuciv.kyoto-u.ac.jp
        </li>
      </ul>
    </div>
  </Layout>
)

export const Head = () => <Seo title="Acknowledgements" />

export default Acknowledgements
