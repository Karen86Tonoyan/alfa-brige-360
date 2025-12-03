"""
ALFA_CORE / MODULES / DEV LAYER
================================
Local Developer Tools
Servers: idl-vscode, pylance
"""

from typing import Dict, Any, Optional, List
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.mcp_dispatcher import get_dispatcher, MCPResponse


class DevLayer:
    """
    Dev Layer - Local Developer Tools
    
    Integrates:
    - IDL for VS Code: Live streaming events, data analysis
    - Pylance: Python language server, type checking
    """
    
    LAYER_NAME = "dev"
    
    def __init__(self):
        self.dispatcher = get_dispatcher()
    
    # -------------------------------------------------------------------------
    # IDL FOR VSCODE OPERATIONS
    # -------------------------------------------------------------------------
    
    async def idl_start(self, headless: bool = False) -> MCPResponse:
        """Start IDL session."""
        return await self.dispatcher.execute(
            "idl-vscode",
            "idl/start",
            {"headless": headless}
        )
    
    async def idl_execute_code(self, code: str) -> MCPResponse:
        """Execute IDL code snippet."""
        return await self.dispatcher.execute(
            "idl-vscode",
            "idl/executeCode",
            {"code": code}
        )
    
    async def idl_execute_file(self, file_path: str) -> MCPResponse:
        """Execute IDL file."""
        return await self.dispatcher.execute(
            "idl-vscode",
            "idl/executeFile",
            {"uri": file_path}
        )
    
    async def idl_create_notebook(
        self,
        file_path: str,
        cells: List[Dict[str, str]]
    ) -> MCPResponse:
        """
        Create IDL notebook.
        
        Args:
            file_path: Path for the notebook (.idlnb)
            cells: List of cells [{"type": "code"|"markdown", "content": "..."}]
        """
        return await self.dispatcher.execute(
            "idl-vscode",
            "idl/createNotebook",
            {
                "uri": file_path,
                "cells": cells
            }
        )
    
    async def idl_open_in_envi(self, file_path: str) -> MCPResponse:
        """Open image in ENVI."""
        return await self.dispatcher.execute(
            "idl-vscode",
            "idl/openInEnvi",
            {"uri": file_path}
        )
    
    # -------------------------------------------------------------------------
    # PYLANCE OPERATIONS
    # -------------------------------------------------------------------------
    
    async def pylance_check_syntax(self, file_path: str, workspace_root: str) -> MCPResponse:
        """Check Python file for syntax errors."""
        return await self.dispatcher.execute(
            "pylance",
            "pylance/fileSyntaxErrors",
            {
                "fileUri": file_path,
                "workspaceRoot": workspace_root
            }
        )
    
    async def pylance_validate_code(self, code: str, python_version: str = "3.11") -> MCPResponse:
        """Validate Python code snippet."""
        return await self.dispatcher.execute(
            "pylance",
            "pylance/syntaxErrors",
            {
                "code": code,
                "pythonVersion": python_version
            }
        )
    
    async def pylance_run_snippet(
        self,
        code: str,
        workspace_root: str,
        working_dir: Optional[str] = None,
        timeout: int = 30
    ) -> MCPResponse:
        """
        Run Python code snippet directly.
        Uses the correct Python interpreter for the workspace.
        """
        params = {
            "codeSnippet": code,
            "workspaceRoot": workspace_root,
            "timeout": timeout
        }
        if working_dir:
            params["workingDirectory"] = working_dir
        
        return await self.dispatcher.execute(
            "pylance",
            "pylance/runCodeSnippet",
            params
        )
    
    async def pylance_get_imports(self, workspace_root: str) -> MCPResponse:
        """Analyze imports across workspace."""
        return await self.dispatcher.execute(
            "pylance",
            "pylance/imports",
            {"workspaceRoot": workspace_root}
        )
    
    async def pylance_get_environments(self, workspace_root: str) -> MCPResponse:
        """Get Python environments for workspace."""
        return await self.dispatcher.execute(
            "pylance",
            "pylance/pythonEnvironments",
            {"workspaceRoot": workspace_root}
        )
    
    async def pylance_refactor(
        self,
        file_path: str,
        refactoring: str,
        mode: str = "update"
    ) -> MCPResponse:
        """
        Apply refactoring to Python file.
        
        Args:
            file_path: File to refactor
            refactoring: Type (source.unusedImports, source.convertImportFormat, source.fixAll.pylance)
            mode: "update" (apply), "edits" (preview), "string" (return content)
        """
        return await self.dispatcher.execute(
            "pylance",
            "pylance/invokeRefactoring",
            {
                "fileUri": file_path,
                "name": refactoring,
                "mode": mode
            }
        )
    
    async def pylance_remove_unused_imports(self, file_path: str) -> MCPResponse:
        """Remove unused imports from Python file."""
        return await self.pylance_refactor(file_path, "source.unusedImports", "update")
    
    async def pylance_fix_all(self, file_path: str) -> MCPResponse:
        """Apply all available fixes to Python file."""
        return await self.pylance_refactor(file_path, "source.fixAll.pylance", "update")
    
    # -------------------------------------------------------------------------
    # COMBINED OPERATIONS
    # -------------------------------------------------------------------------
    
    async def validate_project(self, workspace_root: str) -> Dict[str, Any]:
        """
        Validate entire Python project.
        Checks syntax, imports, and environments.
        """
        results = {}
        
        # Get environments
        envs = await self.pylance_get_environments(workspace_root)
        results["environments"] = envs
        
        # Get imports
        imports = await self.pylance_get_imports(workspace_root)
        results["imports"] = imports
        
        return results
    
    async def quick_run_python(self, code: str) -> MCPResponse:
        """Quick Python code execution."""
        # Determine workspace root from current directory
        import os
        workspace = os.getcwd()
        return await self.pylance_run_snippet(code, workspace)


# Quick API
_dev_layer: Optional[DevLayer] = None


def get_dev_layer() -> DevLayer:
    global _dev_layer
    if _dev_layer is None:
        _dev_layer = DevLayer()
    return _dev_layer


async def run_python(code: str) -> MCPResponse:
    """Quick Python execution."""
    layer = get_dev_layer()
    return await layer.quick_run_python(code)


async def check_python(code: str) -> MCPResponse:
    """Quick Python syntax check."""
    layer = get_dev_layer()
    return await layer.pylance_validate_code(code)
