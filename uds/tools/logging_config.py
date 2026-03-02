import logging
from rich.logging import RichHandler
from rich.console import Console

def setup_logging(level=logging.INFO):
    """Sets up a beautiful terminal logging experience using 'rich'."""
    
    # We use a custom console to ensure colors work correctly in different terminals
    console = Console(width=120)

    # Configure the RichHandler
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_path=False, # We usually don't need the file path for these types of logs
    )

    # Reset existing handlers to avoid double logging
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler]
    )

    # Specific tweaks for third-party noise
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("udsoncan").setLevel(logging.WARNING)
    logging.getLogger("UDSClient").setLevel(logging.WARNING)
    
    return logging.getLogger("UDS")

if __name__ == "__main__":
    # Test session
    log = setup_logging()
    log.info("[bold cyan]UDS Ecosystem[/] initialized.")
    log.warning("Session [yellow]EXTENDED[/] timed out. [red]Resetting to DEFAULT[/].")
    log.error("Failed to authenticate key [italic]0x1234[/].")
