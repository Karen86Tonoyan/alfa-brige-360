"""
ALFA CLI v1 — INTERACTIVE SHELL
Interaktywny shell dla ALFA.
"""

from typing import Optional, Dict, Any, Callable
import logging
import sys
import os

logger = logging.getLogger("ALFA.CLI")

# Colors for terminal
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"

# Disable colors on Windows without proper support
if os.name == 'nt':
    try:
        os.system('')  # Enable ANSI on Windows
    except:
        for attr in dir(Colors):
            if not attr.startswith('_'):
                setattr(Colors, attr, '')


class ALFAShell:
    """
    Interaktywny shell ALFA.
    """
    
    BANNER = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════╗
║                                                              ║
║     █████╗ ██╗     ███████╗ █████╗     ██████╗ ██████╗      ║
║    ██╔══██╗██║     ██╔════╝██╔══██╗    ╚════██╗╚════██╗     ║
║    ███████║██║     █████╗  ███████║     █████╔╝ █████╔╝     ║
║    ██╔══██║██║     ██╔══╝  ██╔══██║     ╚═══██╗ ╚═══██╗     ║
║    ██║  ██║███████╗██║     ██║  ██║    ██████╔╝██████╔╝     ║
║    ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝    ╚═════╝ ╚═════╝      ║
║                                                              ║
║           ALFA CORE KERNEL v3.0 - Production                ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    
    PROMPT = f"{Colors.GREEN}ALFA{Colors.RESET} > "
    
    def __init__(self, kernel=None):
        """
        Args:
            kernel: CoreManager instance (opcjonalny)
        """
        self.kernel = kernel
        self._running = False
        self._commands: Dict[str, Callable] = {}
        
        self._register_builtin_commands()
    
    def _register_builtin_commands(self) -> None:
        """Rejestruje wbudowane komendy."""
        self._commands = {
            "help": self._cmd_help,
            "exit": self._cmd_exit,
            "quit": self._cmd_exit,
            "status": self._cmd_status,
            "clear": self._cmd_clear,
            "reset": self._cmd_reset,
            "providers": self._cmd_providers,
            "memory": self._cmd_memory,
        }
    
    def register_command(self, name: str, handler: Callable) -> None:
        """Rejestruje własną komendę."""
        self._commands[name] = handler
    
    def run(self) -> None:
        """Uruchamia shell."""
        print(self.BANNER)
        print(f"{Colors.YELLOW}Type 'help' for commands, 'exit' to quit.{Colors.RESET}\n")
        
        self._running = True
        
        while self._running:
            try:
                user_input = input(self.PROMPT).strip()
                
                if not user_input:
                    continue
                
                self._process_input(user_input)
                
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Use 'exit' to quit.{Colors.RESET}")
            except EOFError:
                self._running = False
                print()
    
    def _process_input(self, text: str) -> None:
        """Przetwarza input użytkownika."""
        # Check for command
        if text.startswith("/"):
            parts = text[1:].split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            if cmd in self._commands:
                try:
                    self._commands[cmd](args)
                except Exception as e:
                    self._error(f"Command error: {e}")
            else:
                self._error(f"Unknown command: {cmd}")
            return
        
        # Send to kernel
        if self.kernel:
            response = self.kernel.dispatch(text)
            self._print_response(response)
        else:
            self._warning("No kernel configured. Use /help for commands.")
    
    def _print_response(self, text: str) -> None:
        """Wyświetla odpowiedź."""
        print(f"\n{Colors.CYAN}ALFA:{Colors.RESET} {text}\n")
    
    def _info(self, text: str) -> None:
        """Info message."""
        print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")
    
    def _success(self, text: str) -> None:
        """Success message."""
        print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")
    
    def _warning(self, text: str) -> None:
        """Warning message."""
        print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")
    
    def _error(self, text: str) -> None:
        """Error message."""
        print(f"{Colors.RED}✗ {text}{Colors.RESET}")
    
    # Built-in commands
    
    def _cmd_help(self, args: list) -> None:
        """Wyświetla pomoc."""
        print(f"""
{Colors.CYAN}ALFA Commands:{Colors.RESET}

  {Colors.GREEN}/help{Colors.RESET}      - Show this help
  {Colors.GREEN}/status{Colors.RESET}    - Show kernel status
  {Colors.GREEN}/providers{Colors.RESET} - List providers
  {Colors.GREEN}/memory{Colors.RESET}    - Show memory status
  {Colors.GREEN}/clear{Colors.RESET}     - Clear screen
  {Colors.GREEN}/reset{Colors.RESET}     - Reset conversation
  {Colors.GREEN}/exit{Colors.RESET}      - Exit shell

Just type your message to chat with ALFA.
""")
    
    def _cmd_exit(self, args: list) -> None:
        """Wychodzi z shell."""
        self._info("Goodbye!")
        self._running = False
    
    def _cmd_status(self, args: list) -> None:
        """Pokazuje status."""
        if self.kernel:
            status = self.kernel.status()
            print(f"\n{Colors.CYAN}Kernel Status:{Colors.RESET}")
            print(f"  Initialized: {status.get('initialized', False)}")
            print(f"  Uptime: {status.get('uptime_seconds', 0):.1f}s")
            
            components = status.get('components', {})
            print(f"\n{Colors.CYAN}Components:{Colors.RESET}")
            for comp, loaded in components.items():
                icon = "✓" if loaded else "✗"
                color = Colors.GREEN if loaded else Colors.RED
                print(f"  {color}{icon}{Colors.RESET} {comp}")
            print()
        else:
            self._warning("No kernel configured")
    
    def _cmd_clear(self, args: list) -> None:
        """Czyści ekran."""
        os.system('cls' if os.name == 'nt' else 'clear')
        print(self.BANNER)
    
    def _cmd_reset(self, args: list) -> None:
        """Resetuje konwersację."""
        if self.kernel and hasattr(self.kernel, '_memory') and self.kernel._memory:
            self.kernel._memory.clear()
            self._success("Conversation reset")
        else:
            self._warning("No memory to reset")
    
    def _cmd_providers(self, args: list) -> None:
        """Lista providerów."""
        if self.kernel:
            providers = self.kernel.provider_registry.status()
            print(f"\n{Colors.CYAN}Providers:{Colors.RESET}")
            for name, info in providers.get('providers', {}).items():
                status = info.get('status', 'UNKNOWN')
                color = Colors.GREEN if status == 'ONLINE' else Colors.RED
                print(f"  {color}●{Colors.RESET} {name}: {status}")
            print()
        else:
            self._warning("No kernel configured")
    
    def _cmd_memory(self, args: list) -> None:
        """Status pamięci."""
        if self.kernel and hasattr(self.kernel, '_memory') and self.kernel._memory:
            status = self.kernel._memory.status()
            print(f"\n{Colors.CYAN}Memory Status:{Colors.RESET}")
            print(f"  Total entries: {status.get('total_entries', 0)}")
            print(f"  Max entries: {status.get('max_entries', 0)}")
            print()
        else:
            self._warning("Memory not available")


def main():
    """Entry point dla CLI."""
    try:
        from ..kernel import get_kernel
        kernel = get_kernel()
        kernel.initialize()
    except ImportError:
        kernel = None
    
    shell = ALFAShell(kernel)
    shell.run()


if __name__ == "__main__":
    main()
