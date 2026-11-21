export function About() {
  return (
    <section className="about page-section" aria-labelledby="about-title">
      <header className="page-heading">
        <div>
          <h1 id="about-title">About the system</h1>
          <p>Different ways to find financial information.</p>
        </div>
      </header>
      <div className="about-intro">
        <div>
          <h2>One corpus. Five perspectives.</h2>
          <p>
            FiQA is a university information retrieval project using the BEIR
            financial dataset. It retrieves existing English documents; it does
            not generate answers or financial advice.
          </p>
        </div>
        <dl className="corpus-counts">
          <div>
            <dt>Corpus documents</dt>
            <dd>57,638</dd>
          </div>
          <div>
            <dt>BGE vectors</dt>
            <dd>57,600</dd>
          </div>
        </dl>
      </div>
      <p className="muted">
        The 38 empty documents are excluded from the semantic index. Searches
        use the complete backend indexes without downloading the corpus to your
        browser.
      </p>
      <dl className="techniques">
        <div>
          <dt>Jaccard</dt>
          <dd>Overlap between sets of unique terms.</dd>
        </div>
        <div>
          <dt>TF-IDF</dt>
          <dd>Term weighting and cosine similarity.</dd>
        </div>
        <div>
          <dt>BM25</dt>
          <dd>Term frequency, rarity and document length.</dd>
        </div>
        <div>
          <dt>BGE + FAISS</dt>
          <dd>BAAI/bge-base-en-v1.5 embeddings with exact vector search.</dd>
        </div>
        <div>
          <dt>Hybrid BM25 + BGE</dt>
          <dd>
            RRF fusion of lexical and semantic rankings. This is the model used
            by Automatic.
          </dd>
        </div>
      </dl>
      <div className="about-bottom">
        <h2>From evaluation to search</h2>
        <p>
          The service uses Snowball with BM25 k1=0.8 and b=0.75. Parameters were
          selected on 500 validation queries before checking them on 648 test
          queries. The BGE embeddings and FAISS index remain unchanged.
        </p>
        <p>
          Automatic selects the final hybrid model; it is not a sixth algorithm.
          It does not switch algorithms based on your text or estimate relevance
          for a free-text query.
        </p>
      </div>
    </section>
  );
}
