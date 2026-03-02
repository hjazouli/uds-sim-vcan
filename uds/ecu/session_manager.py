import time
import logging
from enum import IntEnum
from typing import Callable

logger = logging.getLogger(__name__)


class DiagnosticSession(IntEnum):
    DEFAULT = 0x01
    PROGRAMMING = 0x02
    EXTENDED = 0x03


class SessionManager:
    """
    UDS Session State Machine.
    Handles transitions and timeouts (S3 timer).
    """

    S3_TIMEOUT = 5.0  # seconds

    def __init__(self, on_timeout: Callable[[], None]) -> None:
        self.current_session = DiagnosticSession.DEFAULT
        self.last_tester_present = time.time()
        self.on_timeout = on_timeout
        logger.info(f"Session initialized: {self.current_session.name}")

    def set_session(self, session: int) -> None:
        """Transition to a new session."""
        try:
            new_session = DiagnosticSession(session)
            if new_session != self.current_session:
                logger.info(
                    f"Session transition: [bold]{self.current_session.name}[/] -> [bold cyan]{new_session.name}[/]"
                )
                self.current_session = new_session
                self.reset_timer()
        except ValueError:
            logger.error(f"Invalid session requested: [red]0x{session:02X}[/]")

    def reset_timer(self) -> None:
        """Reset the S3 timer (Tester Present received)."""
        self.last_tester_present = time.time()

    def check_timeout(self) -> None:
        """Check if session has timed out."""
        if self.current_session != DiagnosticSession.DEFAULT:
            if time.time() - self.last_tester_present > self.S3_TIMEOUT:
                logger.warning(
                    f"Session [yellow]{self.current_session.name}[/] timed out. [red]Resetting to DEFAULT[/]."
                )
                self.current_session = DiagnosticSession.DEFAULT
                self.on_timeout()

    def reset(self) -> None:
        """Force reset to default session."""
        self.current_session = DiagnosticSession.DEFAULT
        self.last_tester_present = time.time()
        logger.info("[bold red]Session manager reset to DEFAULT[/]")

    @property
    def is_default(self) -> bool:
        return self.current_session == DiagnosticSession.DEFAULT

    @property
    def is_extended(self) -> bool:
        return self.current_session == DiagnosticSession.EXTENDED

    @property
    def is_programming(self) -> bool:
        return self.current_session == DiagnosticSession.PROGRAMMING
