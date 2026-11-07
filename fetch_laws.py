"""국가법령정보센터에서 근거 법령의 조문을 받아 laws.json을 만든다. 사용법: python fetch_laws.py

MANUAL.md의 '근거 법령' 표에 적힌 법령을 받는다. 법이 바뀌면 다시 돌린 뒤 python build.py를 실행한다.
받지 못한 법령은 laws.json에서 빠지고, 매뉴얼에서는 그 법령의 조항이 일반 글자로 남는다.
"""
import datetime
import html
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "laws.json"
BASE = "https://www.law.go.kr/LSW/"
TODAY = datetime.date.today().strftime("%Y%m%d")
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")


def plain(page):
    page = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", page)
    page = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", page)
    page = html.unescape(re.sub(r"<[^>]+>", " ", page))
    return re.sub(r"[ \t\r\f\v\xa0]+", " ", page)


def tidy(text):
    """한 줄로 뭉친 조문을 항·호 단위로 줄을 나눈다."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"<[^<>]*(?:개정|신설|삭제)[^<>]*>|\[[^\[\]]*(?:개정|신설|이동|제목|시행일)[^\[\]]*\]", "", text).strip()
    text = re.sub(rf"\s*([{CIRCLED}])", r"\n\1", text)
    text = re.sub(r" (\d{1,2}\. )", r"\n\1", text)
    text = re.sub(r"(?<=[.다]) ([가-하]\. )", r"\n\1", text)
    return text.strip()


def articles(page):
    """법령 사이트가 조 제목에 붙이는 label을 경계로 조문을 나눈다."""
    page = re.sub(r'<span class="sfon\d?">[\s\S]*?</span>', " ", page)
    heads = list(re.finditer(r'<label for="Y\d+">\s*(제\d+조(?:의\d+)?)\s*\(', page))
    out = {}
    for n, m in enumerate(heads):
        stop = heads[n + 1].start() if n + 1 < len(heads) else len(page)
        body = plain(page[m.start():stop])
        body = re.split(r"\s부\s*칙\s", body)[0]
        out.setdefault(m.group(1), tidy(body))
    return out


def sections(text):
    """물리력 규칙처럼 1.1 / 3.9.3 번호로 된 규칙을 나눈다."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    start = next((i for i, l in enumerate(lines) if re.match(r"1\.\s*총칙|1\.1\.", l)), None)
    if start is None:
        return {}
    out, key = {}, None
    for line in lines[start:]:
        m = re.match(r"(\d\.\d+(?:\.\d+)?)\.?\s", line + " ")
        if m:
            key = m.group(1)
            out.setdefault(key, [])
        if key:
            out[key].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def statute(name):
    page = get(BASE + "lsInfoP.do?lsNm=" + urllib.parse.quote(name))
    val = {}
    for k in ("lsiSeq", "ancYd", "ancNo"):
        m = re.search(rf'(?:id|name)="{k}"[^>]*value="([^"]*)"', page)
        val[k] = m.group(1) if m else ""
    dates = re.findall(r"efYd[^0-9]{0,12}(\d{8})", page)
    ef = max((d for d in dates if d <= TODAY), default=dates[0] if dates else "")
    query = urllib.parse.urlencode(dict(val, efYd=ef, chrClsCd="010202", urlMode="lsInfoP", viewCls="lsInfoP", ancYnChk="0", nwJoYnInfo="Y"))
    page = get(BASE + "lsInfoR.do?" + query)
    return {"kind": "법령", "effective": ef, "url": "https://www.law.go.kr/법령/" + name.replace(" ", ""), "articles": articles(page)}


def rule(name):
    page = get(BASE + "admRulLsInfoP.do?admRulNm=" + urllib.parse.quote(name))
    seq = re.search(r'admRulSeq\s*[:=]\s*"?(\d+)', page).group(1)
    page = get(BASE + "admRulInfoR.do?admRulSeq=" + seq)
    arts = articles(page) or sections(plain(page))
    label = re.sub(r"^\(경찰청\)\s*", "", name)
    return {"kind": "행정규칙", "effective": "", "url": "https://www.law.go.kr/행정규칙/" + label.replace(" ", ""), "articles": arts}


def wanted():
    src = (ROOT / "MANUAL.md").read_text(encoding="utf-8")
    part = src[src.index("## [참고] 근거 법령"):src.index("## [참고] 확인 필요 사항")]
    names, kind = [], statute
    for line in part.splitlines():
        if "행정규칙" in line and line.startswith("**"):
            kind = rule
        m = re.match(r"\|\s*([^|]+?)\s*\|", line)
        if m and not re.match(r"[-법규]|법령|규칙\s*$", m.group(1)[:3]) or (m and m.group(1)[0] in "법규" and len(m.group(1)) > 3):
            names.append((re.sub(r"\s*\(수사준칙\)", "", m.group(1)), kind))
    return names


def main():
    laws, failed = {}, []
    for name, fetch in wanted():
        try:
            item = fetch(name)
            if not item["articles"]:
                raise ValueError("조문 없음")
            laws[re.sub(r"^\(경찰청\)\s*", "", name)] = item
            print(f"{name}: {len(item['articles'])}개")
        except Exception as e:
            failed.append(name)
            print(f"{name}: 실패 ({e})")
    OUT.write_text(json.dumps({"fetched": TODAY, "laws": laws}, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"완료: {len(laws)}개 법령, 실패 {len(failed)}개 {failed}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
