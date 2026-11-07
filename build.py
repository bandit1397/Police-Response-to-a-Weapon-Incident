"""MANUAL.md -> index.html (의존성 없음). 사용법: python build.py

MANUAL.md가 유일한 원본입니다. index.html은 직접 고치지 말고 이 스크립트로 다시 만듭니다.

MANUAL.md 작성 규칙
  ## [역할] 이름 | 설명        역할별 흐름도
  > 핵심: 문장                  현장 직원 첫 화면의 핵심 행동 (## [역할] 바로 아래)
  ### = 단계 이름 | 설명        흐름도를 묶는 단계 제목
  ### 칸 제목 | 한 줄 요약      흐름도의 칸
  ### ? 판단 질문              판단 칸. 아래 "- 답 -> 칸 제목"으로 갈림길을 적음
  #### 금지 / 무전 / 완료 기준 / 근거 / 다음    칸 안의 항목
  ## [상황] 이름 | 설명 | 등급  현장 직원 긴급 카드. 등급은 위급/위험/주의/통제.
                               "1. **행동** 설명" 순서와 #### 항목을 적은 차례대로 표시
  ## [참고] 이름 | 설명        참고 자료
  [[참고 이름]]                참고 자료로 가는 링크

갈림길이나 링크의 대상이 없거나, 칸에 할 일이 없으면 빌드가 실패합니다.
"""
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "MANUAL.md"
OUT = ROOT / "index.html"
TEMPLATE = ROOT / "template.html"

ROLE_ID = {"현장 직원": "field", "현장 책임자": "command", "112상황실": "dispatch", "수사부서": "invest"}
PARTS = {"금지": "ban", "무전": "talk", "완료 기준": "done", "근거": "law", "다음": "next"}
TONE = {"위급": "red", "위험": "amber", "주의": "blue", "통제": "green"}
SIT_PARTS = {"금지": "ban", "무전": "talk", "명령": "cmd"}
BRANCH = re.compile(r"^- (.+?) -> (.+)$", re.M)


