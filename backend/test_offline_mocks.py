import os
import sys
import json
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

class MockChatCompletions:
    def create(self, *args, **kwargs) -> Any:
        messages = kwargs.get("messages", [])
        prompt = ""
        for m in messages:
            prompt += m.get("content", "") + "\n"

        # Determine agent type from prompt
        if "sub_questions" in prompt or "sub-questions" in prompt:
            if "expert" in prompt.lower() or " 6 " in prompt:
                content = json.dumps({
                    "sub_questions": [
                        "Impact Question 1", "Impact Question 2", "Impact Question 3",
                        "Impact Question 4", "Impact Question 5", "Impact Question 6"
                    ]
                })
            else:
                content = json.dumps({
                    "sub_questions": [
                        "What are the primary impacts of the research topic?",
                        "What scientific evidence supports these findings?",
                        "What are the future predictions for this topic?"
                    ]
                })
        elif "executive_summary" in prompt or "detailed_analysis" in prompt:
            content = json.dumps({
                "title": "Comprehensive E2E Analysis Report and Diagnostic Frameworks",
                "executive_summary": "This comprehensive research report provides a detailed overview and in-depth assessment of the primary findings from recent clinical trials. Recent scientific evidence shows a 25% increase in operational efficiency across clinics that deployed the latest AI diagnostics frameworks, significantly improving patient throughput and outcomes [Source: https://academic-journal.org/impact]. However, substantial implementation challenges exist for this technology, including high initial deployment costs, database compatibility issues with legacy electronic health record systems, and intensive training requirements for healthcare professionals [Source: https://global-news.com/solutions].",
                "key_findings": [
                    {
                        "point": "Recent scientific evidence shows a 25% increase in clinic operational efficiency.",
                        "citation": "https://academic-journal.org/impact",
                        "status": "verified"
                    },
                    {
                        "point": "Substantial implementation challenges exist, including legacy system integration.",
                        "citation": "https://global-news.com/solutions",
                        "status": "verified"
                    },
                    {
                        "point": "Global adoption of diagnostic frameworks requires international policy alignment.",
                        "citation": "https://global-news.com/solutions",
                        "status": "verified"
                    }
                ],
                "detailed_analysis": "The detailed analysis explores the technical design, architectural patterns, and metrics observed across clinical implementations. First, clinic diagnostic range efficiency shows a 25% improvement when utilizing deep convolutional networks. Second, integration complexity remains a major barrier because legacy databases utilize outdated formatting structures, which necessitates standardized data-interoperability frameworks. Third, medical staff training is essential to reduce diagnostic error rates. Multiple paradigms of clinical trials and implementation studies have been reviewed in existing literature. We conclude that standardized API layers can alleviate many data validation problems. Future work should focus on federated learning to preserve privacy across hospitals. Additionally, our investigation reveals that clinical institutions utilizing AI-driven assistance experienced an average reduction of 15% in patient throughput bottlenecks. This demonstrates that technology-driven operational interventions have a systemic benefit. Finally, future iterations must account for regional differences in policy guidelines to ensure cross-border compatibility and compliance with international standards.",
                "limitations": "The current dataset is restricted to observations over a short timeframe, and the study does not cover the long-term maintenance costs of hardware. The confidence score of 60% reflects minor uncertainties in early clinical trial numbers and lack of historic multi-year diagnostic performance metrics.",
                "conclusion": "The diagnostic technology shows immense promise for modern clinical practice. Resolving the identified regulatory and standardization challenges will pave the way for mainstream adoption globally. We recommend establishing a cross-functional task force to oversee the transition phase and coordinate between vendors and staff."
            })
        elif "summary" in prompt:
            content = json.dumps({
                "summary": "Recent scientific evidence shows a 25% increase in efficiency. However, there are substantial implementation challenges [Source: https://academic-journal.org/impact]. Experts suggest policy intervention is needed [Source: https://global-news.com/solutions].",
                "citations": ["https://academic-journal.org/impact", "https://global-news.com/solutions"]
            })
        elif "verifiable statement" in prompt or "claim extraction" in prompt or "claims" in prompt:
            content = json.dumps([
                "Recent scientific evidence shows a 25% increase in efficiency",
                "Substantial implementation challenges exist for this technology"
            ])
        elif "fact-checking" in prompt or "factcheck" in prompt:
            # Factcheck verification output format
            content = json.dumps([
                {
                    "claim": "Recent scientific evidence shows a 25% increase in efficiency",
                    "status": "verified",
                    "reasoning": "Multiple sources confirm efficiency gains around 20-30%.",
                    "sources": ["https://academic-journal.org/impact"]
                },
                {
                    "claim": "Substantial implementation challenges exist for this technology",
                    "status": "verified",
                    "reasoning": "Reports identify regulatory and financial hurdles.",
                    "sources": ["https://global-news.com/solutions"]
                }
            ])
        elif "followup" in prompt or "followup_questions" in prompt:
            content = json.dumps({
                "followup_questions": [
                    "What are the long-term cost benefits of this technology?",
                    "How does this impact regulatory compliance guidelines?",
                    "What are the secondary environmental factors?",
                    "Who are the key industry players driving this forward?",
                    "What is the expected timeline for mainstream adoption?"
                ]
            })
        else:
            content = "{}"

        mock_choice = MagicMock()
        mock_choice.message.content = content
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        return mock_response


