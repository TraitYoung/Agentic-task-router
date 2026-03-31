from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    text = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(text, extensions=["fenced_code", "tables"])

    base_css = """
    @page { size: A4; margin: 18mm; }
    body { font-family: "Microsoft YaHei", "Noto Sans SC", "SimSun", serif; line-height: 1.5; font-size: 12.5pt; color: #111; }
    code, pre { font-family: "Consolas", "Courier New", monospace; }
    pre { padding: 10px; background: #f6f8fa; border-radius: 6px; overflow-x: auto; }
    img { max-width: 100%; }
    """

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>{base_css}</style>
</head>
<body>
{html_body}
</body>
</html>
"""

    # playwright 直接把“页面内容”打印成 PDF，避免 weasyprint 在 Windows 缺系统库的问题
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        page.emulate_media(media="print")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
        )
        browser.close()


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    docs_dir = project_root / "docs"
    out_dir = project_root / "docs" / "pdf"
    out_dir.mkdir(parents=True, exist_ok=True)

    md_v17 = docs_dir / "Axiodrasil_BIOS_V17.0.md"
    if not md_v17.exists():
        raise FileNotFoundError(str(md_v17))

    # 用 glob 避免在代码里硬编码中文文件名部分
    md_v4_candidates = sorted(docs_dir.glob("Axiodrasil_BIOS_V4.0.15*.md"))
    if not md_v4_candidates:
        raise FileNotFoundError("未找到 Axiodrasil_BIOS_V4.0.15*.md")
    md_v4 = md_v4_candidates[0]

    pdf_v17 = out_dir / f"{md_v17.stem}.pdf"
    pdf_v4 = out_dir / f"{md_v4.stem}.pdf"

    md_to_pdf(md_v17, pdf_v17)
    print(f"生成完成: {pdf_v17}")

    md_to_pdf(md_v4, pdf_v4)
    print(f"生成完成: {pdf_v4}")


if __name__ == "__main__":
    main()

