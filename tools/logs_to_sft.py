import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List


DEFAULT_SYSTEM_INSTRUCTION = (
    "你是一个高可靠的数据清洗助手。请基于输入日志片段输出准确、简洁、可复用的工程知识表达。"
)


def _normalize_text(text: str) -> str:
    """清洗日志文本，去掉装饰线与多余空白。"""
    text = text.replace("\ufeff", "")
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"[=\-]{3,}", line):
            continue
        line = re.sub(r"^\d+\.\s*", "", line)  # 1. xxx
        line = re.sub(r"^[一二三四五六七八九十]+[、.]\s*", "", line)  # 一、xxx
        line = re.sub(r"^[\-\*\u2022]\s*", "", line)  # - xxx / * xxx
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _split_chunks(cleaned_text: str, min_len: int = 20, max_len: int = 1200) -> List[str]:
    """按段切分并限制长度，得到可用于 SFT 的文本块。"""
    if not cleaned_text:
        return []
    raw_chunks = re.split(r"\n{2,}", cleaned_text)
    chunks: List[str] = []
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if len(chunk) < min_len:
            continue
        # 防止单条过长，按句号或换行进一步切分
        if len(chunk) <= max_len:
            chunks.append(chunk)
            continue
        sentences = re.split(r"(?<=[。！？.!?])\s+|\n", chunk)
        buffer = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            candidate = f"{buffer}\n{sentence}".strip() if buffer else sentence
            if len(candidate) <= max_len:
                buffer = candidate
            else:
                if len(buffer) >= min_len:
                    chunks.append(buffer)
                buffer = sentence
        if len(buffer) >= min_len:
            chunks.append(buffer)
    return chunks


def _iter_log_files(input_dir: Path) -> Iterable[Path]:
    for path in sorted(input_dir.glob("*.log")):
        if path.is_file():
            yield path


def build_sft_records(
    log_text: str,
    source_name: str,
    system_instruction: str,
    user_prompt_template: str,
) -> List[dict]:
    cleaned = _normalize_text(log_text)
    chunks = _split_chunks(cleaned)
    records: List[dict] = []
    for idx, chunk in enumerate(chunks, start=1):
        source_id = f"{source_name}#chunk_{idx}"
        records.append(
            {
                "id": hashlib.sha1(source_id.encode("utf-8")).hexdigest(),
                "source": source_name,
                "chunk_index": idx,
                "system": system_instruction,
                "instruction": user_prompt_template,
                "input": chunk,
                "output": chunk,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt_template + "\n\n" + chunk},
                    {"role": "assistant", "content": chunk},
                ],
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
        )
    return records


def _load_system_instruction(args: argparse.Namespace) -> str:
    if args.system_instruction_file:
        text = Path(args.system_instruction_file).read_text(encoding="utf-8").strip()
        return text or DEFAULT_SYSTEM_INSTRUCTION
    if args.system_instruction:
        return args.system_instruction.strip()
    return DEFAULT_SYSTEM_INSTRUCTION


def main() -> None:
    parser = argparse.ArgumentParser(
        description="读取日志并清洗为 SFT_training_data.jsonl，支持归档与自定义 system instruction。"
    )
    parser.add_argument("--input-dir", default="input", help="输入目录，默认 input")
    parser.add_argument("--output-dir", default="output", help="输出目录，默认 output")
    parser.add_argument(
        "--archive-dir",
        default=None,
        help="归档目录，默认 output/archive",
    )
    parser.add_argument(
        "--output-file",
        default="SFT_training_data.jsonl",
        help="输出文件名，默认 SFT_training_data.jsonl",
    )
    parser.add_argument(
        "--system-instruction",
        default=None,
        help="自定义 system instruction 文本",
    )
    parser.add_argument(
        "--system-instruction-file",
        default=None,
        help="从文件读取 system instruction（优先级高于 --system-instruction）",
    )
    parser.add_argument(
        "--user-prompt-template",
        default="请基于以下工程日志片段，输出可复用的技术知识表达。",
        help="写入数据集中的 user 指令模板",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅统计，不写文件不归档",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    archive_dir = Path(args.archive_dir).resolve() if args.archive_dir else (output_dir / "archive").resolve()
    output_path = output_dir / args.output_file
    system_instruction = _load_system_instruction(args)

    # 默认体验：目录不存在就创建
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    all_records: List[dict] = []
    archived_files = []
    file_stats = []
    seen_ids = set()
    source_files = list(_iter_log_files(input_dir))

    for log_file in source_files:
        raw_text = log_file.read_text(encoding="utf-8", errors="ignore")
        records = build_sft_records(
            log_text=raw_text,
            source_name=log_file.name,
            system_instruction=system_instruction,
            user_prompt_template=args.user_prompt_template,
        )
        deduped = []
        for rec in records:
            if rec["id"] in seen_ids:
                continue
            seen_ids.add(rec["id"])
            deduped.append(rec)
        all_records.extend(deduped)
        file_stats.append({"file": log_file.name, "chunks": len(records), "kept": len(deduped)})

    if not args.dry_run:
        with output_path.open("w", encoding="utf-8") as f:
            for rec in all_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        if source_files:
            batch_dir = archive_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_dir.mkdir(parents=True, exist_ok=True)
            for src in source_files:
                target = batch_dir / src.name
                shutil.move(str(src), str(target))
                archived_files.append(str(target))

    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "input_dir": str(input_dir),
        "output_file": str(output_path),
        "archive_dir": str(archive_dir),
        "dry_run": args.dry_run,
        "system_instruction": system_instruction,
        "source_files": [p.name for p in source_files],
        "records_total": len(all_records),
        "file_stats": file_stats,
        "archived_files": archived_files,
    }

    if not args.dry_run:
        manifest_path = output_dir / "sft_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
