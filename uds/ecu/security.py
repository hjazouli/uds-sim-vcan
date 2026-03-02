import random
import logging

logger = logging.getLogger(__name__)


class SecurityManager:
    """
    Security Access (0x27) seed/key logic.
    """

    SECRET_KEY_XOR = 0xDEADBEEF
    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        self.locked = True
        self.attempts = 0
        self.current_seed = 0
        self.lockout_active = False

    def generate_seed(self) -> bytes:
        """Generate a random 4-byte seed."""
        self.current_seed = random.getrandbits(32)
        return self.current_seed.to_bytes(4, "big")

    def validate_key(self, key_bytes: bytes) -> bool:
        """Validate key = seed XOR 0xDEADBEEF."""
        if self.lockout_active:
            logger.warning("[bold red]Security access BLOCKED[/] due to previous failed attempts")
            return False

        if len(key_bytes) != 4:
            logger.warning(f"Invalid key length: expected 4 bytes, got [yellow]{len(key_bytes)}[/]")
            self.attempts += 1
            if self.attempts >= self.MAX_ATTEMPTS:
                self.lockout_active = True
                logger.error("[bold red]Security access LOCKED OUT[/] (too many attempts)")
            return False

        try:
            key = int.from_bytes(key_bytes, "big")
            expected_key = self.current_seed ^ self.SECRET_KEY_XOR

            if key == expected_key:
                self.locked = False
                self.attempts = 0
                logger.info("[bold green]Security access UNLOCKED[/]")
                return True
            else:
                self.attempts += 1
                logger.warning(
                    f"Invalid key. Attempt [yellow]{self.attempts}/{self.MAX_ATTEMPTS}[/]"
                )
                if self.attempts >= self.MAX_ATTEMPTS:
                    self.lockout_active = True
                    logger.error("[bold red]Security access LOCKED OUT[/] (too many attempts)")
                return False
        except Exception as e:
            logger.error(f"Error validating key: [red]{e}[/]")
            return False

    def reset(self) -> None:
        """Reset security state (e.g. on ECU reset)."""
        self.locked = True
        self.attempts = 0
        self.current_seed = 0
        self.lockout_active = False
        logger.info("Security manager reset to [bold yellow]LOCKED[/] state")