class Doc:
    def __init__(self, refs):
        self.refs = refs

    def inline(self, s):
        s = html.escape(s, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = s.replace("`(권장)`", "(권장)").replace("`권장`", "(권장)")
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        s = s.replace("(권장)", '<span class="rec">권장</span>')

        def link(m):
            name = m.group(1)
            if name not in self.refs:
                sys.exit(f"없는 참고 링크: [[{name}]]")
            return f'<a class="ref" href="#{self.refs[name]}">{name}</a>'

        return re.sub(r"\[\[(.+?)\]\]", link, s)

    def table(self, rows):
        cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
        head, body = cells[0], cells[2:]
        cls = ' class="stack"' if len(head) >= 4 else ""  # 4열 이상만 모바일에서 카드로 쌓는다
        out = [f'<div class="tw"><table{cls}><thead><tr>']
        out += [f"<th>{self.inline(c)}</th>" for c in head]
        out.append("</tr></thead><tbody>")
        for r in body:
            if len(r) != len(head):
                sys.exit(f"표 열 수 불일치: {r}")
            tds = "".join(f'<td data-h="{html.escape(h)}">{self.inline(c)}</td>' for h, c in zip(head, r))
            out.append(f"<tr>{tds}</tr>")
        out.append("</tbody></table></div>")
        return "".join(out)

    def blocks(self, text, sid, counter):
        lines, out, i = text.splitlines(), [], 0
        while i < len(lines):
            ln = lines[i]
            if not ln.strip():
                i += 1
            elif ln.startswith("|"):
                j = i
                while j < len(lines) and lines[j].startswith("|"):
                    j += 1
                out.append(self.table(lines[i:j]))
                i = j
            elif ln.startswith("- [ ] "):
                out.append('<ul class="chk">')
                while i < len(lines) and lines[i].startswith("- [ ] "):
                    counter[0] += 1
                    out.append(f'<li><label><input type="checkbox" data-id="{sid}-{counter[0]}"><span>{self.inline(lines[i][6:])}</span></label></li>')
                    i += 1
                out.append("</ul>")
            elif ln.startswith("- "):
                out.append("<ul>")
                while i < len(lines) and lines[i].startswith("- "):
                    out.append(f"<li>{self.inline(lines[i][2:])}</li>")
                    i += 1
                out.append("</ul>")
            elif re.match(r"\d+\. ", ln):
                out.append("<ol>")
                while i < len(lines) and re.match(r"\d+\. ", lines[i]):
                    out.append(f"<li>{self.inline(lines[i].split('. ', 1)[1])}</li>")
                    i += 1
                out.append("</ol>")
            elif ln.startswith("### "):
                out.append(f"<h4>{self.inline(ln[4:])}</h4>")
                i += 1
            elif ln.startswith("> "):
                out.append(f'<p class="lead">{self.inline(ln[2:])}</p>')
                i += 1
            elif ln.startswith('"'):
                out.append(f'<p class="radio">{self.inline(ln)}</p>')
                i += 1
            else:
                out.append(f"<p>{self.inline(ln)}</p>")
                i += 1
        return "".join(out)


def parse(text):
    parts = re.split(r"^## ", text, flags=re.M)
    title = parts[0].split("\n", 1)[0].lstrip("# ").strip()
    notice = [l[2:] for l in parts[0].splitlines() if l.startswith("> ")]
    roles, refs, sits = [], [], []
    for p in parts[1:]:
        head, body = p.split("\n", 1)
        kind = re.match(r"\[(역할|참고|상황)\] (.+?) \| (.+)", head)
        if not kind:
            sys.exit(f"구역 제목 오류: {head}")
        item = dict(name=kind[2], desc=kind[3], body=body.strip())
        if kind[1] == "상황":
            item["desc"], tone = [x.strip() for x in kind[3].rsplit("|", 1)]
            if tone not in TONE:
                sys.exit(f"없는 등급: {tone} ({kind[2]})")
            item["tone"] = TONE[tone]
            if "- [ ] " in body:
                sys.exit(f"긴급 카드에는 체크 항목을 두지 않습니다: {kind[2]}")
            sits.append(item)
        else:
            (roles if kind[1] == "역할" else refs).append(item)
    return title, notice, roles, refs, sits


def parse_nodes(body):
    chunks = re.split(r"^### ", body, flags=re.M)
    nodes = []
    for c in chunks[1:]:
        head, rest = (c.split("\n", 1) + [""])[:2]
        if head.startswith("= "):
            name, sub = [x.strip() for x in head[2:].split("|", 1)]
            nodes.append(dict(kind="s", title=name, sub=sub))
            continue
        if head.startswith("? "):
            branches = BRANCH.findall(rest)
            if len(branches) < 2:
                sys.exit(f"갈림길 부족: {head}")
            nodes.append(dict(kind="q", title=head[2:], branches=branches))
            continue
        title, sub = [x.strip() for x in head.split("|", 1)] if "|" in head else (head.strip(), "")
        secs = re.split(r"^#### ", rest, flags=re.M)
        parts = {}
        for s in secs[1:]:
            name, content = (s.split("\n", 1) + [""])[:2]
            if name.strip() not in PARTS:
                sys.exit(f"알 수 없는 항목: {name} ({title})")
            parts[name.strip()] = content
        if not secs[0].strip():
            sys.exit(f"할 일 없는 칸: {title}")
        nodes.append(dict(kind="n", title=title, sub=sub, main=secs[0], parts=parts))
    return chunks[0].strip(), nodes


def render_sits(doc, sits, chips):
    grid, cards = [], []
    for s in sits:
        grid.append(f'<a class="sbtn" data-tone="{s["tone"]}" href="#{s["id"]}"><b>{doc.inline(s["name"])}</b><span>{doc.inline(s["desc"])}</span></a>')
        secs = re.split(r"^#### ", s["body"], flags=re.M)
        if not re.search(r"^1\. ", secs[0], re.M):
            sys.exit(f"행동 순서 없는 카드: {s['name']}")
        inner = [doc.blocks(secs[0], s["id"], [0])]
        for sec in secs[1:]:
            name, content = (sec.split("\n", 1) + [""])[:2]
            name = name.strip()
            if name == "다음":
                inner.append(f'<h4 class="next">상황이 바뀌면</h4><div class="chips">{chips(BRANCH.findall(content))}</div>')
            elif name == "근거":
                inner.append(f'<details class="law"><summary>근거 조문</summary>{doc.blocks(content, s["id"], [0])}</details>')
            else:
                cls = SIT_PARTS.get(name, "plain")
                inner.append(f'<div class="part {cls}"><h4>{doc.inline(name)}</h4>{doc.blocks(content, s["id"], [0])}</div>')
        cards.append(f'<section class="sit" id="{s["id"]}" data-tone="{s["tone"]}" hidden><div class="sit-h"><h3>{doc.inline(s["name"])}</h3><a class="sit-x" href="#field">닫기</a></div><div class="sit-b">{"".join(inner)}</div></section>')
    return "".join(grid), "".join(cards)


def render_role(doc, role, sits=()):
    rid = ROLE_ID[role["name"]]
    quick, nodes = parse_nodes(role["body"])
    ids, no = {}, 0
    for i, s in enumerate(sits):
        s["id"] = f"sit-{i}"
        if s["name"] in ids:
            sys.exit(f"카드 제목 중복: {s['name']}")
        ids[s["name"]] = s["id"]
    for i, nd in enumerate(nodes):
        nd["id"] = f"{rid}-{i}"
        if nd["kind"] == "s":
            continue
        if nd["kind"] == "n":
            no += 1
            nd["no"] = no
            if nd["title"] in ids:
                sys.exit(f"칸 제목 중복: {nd['title']}")
            ids[nd["title"]] = nd["id"]
        else:
            ids[nd["title"]] = nd["id"]

    def chips(branches):
        out = []
        for ans, target in branches:
            target = target.strip()
            if target not in ids:
                sys.exit(f"없는 갈림길 대상: {target} ({role['name']})")
            out.append(f'<a class="chip" href="#{ids[target]}"><b>{doc.inline(ans)}</b><span>{doc.inline(target)}</span></a>')
        return "".join(out)

    lines = [l[2:] if l.startswith("> ") else l for l in quick.splitlines() if l.strip()]
    core = [l[4:] for l in lines if l.startswith("핵심: ")]
    quick = " ".join(l for l in lines if not l.startswith("핵심: "))
    out = [f'<section class="view" id="{rid}" data-color="{rid}"><div class="vh"><h2>{doc.inline(role["name"])}</h2><p>{doc.inline(role["desc"])}</p>']
    if sits:
        grid, cards = render_sits(doc, sits, chips)
        out.append('</div><div class="now">')
        if core:
            out.append(f'<p class="core">{doc.inline(core[0])}</p>')
        out.append(f'<h3>지금 상황을 누르세요</h3><div class="sitgrid">{grid}</div><p class="draft">검토용 초안입니다. 경찰청 공식 문서가 아닙니다.</p>{cards}</div>')
        out.append('<div class="vh"><h2 class="h2s">단계별 체크리스트</h2><p>출동 전부터 종결까지 할 일과 근거 조문입니다.</p>')
    if quick:
        out.append(f'<p class="quick">{doc.inline(quick)}</p>')
    out.append('<div class="tools"><button data-act="open">모두 펼치기</button><button data-act="close">모두 접기</button><button data-act="reset">체크 초기화</button><button data-act="print">인쇄</button></div></div><div class="flow">')
    for i, nd in enumerate(nodes):
        if nd["kind"] == "s":
            out.append(f'<div class="stage"><b>{doc.inline(nd["title"])}</b><span>{doc.inline(nd["sub"])}</span></div>')
            continue
        if nd["kind"] == "q":
            out.append(f'<div class="dec" id="{nd["id"]}"><p class="q">{doc.inline(nd["title"])}</p><div class="chips">{chips(nd["branches"])}</div></div>')
        else:
            counter = [0]
            inner = [doc.blocks(nd["main"], nd["id"], counter)]
            for name, cls in PARTS.items():
                if name not in nd["parts"]:
                    continue
                content = nd["parts"][name]
                if name == "다음":
                    inner.append(f'<div class="chips">{chips(BRANCH.findall(content))}</div>')
                elif name == "근거":
                    inner.append(f'<details class="law"><summary>근거 조문</summary>{doc.blocks(content, nd["id"], counter)}</details>')
                else:
                    inner.append(f'<div class="part {cls}"><h4>{name}</h4>{doc.blocks(content, nd["id"], counter)}</div>')
            sub = f"<small>{doc.inline(nd['sub'])}</small>" if nd["sub"] else ""
            out.append(f'<details class="node" id="{nd["id"]}"><summary><span class="no">{nd["no"]}</span><span class="tt"><b>{doc.inline(nd["title"])}</b>{sub}</span><span class="pg"></span></summary><div class="nb">{"".join(inner)}</div></details>')
        if i < len(nodes) - 1 and nodes[i + 1]["kind"] != "s":
            out.append('<div class="arrow" aria-hidden="true"></div>')
    out.append("</div></section>")
    return "".join(out)


def main():
    title, notice, roles, refs, sits = parse(SRC.read_text(encoding="utf-8"))
    if [r["name"] for r in roles] != list(ROLE_ID):
        sys.exit(f"역할 오류: {[r['name'] for r in roles]}")
    doc = Doc({r["name"]: f"ref-{i}" for i, r in enumerate(refs)})

    views = "".join(render_role(doc, r, sits if r["name"] == "현장 직원" else ()) for r in roles)
    cards = "".join(f'<a class="card" data-color="{ROLE_ID[r["name"]]}" href="#{ROLE_ID[r["name"]]}"><b>{doc.inline(r["name"])}</b><span>{doc.inline(r["desc"])}</span></a>' for r in roles)
    tabs = "".join(f'<a href="#{ROLE_ID[r["name"]]}" data-tab="{ROLE_ID[r["name"]]}">{doc.inline(r["name"])}</a>' for r in roles)

    ref_body = ['<section class="view" id="ref" data-color="ref"><div class="vh"><h2>참고 자료</h2><p>여러 역할이 함께 보는 기준입니다.</p></div>']
    for i, r in enumerate(refs):
        ref_body.append(f'<details class="node rf" id="ref-{i}"><summary><span class="tt"><b>{doc.inline(r["name"])}</b><small>{doc.inline(r["desc"])}</small></span></summary><div class="nb">{doc.blocks(r["body"], f"ref-{i}", [0])}</div></details>')
    ref_body.append("</section>")

    note = "".join(f"<p>{doc.inline(n)}</p>" for n in notice)
    page = TEMPLATE.read_text(encoding="utf-8")
    for key, val in {"{{TITLE}}": html.escape(title), "{{NOTICE}}": note, "{{CARDS}}": cards, "{{TABS}}": tabs, "{{VIEWS}}": views + "".join(ref_body)}.items():
        page = page.replace(key, val)
    OUT.write_text(page, encoding="utf-8")
    checks = page.count('type="checkbox"')
    nodes = page.count('class="node"')
    print(f"완료: {OUT.name} {len(page):,}자, 역할 {len(roles)}개, 흐름 칸 {nodes}개, 긴급 카드 {len(sits)}개, 체크항목 {checks}개, 참고 {len(refs)}개")


if __name__ == "__main__":
    main()
