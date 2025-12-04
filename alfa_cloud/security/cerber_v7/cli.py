# ═══════════════════════════════════════════════════════════════════════════
# CERBER V7 CLI - Command-Line Interface for Security Operations
# ═══════════════════════════════════════════════════════════════════════════
"""
Cerber v7 CLI: Command-line tools for security management.

Usage:
    python -m cerber_v7 status
    python -m cerber_v7 start
    python -m cerber_v7 scan
    python -m cerber_v7 evidence capture
    python -m cerber_v7 report
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .manager import SecurityManager


def print_banner() -> None:
    """Print Cerber banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║  ██████╗███████╗██████╗ ██████╗ ███████╗██████╗     ██╗   ██╗ ║
║ ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗    ██║   ██║ ║
║ ██║     █████╗  ██████╔╝██████╔╝█████╗  ██████╔╝    ██║   ██║ ║
║ ██║     ██╔══╝  ██╔══██╗██╔══██╗██╔══╝  ██╔══██╗    ╚██╗ ██╔╝ ║
║ ╚██████╗███████╗██║  ██║██████╔╝███████╗██║  ██║     ╚████╔╝  ║
║  ╚═════╝╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝      ╚═══╝   ║
║                                                                ║
║     🛡️ ALFA CLOUD SECURITY - Post-Quantum Protection 🛡️       ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_status(security: SecurityManager) -> None:
    """Print security status."""
    status = security.get_status()
    
    print("\n📊 SECURITY STATUS")
    print("=" * 50)
    print(f"Running: {'✅ YES' if status['running'] else '❌ NO'}")
    print(f"Timestamp: {status['timestamp']}")
    
    print("\n🔧 COMPONENTS:")
    for name, info in status["components"].items():
        active = info.get("active", info.get("keypair_loaded", False))
        icon = "✅" if active else "⏸️"
        print(f"  {icon} {name.upper()}")
        for key, value in info.items():
            if key != "active":
                print(f"      └── {key}: {value}")
    
    if status["recent_alerts"]:
        print("\n🚨 RECENT ALERTS:")
        for alert in status["recent_alerts"]:
            print(f"  [{alert['severity']}] {alert['message']}")
    
    if status["recent_captures"]:
        print("\n🪤 RECENT CAPTURES:")
        for capture in status["recent_captures"]:
            print(f"  [{capture['payload_type']}] {capture.get('source', 'unknown')}")


def print_decoys(security: SecurityManager) -> None:
    """Print decoy status."""
    decoys = security.get_decoy_status()
    
    print("\n🪤 DECOY STATUS")
    print("=" * 50)
    
    if not decoys:
        print("  No decoys deployed")
        return
    
    for decoy in decoys:
        touched = "🔴 TOUCHED" if decoy.get("touched") else "🟢 UNTOUCHED"
        print(f"  [{decoy['type']}] {decoy['path']}")
        print(f"      └── Status: {touched}")


def cmd_status(args: argparse.Namespace) -> None:
    """Status command."""
    security = SecurityManager()
    print_status(security)


def cmd_start(args: argparse.Namespace) -> None:
    """Start command."""
    print_banner()
    security = SecurityManager()
    security.start()
    
    print("\n🛡️ Security system started")
    print_status(security)
    
    if args.watch:
        print("\n👁️ Watching for threats... (Ctrl+C to stop)")
        try:
            import time
            while True:
                time.sleep(60)
                print_status(security)
        except KeyboardInterrupt:
            security.stop()
            print("\n🛡️ Security system stopped")


def cmd_stop(args: argparse.Namespace) -> None:
    """Stop command."""
    security = SecurityManager()
    security.stop()
    print("🛡️ Security system stopped")


def cmd_scan(args: argparse.Namespace) -> None:
    """Scan command."""
    security = SecurityManager()
    security.start()
    
    print("\n🔍 SECURITY SCAN")
    print("=" * 50)
    
    # Let Guardian run a scan
    import time
    time.sleep(2)
    
    alerts = security.get_alerts()
    
    if not alerts:
        print("✅ No threats detected")
    else:
        print(f"🚨 Found {len(alerts)} potential issues:")
        for alert in alerts:
            icon = "🔴" if alert["severity"] == "critical" else "🟠" if alert["severity"] == "high" else "🟡"
            print(f"  {icon} [{alert['category']}] {alert['message']}")
    
    security.stop()


