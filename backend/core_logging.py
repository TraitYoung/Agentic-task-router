import io
import logging
import sys


def configure_stdio_utf8() -> None:
    """
    在 Windows/PowerShell 等环境统一 stdout/stderr 编码，避免日志字符导致编码异常。
    """
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
            # 日志兜底不应阻断业务启动。
            pass


def setup_logging(level: int = logging.INFO) -> None:
    """
    统一初始化根日志格式与输出流，重复调用安全（幂等）。
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
