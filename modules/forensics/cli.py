#!/usr/bin/env python3
"""
ALFA Forensics CLI

Command-line interface for forensic operations.

Usage:
    python -m modules.forensics.cli check
    python -m modules.forensics.cli partitions
    python -m modules.forensics.cli scan /dev/sda2 "ALFA_SEED"
    python -m modules.forensics.cli recover <scan_id> <match_index>

Author: ALFA System / Karen86Tonoyan
Version: 1.0.0
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .forensics_engine import ForensicsEngine, WindowsForensics
from .disk_scanner import DiskScanner, print_partition_table


def cmd_check(args):
    """Check system readiness."""
    engine = ForensicsEngine()
    status = engine.check_system()
    
    print("=== ALFA Forensics System Check ===\n")
    print(f"Platform:         {status['platform']}")
    print(f"Linux:            {'✓' if status['is_linux'] else '✗'}")
    print(f"Root privileges:  {'✓' if status['is_root'] else '✗ (required for disk scanning)'}")
    print(f"RecoverPy:        {'✓' if status['recoverpy_available'] else '✗'}")
    
    if not status['recoverpy_available']:
        print(f"  Reason: {status['recoverpy_reason']}")
    
    print(f"\nOutput directory: {status['output_dir']}")
    
    if sys.platform == "win32":
        print("\n=== Windows Tools ===")
        tools = WindowsForensics.check_available_tools()
        for tool, available in tools.items():
            print(f"  {tool}: {'✓' if available else '✗'}")
        
        shadows = WindowsForensics.list_shadow_copies()
        if shadows:
            print(f"\n  Shadow copies: {len(shadows)}")
            for s in shadows[:3]:
                print(f"    - {s.get('id', 'unknown')[:20]}... ({s.get('created', 'unknown')})")
    
    return 0


def cmd_partitions(args):
    """List partitions."""
    print("=== Available Partitions ===\n")
    print_partition_table()
    
    scanner = DiskScanner()
    
    print("\n=== Scan Safety ===")
    for p in scanner.partitions:
        safe, reason = scanner.is_safe_to_scan(p)
        status = "✓ SAFE" if safe else f"⚠ {reason}"
        print(f"  {p.device}: {status}")
    
    return 0


def cmd_scan(args):
    """Scan partition for pattern."""
    engine = ForensicsEngine()
    
    print(f"Scanning {args.partition} for '{args.pattern}'...\n")
    
    async def do_scan():
        return await engine.scan_custom(args.partition, args.pattern)
    
    result = asyncio.run(do_scan())
    
    print(f"Scan ID: {result.scan_id}")
    print(f"Status:  {result.status.value}")
    print(f"Blocks:  {result.blocks_scanned}")
    print(f"Matches: {len(result.matches)}")
    
    if result.error_message:
        print(f"Error:   {result.error_message}")
    
    if result.matches:
        print("\n=== Matches ===")
        for i, m in enumerate(result.matches[:10]):
            print(f"\n[{i}] Block {m.block_number} @ offset {m.offset}")
            print(f"    Score: {m.match_score}")
            print(f"    Preview: {m.content_preview[:80]}...")
    
    # Save result
    output_file = Path(engine.output_dir) / f"scan_{result.scan_id}.json"
    with open(output_file, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    print(f"\nResult saved to: {output_file}")
    
    return 0


def cmd_scan_seed(args):
    """Scan for ALFA seed patterns."""
    engine = ForensicsEngine()
    
    print(f"Scanning {args.partition} for ALFA seed patterns...\n")
    
    async def do_scan():
        return await engine.scan_for_alfa_seed(args.partition)
    
    result = asyncio.run(do_scan())
    
    print(f"Scan ID: {result.scan_id}")
    print(f"Status:  {result.status.value}")
    print(f"Pattern: {result.search_pattern}")
    print(f"Matches: {len(result.matches)}")
    
    if result.matches:
        print("\n=== Potential ALFA Seed Locations ===")
        for i, m in enumerate(result.matches[:5]):
            print(f"\n[{i}] Block {m.block_number}")
            print(f"    Preview: {m.content_preview[:100]}...")
    
    return 0


def cmd_recover(args):
    """Recover block from previous scan."""
    engine = ForensicsEngine()
    
    # Load scan result
    scan_file = Path(engine.output_dir) / f"scan_{args.scan_id}.json"
    if not scan_file.exists():
        print(f"Scan result not found: {scan_file}")
        return 1
    
    with open(scan_file) as f:
        scan_data = json.load(f)
    
    # Recreate result object (simplified)
    from .forensics_engine import ForensicsScanResult, BlockMatch, ScanStatus
    from datetime import datetime
    
    result = ForensicsScanResult(
        scan_id=scan_data["scan_id"],
        partition=scan_data["partition"],
        search_pattern=scan_data["search_pattern"],
        status=ScanStatus(scan_data["status"]),
        started_at=datetime.fromisoformat(scan_data["started_at"]),
    )
    
    for m in scan_data["matches"]:
        result.matches.append(BlockMatch(
            block_number=m["block"],
            offset=m["offset"],
            content_preview=m["preview"],
            match_score=m["score"],
        ))
    
    # Recover
    data = engine.recover_match(result, args.match_index)
    
    if data:
        print(f"Recovered {len(data)} bytes from block {result.matches[args.match_index].block_number}")
        print(f"Saved to: {result.matches[args.match_index].recovery_path}")
        
        # Preview
        print("\n=== Preview (first 256 bytes) ===")
        try:
            print(data[:256].decode("utf-8", errors="replace"))
        except Exception:
            print(data[:256].hex())
    else:
        print("Recovery failed - check privileges and partition access")
        return 1
    
    return 0


def cmd_history(args):
    """Show scan history."""
    engine = ForensicsEngine()
    
    log_file = Path(engine.output_dir) / "forensics.log"
    if not log_file.exists():
        print("No scan history found")
        return 0
    
    print("=== Forensics History ===\n")
    
    with open(log_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                print(f"[{entry['timestamp']}] {entry['action']}")
                for k, v in entry.items():
                    if k not in ['timestamp', 'action']:
                        print(f"    {k}: {v}")
            except json.JSONDecodeError:
                continue
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="ALFA Forensics CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # check
    subparsers.add_parser("check", help="Check system readiness")
    
    # partitions
    subparsers.add_parser("partitions", help="List partitions")
    
    # scan
    scan_parser = subparsers.add_parser("scan", help="Scan partition for pattern")
    scan_parser.add_argument("partition", help="Partition to scan (e.g., /dev/sda2)")
    scan_parser.add_argument("pattern", help="Search pattern")
    
    # scan-seed
    seed_parser = subparsers.add_parser("scan-seed", help="Scan for ALFA seed")
    seed_parser.add_argument("partition", help="Partition to scan")
    
    # recover
    recover_parser = subparsers.add_parser("recover", help="Recover block from scan")
    recover_parser.add_argument("scan_id", help="Scan ID")
    recover_parser.add_argument("match_index", type=int, help="Match index to recover")
    
    # history
    subparsers.add_parser("history", help="Show scan history")
    
    args = parser.parse_args()
    
    commands = {
        "check": cmd_check,
        "partitions": cmd_partitions,
        "scan": cmd_scan,
        "scan-seed": cmd_scan_seed,
        "recover": cmd_recover,
        "history": cmd_history,
    }
    
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