def cmd_evidence(args: argparse.Namespace) -> None:
    """Evidence command."""
    security = SecurityManager()
    
    if args.action == "capture":
        print("\n📸 CAPTURING EVIDENCE...")
        bundle = security.capture_evidence()
        print(f"✅ Evidence captured: {bundle.id}")
        print(f"   Files: {len(bundle.artifacts)}")
        print(f"   Path: {bundle.path if hasattr(bundle, 'path') else 'N/A'}")
    
    elif args.action == "list":
        evidence_dir = security.base_dir / "evidence"
        if not evidence_dir.exists():
            print("No evidence collected")
            return
        
        print("\n📂 EVIDENCE BUNDLES:")
        for bundle_dir in sorted(evidence_dir.glob("bundle_*")):
            print(f"  📦 {bundle_dir.name}")


def cmd_report(args: argparse.Namespace) -> None:
    """Report command."""
    security = SecurityManager()
    
    output_path = Path(args.output) if args.output else None
    report_path = security.export_security_report(output_path)
    
    print(f"\n📄 Security report generated: {report_path}")
    
    if args.view:
        report = json.loads(report_path.read_text())
        print("\n" + json.dumps(report, indent=2))


def cmd_decoys(args: argparse.Namespace) -> None:
    """Decoys command."""
    security = SecurityManager()
    
    if args.action == "status":
        print_decoys(security)
    
    elif args.action == "deploy":
        if not security._running:
            security.start()
        print("🪤 Decoys deployed")
        print_decoys(security)
    
    elif args.action == "honeypot":
        port = args.port or 4040
        security.start()
        security.start_honeypot(port=port)
        print(f"🪤 Honeypot started on port {port}")
        
        try:
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            security.stop()


def cmd_keygen(args: argparse.Namespace) -> None:
    """Generate PQ keypair."""
    from .pqxhybrid import generate_keypair
    
    scheme = args.scheme or "falcon"
    
    print(f"\n🔑 Generating {scheme.upper()} keypair...")
    keypair = generate_keypair(scheme)
    
    output_path = Path(args.output) if args.output else Path(f"{scheme}_keypair.json")
    output_path.write_text(json.dumps(keypair.to_dict(), indent=2))
    
    print(f"✅ Keypair saved: {output_path}")
    print(f"   Scheme: {keypair.scheme}")
    print(f"   Public key: {len(keypair.public_key)} bytes")
    print(f"   Secret key: {len(keypair.secret_key)} bytes")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Cerber v7 Security CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show security status")
    status_parser.set_defaults(func=cmd_status)
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start security system")
    start_parser.add_argument("-w", "--watch", action="store_true", help="Keep running and watch")
    start_parser.set_defaults(func=cmd_start)
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop security system")
    stop_parser.set_defaults(func=cmd_stop)
    
    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Run security scan")
    scan_parser.set_defaults(func=cmd_scan)
    
    # Evidence command
    evidence_parser = subparsers.add_parser("evidence", help="Evidence management")
    evidence_parser.add_argument("action", choices=["capture", "list"], help="Action to perform")
    evidence_parser.set_defaults(func=cmd_evidence)
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate security report")
    report_parser.add_argument("-o", "--output", help="Output file path")
    report_parser.add_argument("-v", "--view", action="store_true", help="View report after generation")
    report_parser.set_defaults(func=cmd_report)
    
    # Decoys command
    decoys_parser = subparsers.add_parser("decoys", help="Decoy management")
    decoys_parser.add_argument("action", choices=["status", "deploy", "honeypot"], help="Action to perform")
    decoys_parser.add_argument("-p", "--port", type=int, help="Honeypot port")
    decoys_parser.set_defaults(func=cmd_decoys)
    
    # Keygen command
    keygen_parser = subparsers.add_parser("keygen", help="Generate PQ keypair")
    keygen_parser.add_argument("-s", "--scheme", choices=["falcon", "sphincs", "dilithium"], help="PQ scheme")
    keygen_parser.add_argument("-o", "--output", help="Output file path")
    keygen_parser.set_defaults(func=cmd_keygen)
    
    args = parser.parse_args()
    
    if not args.command:
        print_banner()
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
