"""MANUAL.md -> index.html (의존성 없음). 사용법: python build.py

MANUAL.md가 유일한 원본입니다. index.html은 직접 고치지 말고 이 스크립트로 다시 만듭니다.
각 단계(0~10단계)에 ①~⑦ 항목이 모두 있는지 검사하고, 빠지면 실패합니다.
"""
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "MANUAL.md"
OUT = ROOT / "index.html"
TEMPLATE = ROOT / "template.html"

REQUIRED = ["① 현장 경찰관", "② 112상황실", "③ 현장책임자", "④ 법적 근거", "⑤ 금지사항", "⑥ 무전 예시", "⑦ 완료 확인"]
ROLE = {"①": "field", "②": "dispatch", "③": "command"}


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = s.replace("(권장)", '<span class="rec">권장</span>')
    return s


def table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], cells[2:]
    cls = ' class="stack"' if len(head) >= 4 else ""  # 4열 이상만 모바일에서 카드로 쌓는다
    out = [f'<div class="tw"><table{cls}><thead><tr>']
    out += [f"<th>{inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        if len(r) != len(head):
            sys.exit(f"표 열 수 불일치: {r}")
        out.append("<tr>" + "".join(f'<td data-h="{html.escape(h)}">{inline(c)}</td>' for h, c in zip(head, r)) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def blocks(lines, sid, counter):
    """본문 줄들을 HTML로 변환한다. 체크 항목은 단계 내 고유 id를 받는다."""
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
        elif ln.startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append(table(lines[i:j]))
            i = j
        elif ln.startswith("- [ ] "):
            out.append('<ul class="chk">')
            while i < len(lines) and lines[i].startswith("- [ ] "):
                counter[0] += 1
                cid = f"{sid}-{counter[0]}"
                out.append(f'<li><label><input type="checkbox" data-id="{cid}"><span>{inline(lines[i][6:])}</span></label></li>')
                i += 1
            out.append("</ul>")
        elif ln.startswith("- "):
            out.append("<ul>")
            while i < len(lines) and lines[i].startswith("- "):
                out.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            out.append("</ul>")
        elif re.match(r"\d+\. ", ln):
            out.append("<ol>")
            while i < len(lines) and re.match(r"\d+\. ", lines[i]):
                out.append(f"<li>{inline(lines[i].split('. ', 1)[1])}</li>")
                i += 1
            out.append("</ol>")
        elif ln.startswith('"'):
            out.append(f'<p class="radio">{inline(ln)}</p>')
            i += 1
        else:
            out.append(f"<p>{inline(ln)}</p>")
            i += 1
    return "".join(out)


def parse(text):
    parts = re.split(r"^## ", text, flags=re.M)
    title = parts[0].split("\n", 1)[0].lstrip("# ").strip()
    notice = [l[2:] for l in parts[0].splitlines() if l.startswith("> ")]
    secs = []
    for p in parts[1:]:
        head, body = p.split("\n", 1)
        short, name = [x.strip() for x in head.split("|", 1)]
        lead = next((l[2:] for l in body.splitlines() if l.startswith("> ")), "")
        body = "\n".join(l for l in body.splitlines() if not l.startswith("> "))
        subs = re.split(r"^### ", body, flags=re.M)
        secs.append(dict(short=short, name=name, lead=lead, intro=subs[0].strip(), subs=[(s.split("\n", 1)[0].strip(), s.split("\n", 1)[1] if "\n" in s else "") for s in subs[1:]]))
    return title, notice, secs


def validate(secs):
    stages = [s for s in secs if s["short"].endswith("단계")]
    if len(stages) != 11:
        sys.exit(f"단계 수 오류: {len(stages)}")
    for s in stages:
        names = [n for n, _ in s["subs"]]
        if names != REQUIRED:
            sys.exit(f"{s['short']} 항목 오류: {names}")


def render(secs):
    nav, main = [], []
    for n, s in enumerate(secs):
        sid = f"s{n}"
        counter = [0]
        nav.append(f'<a href="#{sid}" data-sec="{sid}"><b>{inline(s["short"])}</b><span>{inline(s["name"])}</span></a>')
        body = [f'<section id="{sid}"><h2><small>{inline(s["short"])}</small>{inline(s["name"])}</h2>']
        if s["lead"]:
            body.append(f'<p class="lead">{inline(s["lead"])}</p>')
        if s["intro"]:
            body.append(blocks(s["intro"].splitlines(), sid, counter))
        for name, content in s["subs"]:
            inner = blocks(content.splitlines(), sid, counter)
            mark = name[0]
            if mark == "④":
                body.append(f'<details class="law"><summary>{inline(name)}</summary>{inner}</details>')
            else:
                role = ROLE.get(mark, "")
                cls = {"⑤": "ban", "⑥": "talk", "⑦": "done"}.get(mark, "")
                attr = f' data-role="{role}"' if role else ""
                body.append(f'<div class="sub {cls}"{attr}><h3>{inline(name)}</h3>{inner}</div>')
        body.append("</section>")
        main.append("".join(body))
    return "".join(nav), "".join(main)


def main():
    title, notice, secs = parse(SRC.read_text(encoding="utf-8"))
    validate(secs)
    nav, body = render(secs)
    note = "".join(f"<p>{inline(n)}</p>" for n in notice)
    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("{{TITLE}}", html.escape(title)).replace("{{NOTICE}}", note).replace("{{NAV}}", nav).replace("{{BODY}}", body)
    OUT.write_text(page, encoding="utf-8")
    checks = page.count('type="checkbox"')
    print(f"완료: {OUT.name} {len(page):,}자, 구역 {len(secs)}개, 체크항목 {checks}개")


if __name__ == "__main__":
    main()
