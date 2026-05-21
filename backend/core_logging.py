import contextvars
import io
import json
import logging
import sys

from config.settings import get_settings

# contextvars 用于在请求链路中透传 trace_id / session_id
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="")


class JSONFormatter(logging.Formatter):
    """输出单行 JSON 日志，便于集中采集与机读。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }

        for key in ("trace_id", "session_id", "duration_ms"):
            val = getattr(record, key, None)
            if val:
                log_entry[key] = str(val)

        # contextvars 注入（由 RequestLogMiddleware 设置）
        tid = trace_id_var.get()
        sid = session_id_var.get()
        if tid:
            log_entry["trace_id"] = tid
        if sid:
            log_entry["session_id"] = sid

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """传统文本格式，兼容开发环境阅读习惯。"""

    def __init__(self) -> None:
        super().__init__("%(asctime)s | %(levelname)s | %(name)s | %(message)s")


def configure_stdio_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
                continue
            if isinstance(stream, io.TextIOBase):
                wrapped = io.TextIOWrapper(
                    stream.buffer,
                    encoding="utf-8",
                    errors="replace",
                    line_buffering=True,
                )
                setattr(sys, stream_name, wrapped)
        except Exception:
            pass


def setup_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    settings = get_settings()
    use_json = settings.log_format != "text"
    formatter: logging.Formatter = JSONFormatter() if use_json else TextFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
