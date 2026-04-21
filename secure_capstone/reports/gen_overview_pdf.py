"""project_overview.md → project_overview.pdf (가독성 중심 스타일)"""
import re
from fpdf import FPDF

MD = r"C:\Users\08121\Desktop\test\Ai_Slopsquatting\secure_capstone\reports\project_overview.md"
OUT = r"C:\Users\08121\Desktop\test\Ai_Slopsquatting\secure_capstone\reports\project_overview.pdf"

F_REG = r"C:\Windows\Fonts\malgun.ttf"
F_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
F_MONO = r"C:\Windows\Fonts\consola.ttf"

pdf = FPDF(format="A4")
pdf.set_auto_page_break(auto=True, margin=18)
pdf.add_font("mg", "", F_REG, uni=True)
pdf.add_font("mg", "B", F_BOLD, uni=True)
pdf.add_font("co", "", F_MONO, uni=True)

pdf.add_page()

PAGE_W = 210
MARGIN = 15
CONTENT_W = PAGE_W - 2 * MARGIN  # 180
pdf.set_margins(MARGIN, 18, MARGIN)

# ── 색상 ──
C_H1 = (26, 26, 46)      # navy
C_H2 = (30, 64, 175)     # blue-700
C_H3 = (51, 65, 85)      # slate-700
C_TEXT = (31, 41, 55)    # gray-800
C_MUTED = (100, 116, 139)
C_ACCENT = (37, 99, 235)
C_CODE_BG = (243, 244, 246)
C_CODE_TEXT = (30, 41, 59)
C_TABLE_HEAD = (219, 234, 254)
C_TABLE_ROW = (248, 250, 252)
C_BORDER = (203, 213, 225)
C_QUOTE = (59, 130, 246)

def rule():
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.2)
    y = pdf.get_y() + 1
    pdf.line(MARGIN, y, PAGE_W - MARGIN, y)
    pdf.ln(5)

def h1(text):
    pdf.ln(4)
    if pdf.get_y() + 18 > 270:
        pdf.add_page()
    pdf.set_font("mg", "B", 20)
    pdf.set_text_color(*C_H1)
    pdf.cell(0, 11, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(0.8)
    y = pdf.get_y()
    pdf.line(MARGIN, y, MARGIN + 30, y)
    pdf.ln(5)

def h2(text):
    pdf.ln(3)
    if pdf.get_y() + 14 > 270:
        pdf.add_page()
    pdf.set_font("mg", "B", 14)
    pdf.set_text_color(*C_H2)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

def h3(text):
    pdf.ln(2)
    if pdf.get_y() + 10 > 270:
        pdf.add_page()
    pdf.set_font("mg", "B", 11.5)
    pdf.set_text_color(*C_H3)
    pdf.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.5)

def h4(text):
    pdf.ln(1)
    pdf.set_font("mg", "B", 10.5)
    pdf.set_text_color(*C_H3)
    pdf.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")

def body(text):
    pdf.set_font("mg", "", 10)
    pdf.set_text_color(*C_TEXT)
    # 인라인 마크다운 간단 파싱: **bold**, `code`
    parts = re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            pdf.set_font("mg", "B", 10)
            pdf.write(5.5, part[2:-2])
            pdf.set_font("mg", "", 10)
        elif part.startswith("`") and part.endswith("`"):
            pdf.set_font("co", "", 9)
            pdf.set_text_color(*C_ACCENT)
            pdf.write(5.5, part[1:-1])
            pdf.set_font("mg", "", 10)
            pdf.set_text_color(*C_TEXT)
        else:
            pdf.write(5.5, part)
    pdf.ln(5.5)

def bullet(text, indent=1):
    pdf.set_font("mg", "", 10)
    pdf.set_text_color(*C_TEXT)
    pdf.set_x(MARGIN + indent * 4)
    pdf.set_text_color(*C_ACCENT)
    pdf.write(5.5, "• ")
    pdf.set_text_color(*C_TEXT)
    parts = re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            pdf.set_font("mg", "B", 10)
            pdf.write(5.5, part[2:-2])
            pdf.set_font("mg", "", 10)
        elif part.startswith("`") and part.endswith("`"):
            pdf.set_font("co", "", 9)
            pdf.set_text_color(*C_ACCENT)
            pdf.write(5.5, part[1:-1])
            pdf.set_font("mg", "", 10)
            pdf.set_text_color(*C_TEXT)
        else:
            pdf.write(5.5, part)
    pdf.ln(5.5)

def blockquote(lines):
    pdf.ln(1)
    start_y = pdf.get_y()
    pdf.set_font("mg", "", 9.5)
    pdf.set_text_color(75, 85, 99)
    pdf.set_fill_color(239, 246, 255)
    pdf.set_x(MARGIN + 3)
    for line in lines:
        clean_line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
        clean_line = re.sub(r'`([^`]+)`', r'\1', clean_line)
        pdf.set_x(MARGIN + 5)
        pdf.multi_cell(CONTENT_W - 5, 5.5, clean_line, fill=False)
    end_y = pdf.get_y()
    pdf.set_draw_color(*C_QUOTE)
    pdf.set_line_width(1.2)
    pdf.line(MARGIN + 1, start_y, MARGIN + 1, end_y - 1)
    pdf.ln(2)

