# -*- coding: utf-8 -*-
"""按官方模板生成两份提交文档（金砖大赛 2026 · A-159）。

用法：python -I build.py
"""
from __future__ import annotations

import re
import sys
from copy import deepcopy
from pathlib import Path

import docx
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

HERE = Path(__file__).resolve().parent
TEMPLATE_DIR = Path(
    r"D:/user/HUAWEI/OneDrive/Desktop/temp3/article2/投稿期刊/"
    r"电化教育研究_CSSCI 来源 (2025-2026)＋北大核心＋AMI 核心＋RCCSE A+"
)
OUT_DIR = HERE / "output"

BODY_SIZE = 10.5       # 五号
LINE_PT = 15.0         # 固定值 15 磅，与模板空段一致
INDENT_TWIPS = 420     # 2 字符（10.5pt * 2 = 21pt = 420 twips）

APPENDIX = {
    "works": (
        "本说明书配套材料包括：技术报告、设计与开发文档、测试数据与性能指标报告、"
        "核心代码与算法实现说明、演示视频与答辩演示文稿；支撑材料包括软件著作权登记证书、"
        "企业技术合作合同、任课教师使用评价，以及中国日报网、江西新闻网相关报道。"
        "文中引用的评测与性能数据均取自《测试数据与性能指标报告》，采集于 2026 年 10 月 12 日"
        "的本机演示环境，原始数据文件索引与复现步骤见该报告第六章。"
    ),
    "security": (
        "本说明书配套材料包括：技术报告、设计与开发文档、测试数据与性能指标报告、"
        "安全测试用例与接口抽检记录、核心安全模块实现说明（输入过滤、事实校验、审计留痕、"
        "判题沙箱与反向代理门禁）；支撑材料包括软件著作权登记证书与任课教师使用评价。"
        "文中引用的测试数据采集于 2026 年 10 月 12 日的本机演示环境，"
        "测试口径、原始记录与复现步骤见《测试数据与性能指标报告》。"
    ),
}


def set_run_font(run, size=BODY_SIZE, bold=False, ea="宋体", latin="Times New Roman"):
    run.font.size = Pt(size)
    run.bold = bold
    run.font.name = latin
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), ea)


def style_body_paragraph(p, indent=True):
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(LINE_PT)

    ppr = p._p.get_or_add_pPr()
    ind = ppr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        ppr.append(ind)
    if indent:
        ind.set(qn("w:firstLine"), str(INDENT_TWIPS))
        ind.set(qn("w:firstLineChars"), "200")
    else:
        ind.set(qn("w:firstLine"), "0")
        ind.set(qn("w:firstLineChars"), "0")


def clear_cell(cell):
    tc = cell._tc
    for p in tc.findall(qn("w:p")):
        tc.remove(p)


def fill_cell(cell, paragraphs, indent=True):
    clear_cell(cell)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    for item in paragraphs:
        p = cell.add_paragraph()
        style_body_paragraph(p, indent=indent)
        if item[0] == "p":
            r = p.add_run(item[1])
            set_run_font(r)
        elif item[0] == "b":
            r1 = p.add_run(item[1])
            set_run_font(r1, bold=True, ea="黑体")
            r2 = p.add_run(item[2])
            set_run_font(r2)
        else:
            raise ValueError(item[0])


def set_cover(doc, meta):
    paras = doc.paragraphs
    mapping = {
        "项目名称": f"项目名称：{meta['project']}",
        "参赛编号": f"参赛编号：{meta['number']}",
        "参赛组别": f"参赛组别：{meta['group']}",
    }
    for p in paras:
        text = p.text.strip()
        if text.startswith("项目名称") and p.runs:
            # 项目名较长，拆为「项目名称：智课共生」+ 换行缩进的副标题，避免折行断字
            run = p.runs[0]
            run.text = "项目名称：智课共生"
            for extra in p.runs[1:]:
                extra.text = ""
            br = OxmlElement("w:br")
            tail = OxmlElement("w:t")
            tail.set(qn("xml:space"), "preserve")
            tail.text = "——多智能体个性化互动学习系统"
            run._element.append(br)
            run._element.append(tail)
            ppr = p._p.get_or_add_pPr()
            ind = ppr.find(qn("w:ind"))
            if ind is None:
                ind = OxmlElement("w:ind")
                ppr.append(ind)
            ind.set(qn("w:left"), "3426")
            ind.set(qn("w:hanging"), "1300")
            if ind.get(qn("w:firstLine")) is not None:
                del ind.attrib[qn("w:firstLine")]
            continue
        for key, new in mapping.items():
            if text.startswith(key) and p.runs:
                p.runs[0].text = new
                for extra in p.runs[1:]:
                    extra.text = ""
                break
        if text.startswith("（填") and "模" in text:
            p._p.getparent().remove(p._p)
        elif text.strip() == "二〇二六年十月":
            if p.runs:
                p.runs[0].text = "二〇二六年十一月"


def drop_template_hint(cell):
    """删除单元格首段的填写提示（如「（800字／背景·痛点·用户·价值）」）。"""
    for p in list(cell.paragraphs):
        if "字／" in p.text or p.text.strip().startswith("（") and "／" in p.text:
            p._p.getparent().remove(p._p)


def count_chars(sections):
    total = 0
    for title, items in sections:
        n = 0
        for it in items:
            n += len(it[1]) + (len(it[2]) if it[0] == "b" else 0)
        total += n
        print(f"  {title}: {n} 字")
    print(f"  合计：{total} 字")


def build(module_name, template_name, out_name, appendix, extra_fix=None):
    sys.path.insert(0, str(HERE))
    meta = __import__(module_name)

    src = TEMPLATE_DIR / template_name
    doc = docx.Document(str(src))

    set_cover(doc, {
        "project": meta.PROJECT,
        "number": meta.NUMBER,
        "group": meta.GROUP,
    })

    table = doc.tables[0]
    body_rows = [table.rows[i] for i in range(1, len(table.rows), 2)]
    for (title, items), row in zip(meta.SECTIONS, body_rows):
        cell = row.cells[0]
        drop_template_hint(cell)
        fill_cell(cell, items)

    # 附录行
    appendix_cell = table.rows[-1].cells[0]
    drop_template_hint(appendix_cell)
    fill_cell(appendix_cell, [("p", appendix)])

    if extra_fix:
        extra_fix(doc)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / out_name
    doc.save(str(out))
    print(f"[saved] {out}")
    print("字数统计：")
    count_chars(meta.SECTIONS)
    return out


if __name__ == "__main__":
    build(
        "content_works",
        "项目作品说明文档（模板）.docx",
        "A-159_智课共生_项目作品说明文档.docx",
        APPENDIX["works"],
    )
    build(
        "content_security",
        "安全架构专项设计说明书（模板）.docx",
        "A-159_智课共生_安全架构专项设计说明书.docx",
        APPENDIX["security"],
    )
