#!/usr/bin/env python3
"""
☁️ ALFA CLOUD OFFLINE v1.0
Entry point: python -m alfa_cloud

100% lokalnie | 0% chmura publiczna | Pełna prywatność
"""

import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ALFA_CLOUD")


def print_banner():
    """Print startup banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     █████╗ ██╗     ███████╗ █████╗      ██████╗██╗      ║
    ║    ██╔══██╗██║     ██╔════╝██╔══██╗    ██╔════╝██║      ║
    ║    ███████║██║     █████╗  ███████║    ██║     ██║      ║
    ║    ██╔══██║██║     ██╔══╝  ██╔══██║    ██║     ██║      ║
    ║    ██║  ██║███████╗██║     ██║  ██║    ╚██████╗███████╗ ║
    ║    ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝     ╚═════╝╚══════╝ ║
    ║                                                               ║
    ║              ☁️  OFFLINE CLOUD v1.0  ☁️                       ║
    ║         100% Local | Zero Public Cloud | Full Privacy        ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


async def start_full():
    """Start full ALFA CLOUD system"""
    from alfa_cloud.api.server import start_server
    from alfa_cloud.core.cloud_engine import CloudEngine
    from alfa_cloud.core.sync_engine import SyncEngine
    
    logger.info("🚀 Starting ALFA CLOUD OFFLINE...")
    
    # Initialize engines
    cloud = CloudEngine()
    await cloud.start()
    
    sync = SyncEngine()
    await sync.start()
    
    # Start API server
    await start_server()


async def start_api_only():
    """Start only API server"""
    from alfa_cloud.api.server import start_server
    
    logger.info("🌐 Starting API server only...")
    await start_server()


async def start_sync_only():
    """Start only sync daemon"""
    from alfa_cloud.core.sync_engine import SyncEngine
    
    logger.info("🔄 Starting sync daemon only...")
    sync = SyncEngine()
    await sync.start()
    
    # Keep running
    while True:
        await asyncio.sleep(1)


def start_cli():
    """Start interactive CLI"""
    from alfa_cloud.agents.ai_agent import AIAgent
    import asyncio
    
    logger.info("💬 Starting interactive CLI...")
    
    agent = AIAgent()
    
    print("\n🤖 ALFA CLOUD CLI - Wpisz 'exit' aby wyjść\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ('exit', 'quit', 'q'):
                print("👋 Do widzenia!")
                break
            
            if not user_input:
                continue
            
            # Run async chat
            response = asyncio.get_event_loop().run_until_complete(
                agent.chat(user_input)
            )
            print(f"ALFA: {response}\n")
            
        except KeyboardInterrupt:
            print("\n👋 Do widzenia!")
            break
        except Exception as e:
            print(f"❌ Błąd: {e}")


async def check_health():
    """Check system health"""
    import httpx
    
    checks = {
        "Ollama": "http://127.0.0.1:11434/api/tags",
        "API": "http://127.0.0.1:8765/health",
    }
    
    print("\n🏥 ALFA CLOUD Health Check\n")
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in checks.items():
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    print(f"  ✅ {name}: OK")
                else:
                    print(f"  ⚠️ {name}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"  ❌ {name}: {type(e).__name__}")
    
    print()


def show_status():
    """Show system status"""
    import json
    
    config_path = Path(__file__).parent / "config" / "cloud_config.json"
    
    print("\n📊 ALFA CLOUD Status\n")
    
    if config_path.exists():
        config = json.loads(config_path.read_text())
        print(f"  📁 Storage: {config.get('storage', {}).get('base_path', 'N/A')}")
        print(f"  🔐 Encryption: {config.get('encryption', {}).get('algorithm', 'N/A')}")
        print(f"  🌐 API Port: {config.get('api', {}).get('port', 'N/A')}")
        print(f"  🤖 AI Model: {config.get('ai', {}).get('default_model', 'N/A')}")
    else:
        print("  ⚠️ Config not found")
    
    print()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="☁️ ALFA CLOUD OFFLINE v1.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m alfa_cloud                  # Start full system
  python -m alfa_cloud --mode api       # Start API only
  python -m alfa_cloud --mode sync      # Start sync only
  python -m alfa_cloud --mode cli       # Interactive CLI
  python -m alfa_cloud health           # Check health
  python -m alfa_cloud status           # Show status
        """
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        choices=["health", "status"],
        help="Command to run"
    )
    
    parser.add_argument(
        "--mode", "-m",
        choices=["full", "api", "sync", "cli"],
        default="full",
        help="Run mode (default: full)"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="API port (default: 8765)"
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="API host (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Don't show banner"
    )
    
    args = parser.parse_args()
    
    # Show banner
    if not args.no_banner:
        print_banner()
    
    # Handle commands
    if args.command == "health":
        asyncio.run(check_health())
        return
    
    if args.command == "status":
        show_status()
        return
    
    # Handle modes
    try:
        if args.mode == "full":
            asyncio.run(start_full())
        
        elif args.mode == "api":
            asyncio.run(start_api_only())
        
        elif args.mode == "sync":
            asyncio.run(start_sync_only())
        
        elif args.mode == "cli":
            start_cli()
    
    except KeyboardInterrupt:
        logger.info("👋 Shutting down ALFA CLOUD...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
