"""Summary Agent
- Chunks content, embeds, stores/retrieves from Pinecone, and summarizes.
- Placeholder code; integrate LangChain + Pinecone later.
"""

from typing import List, Dict


def summarize_search_results(search_results: List[Dict]) -> List[Dict]:
    """Produce RAG-based summaries with citations for each sub-question.
    Returns list of summaries per sub-question.
    """
    summaries = []
    for sr in search_results:
        summaries.append({
            "sub_question": sr.get("sub_question"),
            "summary": "This is a placeholder summary.",
            "citations": [s.get("url") for s in sr.get("sources", [])],
        })
    return summaries