def code_block(code_lines):
    pdf.ln(1)
    line_h = 4.5
    total_h = len(code_lines) * line_h + 5
    if pdf.get_y() + total_h > 275:
        pdf.add_page()
    start_y = pdf.get_y()

    pdf.set_fill_color(*C_CODE_BG)
    pdf.rect(MARGIN, start_y, CONTENT_W, total_h, style="F")

    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(MARGIN, start_y, MARGIN, start_y + total_h)

    pdf.set_text_color(*C_CODE_TEXT)
    pdf.set_xy(MARGIN + 3, start_y + 2.5)
    for cl in code_lines:
        pdf.set_x(MARGIN + 3)
        while len(cl.encode('utf-8')) > 200:
            cl = cl[:-1]
        # 한글 포함이면 Malgun, 아니면 Consolas
        has_korean = any('\uac00' <= c <= '\ud7af' for c in cl)
        pdf.set_font("mg" if has_korean else "co", "", 8.5)
        pdf.cell(0, line_h, cl, new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(start_y + total_h + 2)
    pdf.set_text_color(*C_TEXT)

def render_table(header, rows):
    if not header or not rows:
        return
    cols = [c.strip() for c in header.strip("|").split("|")]
    n = len(cols)

    # 균등 분할, 너무 좁은 컬럼 방지
    col_w = CONTENT_W / n

    # 페이지 확인
    needed_h = (len(rows) + 1) * 7 + 4
    if pdf.get_y() + needed_h > 275:
        pdf.add_page()

    pdf.ln(1)

    # 헤더
    pdf.set_font("mg", "B", 9)
    pdf.set_text_color(*C_H2)
    pdf.set_fill_color(*C_TABLE_HEAD)
    pdf.set_draw_color(*C_BORDER)
    pdf.set_line_width(0.2)
    for c in cols:
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', c).strip()
        pdf.cell(col_w, 7, clean, border=1, align="L", fill=True)
    pdf.ln()

    # 행
    pdf.set_font("mg", "", 9)
    pdf.set_text_color(*C_TEXT)
    for i, row in enumerate(rows):
        cells = [c.strip() for c in row.strip("|").split("|")]
        while len(cells) < n:
            cells.append("")
        fill = i % 2 == 1
        pdf.set_fill_color(*C_TABLE_ROW) if fill else pdf.set_fill_color(255, 255, 255)
        for c in cells[:n]:
            clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', c)
            clean = re.sub(r'`([^`]+)`', r'\1', clean).strip()
            if len(clean) > 60:
                clean = clean[:58] + ".."
            pdf.cell(col_w, 6.5, clean, border=1, fill=fill)
        pdf.ln()
    pdf.ln(2)

# ── 마크다운 파싱 ──
with open(MD, encoding="utf-8") as f:
    lines = f.readlines()

i = 0
in_code = False
code_buf = []
in_table = False
table_header = None
table_rows = []
in_quote = False
quote_lines = []

def flush_table():
    global in_table, table_header, table_rows
    if in_table and table_header:
        render_table(table_header, table_rows)
    in_table = False
    table_header = None
    table_rows = []

def flush_quote():
    global in_quote, quote_lines
    if in_quote and quote_lines:
        blockquote(quote_lines)
    in_quote = False
    quote_lines = []

while i < len(lines):
    line = lines[i].rstrip("\n")

    # 코드 블록
    if line.startswith("```"):
        flush_table()
        flush_quote()
        if in_code:
            code_block(code_buf)
            code_buf = []
            in_code = False
        else:
            in_code = True
        i += 1
        continue
    if in_code:
        code_buf.append(line)
        i += 1
        continue

    # 테이블
    if "|" in line and line.strip().startswith("|"):
        flush_quote()
        stripped = line.strip()
        if re.match(r'^\|[\s\-:|\*]+\|$', stripped):
            i += 1
            continue
        if not in_table:
            in_table = True
            table_header = stripped
        else:
            table_rows.append(stripped)
        i += 1
        continue
    else:
        flush_table()

    # 인용
    if line.startswith("> "):
        flush_table()
        quote_lines.append(line[2:].strip())
        in_quote = True
        i += 1
        continue
    else:
        flush_quote()

    # 제목
    if line.startswith("# ") and not line.startswith("## "):
        title = line[2:].strip()
        # 첫 H1은 큰 표지로
        if i < 5:
            pdf.set_font("mg", "B", 24)
            pdf.set_text_color(*C_H1)
            pdf.cell(0, 14, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(*C_ACCENT)
            pdf.set_line_width(1.2)
            y = pdf.get_y()
            pdf.line(MARGIN, y, MARGIN + 40, y)
            pdf.ln(6)
        else:
            h1(title)
        i += 1
        continue
    if line.startswith("## "):
        h2(line[3:].strip())
        i += 1
        continue
    if line.startswith("### "):
        h3(line[4:].strip())
        i += 1
        continue
    if line.startswith("#### "):
        h4(line[5:].strip())
        i += 1
        continue

    # 구분선
    if line.strip() == "---":
        rule()
        i += 1
        continue

    # 불릿
    if line.startswith("- "):
        bullet(line[2:].strip())
        i += 1
        continue

    # 빈 줄
    if not line.strip():
        pdf.ln(1.5)
        i += 1
        continue

    # 일반 텍스트
    body(line.strip())
    i += 1

flush_table()
flush_quote()

pdf.output(OUT)
print(f"Done: {OUT}")
