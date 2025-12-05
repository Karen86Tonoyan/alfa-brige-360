"""
ALFA_CORE / MODULES / KNOWLEDGE LAYER
======================================
Documentation & Knowledge Base
Servers: deepwiki, microsoft-docs
"""

from typing import Dict, Any, Optional, List
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.mcp_dispatcher import get_dispatcher, MCPResponse


class KnowledgeLayer:
    """
    Knowledge Layer - Documentation & Knowledge Base
    
    Integrates:
    - DeepWiki: GitHub repo documentation, SSE streaming
    - Microsoft Docs: Official Microsoft Learn documentation
    """
    
    LAYER_NAME = "knowledge"
    
    def __init__(self):
        self.dispatcher = get_dispatcher()
    
    # -------------------------------------------------------------------------
    # DEEPWIKI OPERATIONS
    # -------------------------------------------------------------------------
    
    async def wiki_ask(self, repo: str, question: str) -> MCPResponse:
        """
        Ask a question about a GitHub repository.
        
        Args:
            repo: GitHub repo in format "owner/repo" (e.g., "facebook/react")
            question: Natural language question
        """
        return await self.dispatcher.execute(
            "deepwiki",
            "deepwiki/askQuestion",
            {
                "repoName": repo,
                "question": question
            }
        )
    
    async def wiki_structure(self, repo: str) -> MCPResponse:
        """Get documentation structure for a GitHub repo."""
        return await self.dispatcher.execute(
            "deepwiki",
            "deepwiki/readWikiStructure",
            {"repoName": repo}
        )
    
    async def wiki_contents(self, repo: str) -> MCPResponse:
        """Get full documentation contents for a GitHub repo."""
        return await self.dispatcher.execute(
            "deepwiki",
            "deepwiki/readWikiContents",
            {"repoName": repo}
        )
    
    # -------------------------------------------------------------------------
    # MICROSOFT DOCS OPERATIONS
    # -------------------------------------------------------------------------
    
    async def ms_search(self, query: str) -> MCPResponse:
        """
        Search Microsoft Learn documentation.
        Returns up to 10 high-quality content chunks.
        """
        return await self.dispatcher.execute(
            "microsoft-docs",
            "microsoft/docsSearch",
            {"query": query}
        )
    
    async def ms_fetch(self, url: str) -> MCPResponse:
        """
        Fetch full Microsoft documentation page.
        Returns complete markdown content.
        """
        return await self.dispatcher.execute(
            "microsoft-docs",
            "microsoft/docsFetch",
            {"url": url}
        )
    
    async def ms_code_samples(self, query: str, language: Optional[str] = None) -> MCPResponse:
        """
        Search for code samples in Microsoft docs.
        
        Args:
            query: Search query
            language: Optional filter (python, csharp, typescript, etc.)
        """
        params = {"query": query}
        if language:
            params["language"] = language
        
        return await self.dispatcher.execute(
            "microsoft-docs",
            "microsoft/codeSampleSearch",
            params
        )
    
    # -------------------------------------------------------------------------
    # UNIFIED SEARCH
    # -------------------------------------------------------------------------
    
    async def search_all(self, query: str, sources: Optional[List[str]] = None) -> Dict[str, MCPResponse]:
        """
        Search across all knowledge sources.
        
        Args:
            query: Search query
            sources: Optional list of sources to search (default: all)
        """
        sources = sources or ["deepwiki", "microsoft-docs"]
        results = {}
        
        if "microsoft-docs" in sources:
            results["microsoft"] = await self.ms_search(query)
        
        # DeepWiki requires a repo, so we skip it for general search
        # unless query contains repo reference
        
        return results
    
    async def get_repo_docs(self, repo: str) -> Dict[str, MCPResponse]:
        """
        Get complete documentation for a GitHub repository.
        Combines structure and contents.
        """
        structure = await self.wiki_structure(repo)
        contents = await self.wiki_contents(repo)
        
        return {
            "structure": structure,
            "contents": contents
        }
    
    async def research_topic(
        self,
        topic: str,
        repo: Optional[str] = None,
        include_code: bool = True
    ) -> Dict[str, Any]:
        """
        Comprehensive research on a topic.
        Queries multiple sources and aggregates results.
        """
        results = {
            "topic": topic,
            "sources": {}
        }
        
        # Search Microsoft docs
        ms_docs = await self.ms_search(topic)
        results["sources"]["microsoft_docs"] = ms_docs
        
        if include_code:
            ms_code = await self.ms_code_samples(topic)
            results["sources"]["microsoft_code"] = ms_code
        
        # If repo provided, query DeepWiki
        if repo:
            wiki = await self.wiki_ask(repo, f"Explain {topic}")
            results["sources"]["deepwiki"] = wiki
        
        return results


# Quick API
_knowledge_layer: Optional[KnowledgeLayer] = None


def get_knowledge_layer() -> KnowledgeLayer:
    global _knowledge_layer
    if _knowledge_layer is None:
        _knowledge_layer = KnowledgeLayer()
    return _knowledge_layer


async def ask_docs(query: str) -> MCPResponse:
    """Quick search across knowledge sources."""
    layer = get_knowledge_layer()
    return await layer.ms_search(query)


async def ask_repo(repo: str, question: str) -> MCPResponse:
    """Quick question about a GitHub repo."""
    layer = get_knowledge_layer()
    return await layer.wiki_ask(repo, question)
