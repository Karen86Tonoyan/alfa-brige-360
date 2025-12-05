"""
ALFA_CORE / MODULES / AUTOMATION LAYER
=======================================
Data Processing & Web Scraping
Servers: apify, markitdown
"""

from typing import Dict, Any, Optional, List
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.mcp_dispatcher import get_dispatcher, MCPResponse


class AutomationLayer:
    """
    Automation Layer - Data Processing & Web Scraping
    
    Integrates:
    - Apify: Web scraping, automation workflows
    - Markitdown: Markdown parsing and transformation
    """
    
    LAYER_NAME = "automation"
    
    def __init__(self):
        self.dispatcher = get_dispatcher()
    
    # -------------------------------------------------------------------------
    # APIFY OPERATIONS
    # -------------------------------------------------------------------------
    
    async def apify_run_actor(
        self,
        actor_id: str,
        input_data: Dict[str, Any],
        memory_mb: int = 256,
        timeout_secs: int = 300
    ) -> MCPResponse:
        """
        Run an Apify actor.
        
        Args:
            actor_id: Actor ID (e.g., "apify/web-scraper")
            input_data: Actor input configuration
            memory_mb: Memory allocation
            timeout_secs: Execution timeout
        """
        return await self.dispatcher.execute(
            "apify",
            "apify/runActor",
            {
                "actorId": actor_id,
                "input": input_data,
                "memory": memory_mb,
                "timeout": timeout_secs
            }
        )
    
    async def apify_scrape_url(self, url: str, selector: Optional[str] = None) -> MCPResponse:
        """
        Quick web scraping using Apify.
        
        Args:
            url: URL to scrape
            selector: Optional CSS selector for specific content
        """
        input_data = {
            "startUrls": [{"url": url}],
            "pageFunction": """
                async function pageFunction(context) {
                    const { page, request } = context;
                    const title = await page.title();
                    const content = await page.$eval('body', el => el.innerText);
                    return { url: request.url, title, content };
                }
            """
        }
        
        if selector:
            input_data["pageFunction"] = f"""
                async function pageFunction(context) {{
                    const {{ page, request }} = context;
                    const content = await page.$eval('{selector}', el => el.innerText);
                    return {{ url: request.url, content }};
                }}
            """
        
        return await self.apify_run_actor("apify/web-scraper", input_data)
    
    async def apify_get_dataset(self, dataset_id: str, format: str = "json") -> MCPResponse:
        """Get results from Apify dataset."""
        return await self.dispatcher.execute(
            "apify",
            "apify/getDataset",
            {
                "datasetId": dataset_id,
                "format": format
            }
        )
    
    async def apify_list_actors(self) -> MCPResponse:
        """List available Apify actors."""
        return await self.dispatcher.execute(
            "apify",
            "apify/listActors",
            {}
        )
    
    # -------------------------------------------------------------------------
    # MARKITDOWN OPERATIONS
    # -------------------------------------------------------------------------
    
    async def markdown_convert(self, content: str, from_format: str = "html") -> MCPResponse:
        """
        Convert content to Markdown.
        
        Args:
            content: Source content
            from_format: Source format (html, docx, pdf, etc.)
        """
        return await self.dispatcher.execute(
            "markitdown",
            "markitdown/convert",
            {
                "content": content,
                "fromFormat": from_format
            }
        )
    
    async def markdown_parse(self, markdown: str) -> MCPResponse:
        """Parse Markdown and extract structure."""
        return await self.dispatcher.execute(
            "markitdown",
            "markitdown/parse",
            {"markdown": markdown}
        )
    
    async def markdown_transform(
        self,
        markdown: str,
        transformations: List[str]
    ) -> MCPResponse:
        """
        Apply transformations to Markdown.
        
        Args:
            markdown: Source Markdown
            transformations: List of transformations (e.g., ["removeImages", "extractLinks"])
        """
        return await self.dispatcher.execute(
            "markitdown",
            "markitdown/transform",
            {
                "markdown": markdown,
                "transformations": transformations
            }
        )
    
    async def markdown_extract_code(self, markdown: str, language: Optional[str] = None) -> MCPResponse:
        """Extract code blocks from Markdown."""
        params = {"markdown": markdown}
        if language:
            params["language"] = language
        
        return await self.dispatcher.execute(
            "markitdown",
            "markitdown/extractCode",
            params
        )
    
    # -------------------------------------------------------------------------
    # PIPELINES
    # -------------------------------------------------------------------------
    
    async def scrape_and_convert(self, url: str, output_format: str = "markdown") -> Dict[str, MCPResponse]:
        """
        Pipeline: Scrape URL → Convert to Markdown
        """
        results = {}
        
        # Scrape the URL
        scrape = await self.apify_scrape_url(url)
        results["scrape"] = scrape
        
        if scrape.success and scrape.result:
            # Convert to Markdown
            content = scrape.result.get("content", "")
            convert = await self.markdown_convert(content, "html")
            results["convert"] = convert
        
        return results
    
    async def batch_scrape(
        self,
        urls: List[str],
        convert_to_markdown: bool = True
    ) -> Dict[str, Any]:
        """
        Batch scrape multiple URLs.
        
        Args:
            urls: List of URLs to scrape
            convert_to_markdown: Whether to convert results to Markdown
        """
        results = {"urls": [], "errors": []}
        
        for url in urls:
            try:
                if convert_to_markdown:
                    result = await self.scrape_and_convert(url)
                else:
                    result = {"scrape": await self.apify_scrape_url(url)}
                
                results["urls"].append({
                    "url": url,
                    "status": "success",
                    "data": result
                })
            except Exception as e:
                results["errors"].append({
                    "url": url,
                    "error": str(e)
                })
        
        return results


# Quick API
_automation_layer: Optional[AutomationLayer] = None


def get_automation_layer() -> AutomationLayer:
    global _automation_layer
    if _automation_layer is None:
        _automation_layer = AutomationLayer()
    return _automation_layer


async def scrape(url: str) -> MCPResponse:
    """Quick URL scrape."""
    layer = get_automation_layer()
    return await layer.apify_scrape_url(url)


async def to_markdown(content: str, from_format: str = "html") -> MCPResponse:
    """Quick conversion to Markdown."""
    layer = get_automation_layer()
    return await layer.markdown_convert(content, from_format)
