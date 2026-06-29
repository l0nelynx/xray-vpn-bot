import logging
import traceback as tb_module
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LogEntry:
    timestamp: datetime
    logger_name: str
    level: str
    message: str
    traceback: str | None = None


class RingBufferHandler(logging.Handler):
    def __init__(self, maxlen: int = 20):
        super().__init__(level=logging.ERROR)
        self._buffer: deque[LogEntry] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord):
        trace = None
        if record.exc_info and record.exc_info[2]:
            trace = "".join(tb_module.format_exception(*record.exc_info))
        entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created),
            logger_name=record.name,
            level=record.levelname,
            message=self.format(record) if not record.getMessage() else record.getMessage(),
            traceback=trace,
        )
        self._buffer.append(entry)

    def get_entries(self) -> list[LogEntry]:
        return list(self._buffer)

    def format_entries_for_display(self) -> str:
        if not self._buffer:
            return ""
        parts = []
        for e in self._buffer:
            ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            msg = e.message[:500] if len(e.message) > 500 else e.message
            text = f"<b>[{e.level}]</b> {ts}\n<b>{e.logger_name}</b>\n<code>{msg}</code>"
            if e.traceback:
                tr = e.traceback[:300] if len(e.traceback) > 300 else e.traceback
                text += f"\n<pre>{tr}</pre>"
            parts.append(text)
        return "\n\n".join(parts)


error_log_handler: RingBufferHandler | None = None


def init_error_log_handler(maxlen: int = 20):
    global error_log_handler
    error_log_handler = RingBufferHandler(maxlen=maxlen)
    logging.getLogger().addHandler(error_log_handler)