class MockEmbeddings:
    def create(self, *args, **kwargs) -> Any:
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        return mock_response


class MockPineconeIndex:
    def __init__(self):
        self.vectors = {}
    def upsert(self, vectors):
        for vec in vectors:
            if isinstance(vec, tuple):
                self.vectors[vec[0]] = {
                    "id": vec[0],
                    "values": vec[1],
                    "metadata": vec[2]
                }
            else:
                self.vectors[vec.get("id")] = vec
        return len(vectors)
    def query(self, vector, top_k=5, include_metadata=True, filter=None):
        matches = []
        report_id = filter.get("report_id", {}).get("$eq") if filter else None
        for vid, vec in self.vectors.items():
            if report_id and vec.get("metadata", {}).get("report_id") != report_id:
                continue
            matches.append({
                "id": vid,
                "score": 0.9,
                "metadata": vec.get("metadata", {})
            })
        
        # Fallback if no vectors saved
        if not matches:
            matches = [
                {
                    "id": f"mock_match_{i}",
                    "score": 0.85,
                    "metadata": {
                        "content": f"Mock stored vector content chunk {i} discussing research topic details.",
                        "source_url": "https://academic-journal.org/impact" if i % 2 == 0 else "https://global-news.com/solutions",
                        "source_title": "Academic Journal" if i % 2 == 0 else "Global News",
                        "sub_question": "Primary impacts of research?",
                        "report_id": report_id,
                        "credibility_rating": "Academic" if i % 2 == 0 else "News",
                        "credibility_score": 90 if i % 2 == 0 else 80,
                        "credibility_label": "High Credibility",
                        "credibility_color": "green",
                        "credibility_emoji": "🎓"
                    }
                }
                for i in range(top_k)
            ]
        return {"matches": matches}
    def delete(self, filter=None):
        pass
    def describe_index_stats(self):
        return {
            "total_vector_count": len(self.vectors),
            "namespaces": {},
            "totalVectors": len(self.vectors)
        }

_MOCK_PINECONE_INDEX = MockPineconeIndex()

def mock_search_tavily(query: str, max_results: int = 4, search_depth: str = "basic") -> List[Dict[str, Any]]:
    h = sum(ord(c) for c in query) % 100
    return [
        {
            "url": f"https://academic-journal.org/impact-{h}-{i}" if i % 2 == 0 else f"https://global-news.com/solutions-{h}-{i}",
            "title": f"Academic study on {query[:20]}" if i % 2 == 0 else f"Global analysis of {query[:20]}",
            "content": f"This is high credibility content for search result {i} supporting scientific facts. We observe key metrics regarding {query}.",
            "score": 0.90 - (i * 0.05)
        }
        for i in range(max_results)
    ]


def is_openai_key_valid() -> bool:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or any(placeholder in api_key.lower() for placeholder in ["replace_with", "your_", "sk-proj-FjFXybv"]):
        # The project template uses 'sk-proj-FjFXybv...' as a placeholder
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        client.models.list()
        return True
    except Exception:
        return False


def patch_if_offline():
    """Determine if offline/key invalid, and apply global mocks dynamically."""
    if not is_openai_key_valid():
        print("⚠️  OpenAI API key is missing or invalid. Activating high-fidelity MOCK mode for E2E tests.")
        
        # 1. Patch OpenAI completions and embeddings
        patchers = [
            patch("openai.resources.chat.completions.Completions.create", new=MockChatCompletions().create),
            patch("openai.resources.embeddings.Embeddings.create", new=MockEmbeddings().create),
            # 2. Patch Pinecone
            patch("tools.pinecone_tool.get_pinecone_index", return_value=_MOCK_PINECONE_INDEX),
            # 3. Patch Tavily
            patch("tools.tavily_tool.search", new=mock_search_tavily)
        ]
        
        for p in patchers:
            p.start()
        
        # Pre-populate index stats mock return values
        import tools.pinecone_tool
        tools.pinecone_tool.get_index_stats = lambda: {
            "status": "Ready",
            "index_name": "research-chunks",
            "total_vectors": len(_MOCK_PINECONE_INDEX.vectors)
        }
    else:
        print("✅ OpenAI API key is valid. Running real end-to-end tests.")
