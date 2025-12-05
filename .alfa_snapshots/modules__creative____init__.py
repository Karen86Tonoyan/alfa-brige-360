"""
ALFA_CORE / MODULES / CREATIVE LAYER
=====================================
Design & Web Publishing Pipeline
Servers: figma, webflow
"""

from typing import Dict, Any, Optional
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.mcp_dispatcher import get_dispatcher, MCPResponse


class CreativeLayer:
    """
    Creative Layer - Design & Web Publishing
    
    Integrates:
    - Figma: Design files, components, styles
    - Webflow: CMS, publishing, hosting
    """
    
    LAYER_NAME = "creative"
    
    def __init__(self):
        self.dispatcher = get_dispatcher()
    
    # -------------------------------------------------------------------------
    # FIGMA OPERATIONS
    # -------------------------------------------------------------------------
    
    async def figma_get_file(self, file_key: str) -> MCPResponse:
        """Get Figma file details."""
        return await self.dispatcher.execute(
            "figma",
            "figma/getFile",
            {"fileKey": file_key}
        )
    
    async def figma_get_components(self, file_key: str) -> MCPResponse:
        """Get components from Figma file."""
        return await self.dispatcher.execute(
            "figma",
            "figma/getComponents",
            {"fileKey": file_key}
        )
    
    async def figma_get_styles(self, file_key: str) -> MCPResponse:
        """Get styles from Figma file."""
        return await self.dispatcher.execute(
            "figma",
            "figma/getStyles",
            {"fileKey": file_key}
        )
    
    async def figma_export_image(
        self,
        file_key: str,
        node_id: str,
        format: str = "png",
        scale: float = 1.0
    ) -> MCPResponse:
        """Export image from Figma node."""
        return await self.dispatcher.execute(
            "figma",
            "figma/exportImage",
            {
                "fileKey": file_key,
                "nodeId": node_id,
                "format": format,
                "scale": scale
            }
        )
    
    # -------------------------------------------------------------------------
    # WEBFLOW OPERATIONS
    # -------------------------------------------------------------------------
    
    async def webflow_list_sites(self) -> MCPResponse:
        """List all Webflow sites."""
        return await self.dispatcher.execute(
            "webflow",
            "webflow/listSites",
            {}
        )
    
    async def webflow_get_site(self, site_id: str) -> MCPResponse:
        """Get Webflow site details."""
        return await self.dispatcher.execute(
            "webflow",
            "webflow/getSite",
            {"siteId": site_id}
        )
    
    async def webflow_list_collections(self, site_id: str) -> MCPResponse:
        """List CMS collections for a site."""
        return await self.dispatcher.execute(
            "webflow",
            "webflow/listCollections",
            {"siteId": site_id}
        )
    
    async def webflow_create_item(
        self,
        collection_id: str,
        fields: Dict[str, Any],
        publish: bool = False
    ) -> MCPResponse:
        """Create new CMS item."""
        return await self.dispatcher.execute(
            "webflow",
            "webflow/createItem",
            {
                "collectionId": collection_id,
                "fields": fields,
                "publish": publish
            }
        )
    
    async def webflow_publish_site(self, site_id: str, domains: Optional[list] = None) -> MCPResponse:
        """Publish Webflow site."""
        return await self.dispatcher.execute(
            "webflow",
            "webflow/publishSite",
            {
                "siteId": site_id,
                "domains": domains or []
            }
        )
    
    # -------------------------------------------------------------------------
    # CROSS-PLATFORM OPERATIONS
    # -------------------------------------------------------------------------
    
    async def design_to_web(
        self,
        figma_file_key: str,
        webflow_site_id: str,
        node_ids: list
    ) -> Dict[str, MCPResponse]:
        """
        Pipeline: Export from Figma → Import to Webflow
        """
        results = {}
        
        # Export images from Figma
        for node_id in node_ids:
            export = await self.figma_export_image(figma_file_key, node_id)
            results[f"figma_export_{node_id}"] = export
        
        # Get Webflow site info
        site = await self.webflow_get_site(webflow_site_id)
        results["webflow_site"] = site
        
        return results


# Quick API
_creative_layer: Optional[CreativeLayer] = None


def get_creative_layer() -> CreativeLayer:
    global _creative_layer
    if _creative_layer is None:
        _creative_layer = CreativeLayer()
    return _creative_layer
