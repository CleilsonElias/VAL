"""Create a publication-style DOCX while preserving Pandoc's native OMML math.

Requires Pandoc and python-docx. Rendering is a separate verification step.
"""
from pathlib import Path
import subprocess

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT.parent/"output"/"VAL_Revised_Manuscript_2026-11-11.docx"


def font_style(style,name,size,bold=False):
    style.font.name=name
    style.font.size=Pt(size)
    style.font.bold=bold
    style.font.color.rgb=RGBColor(0,0,0)
    props=style.element.get_or_add_rPr()
    fonts=props.find(qn('w:rFonts'))
    if fonts is None:
        fonts=OxmlElement('w:rFonts')
        props.insert(0,fonts)
    for key in ('ascii','hAnsi','eastAsia','cs'):
        fonts.set(qn('w:'+key),name)
    for tag in ('w:color',):
        for el in props.findall(qn(tag)):
            el.attrib.pop(qn('w:themeColor'),None)


def main():
    raw=ROOT/"manuscript/pandoc_manuscript.docx"
    subprocess.run(['pandoc','VAL_Revised_Manuscript_2026-11-11.md',
                    '--from','markdown+tex_math_dollars-implicit_figures','--to','docx',
                    '--output',str(raw)],cwd=ROOT/'manuscript',check=True)
    doc=Document(raw)
    # Pandoc can capitalize built-in style names differently from python-docx's
    # built-in-name lookup; retain the actual style objects by their UI names.
    available={style.name:style for style in doc.styles}
    for section in doc.sections:
        section.page_width=Inches(8.5)
        section.page_height=Inches(11)
        section.top_margin=Inches(.78)
        section.bottom_margin=Inches(.95)
        section.left_margin=Inches(.95)
        section.right_margin=Inches(.95)
        section.header_distance=Inches(.28)
        section.footer_distance=Inches(.30)
    for name in ['Normal','Body Text','First Paragraph']:
        if name in available:
            style=available[name]
            font_style(style,'Liberation Serif',11)
            style.paragraph_format.line_spacing=1.08
            style.paragraph_format.space_after=Pt(6)
            style.paragraph_format.space_before=Pt(0)
            style.paragraph_format.widow_control=True
    for name,size in [('Title',18),('Subtitle',11),('Author',11),('Date',10)]:
        if name in available:
            style=available[name]
            font_style(style,'Liberation Serif',size,bold=(name=='Title'))
            style.paragraph_format.space_after=Pt(6)
            style.paragraph_format.keep_with_next=True
            style.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
            for border in style.element.xpath('.//w:pBdr'):
                border.getparent().remove(border)
    for name,size in [('Heading 1',13),('Heading 2',11.6),('Heading 3',11)]:
        style=available[name]
        font_style(style,'Liberation Sans',size,True)
        style.paragraph_format.space_before=Pt(10)
        style.paragraph_format.space_after=Pt(5)
        style.paragraph_format.keep_with_next=True
        style.paragraph_format.keep_together=True
        style.paragraph_format.page_break_before=False
    for name in ['Caption','Image Caption','Table Caption']:
        if name in available:
            font_style(available[name],'Liberation Serif',9.5)
    for name in ['Source Code','Verbatim Char']:
        if name in available:
            font_style(available[name],'Liberation Mono',9)
    if 'Source Code' in available:
        available['Source Code'].paragraph_format.line_spacing=1.0
    # Remove decorative paragraph borders in title blocks and headings.
    for p in doc.paragraphs:
        if p.style.name in ('Title','Subtitle','Author','Date') or p.style.name.startswith('Heading'):
            for border in p._p.xpath('./w:pPr/w:pBdr'):
                border.getparent().remove(border)
        if p.style.name in ('Author','Date'):
            p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        if p.text.startswith(('Independent researcher','Contact:')):
            p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after=Pt(4)
            for r in p.runs:
                r.font.size=Pt(10)
        if p.text.startswith('Table '):
            p.paragraph_format.keep_with_next=True
            for r in p.runs:
                r.font.size=Pt(9.5)
                r.font.bold=True
        if p.text.startswith('Figure 1.'):
            p.paragraph_format.keep_together=True
            for r in p.runs:
                r.font.size=Pt(9.5)
        if p._p.xpath('.//w:drawing'):
            p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next=True
        if p._p.xpath('.//m:oMathPara'):
            p.paragraph_format.space_before=Pt(4)
            p.paragraph_format.space_after=Pt(7)
            p.paragraph_format.keep_together=True
            previous=p._p.getprevious()
            if previous is not None and previous.tag==qn('w:p'):
                from docx.text.paragraph import Paragraph
                Paragraph(previous,p._parent).paragraph_format.keep_with_next=True
    for shape in doc.inline_shapes:
        if shape.width>Inches(6.3):
            ratio=Inches(6.3)/shape.width
            shape.width=Inches(6.3)
            shape.height=int(shape.height*ratio)
    widths=[(0.52,2.20,1.95,1.93),(3.30,1.10,1.10,1.10),(3.30,1.10,1.10,1.10),
            (1.45,1.85,1.12,2.18),(1.73,2.37,2.50)]
    for table_index,(table,widths_in) in enumerate(zip(doc.tables,widths)):
        table.alignment=WD_TABLE_ALIGNMENT.CENTER
        table.autofit=False
        for col,width in zip(table.columns,widths_in):
            col.width=Inches(width)
        props=table._tbl.tblPr
        borders=OxmlElement('w:tblBorders')
        for edge in ['top','left','bottom','right','insideH','insideV']:
            item=OxmlElement('w:'+edge)
            item.set(qn('w:val'),'single')
            item.set(qn('w:sz'),'4')
            item.set(qn('w:color'),'D9D9D9')
            borders.append(item)
        props.append(borders)
        for i,row in enumerate(table.rows):
            trpr=row._tr.get_or_add_trPr()
            cant=OxmlElement('w:cantSplit')
            trpr.append(cant)
            if i==0:
                repeat=OxmlElement('w:tblHeader')
                trpr.append(repeat)
            for j,(cell,width) in enumerate(zip(row.cells,widths_in)):
                cell.width=Inches(width)
                cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                tcpr=cell._tc.get_or_add_tcPr()
                shd=OxmlElement('w:shd')
                shd.set(qn('w:fill'),'343B43' if i==0 else ('F3F4F5' if i%2==0 else 'FFFFFF'))
                tcpr.append(shd)
                margins=OxmlElement('w:tcMar')
                for edge in ['top','bottom','left','right']:
                    margin=OxmlElement('w:'+edge)
                    margin.set(qn('w:w'),'85')
                    margin.set(qn('w:type'),'dxa')
                    margins.append(margin)
                tcpr.append(margins)
                for p in cell.paragraphs:
                    p.paragraph_format.space_after=Pt(2)
                    p.paragraph_format.space_before=Pt(2)
                    p.paragraph_format.line_spacing=1.0
                    numeric=(table_index in (1,2) and j>0) or (table_index==3 and j>1)
                    p.alignment=WD_ALIGN_PARAGRAPH.CENTER if numeric else WD_ALIGN_PARAGRAPH.LEFT
                    for r in p.runs:
                        r.font.name='Liberation Serif'
                        r.font.size=Pt(9.3)
                        r.font.bold=(i==0)
                        r.font.color.rgb=RGBColor(255,255,255) if i==0 else RGBColor(0,0,0)
        after=table._tbl.getnext()
        if after is not None and after.tag==qn('w:p'):
            from docx.text.paragraph import Paragraph
            Paragraph(after,table._parent).paragraph_format.space_before=Pt(8)
    # Footers supply navigation for this long technical article.
    for section in doc.sections:
        footer=section.footer.paragraphs[0]
        footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
        run=footer.add_run()
        field=OxmlElement('w:fldSimple')
        field.set(qn('w:instr'),'PAGE')
        run._r.addnext(field)
    doc.core_properties.title='VAL for Domain Selective Memory Admission and Retrieval'
    doc.core_properties.author='Cleilson Elias de Sousa'
    doc.core_properties.subject='Revised formulation and controlled episodic retrieval study'
    doc.core_properties.keywords='VAL; domain selective memory; admission; retrieval; controlled comparison'
    # LibreOffice can misrender the right side of native stretchable square
    # delimiters as ')'. Keep their editable content and literal square glyphs.
    math_namespace='http://schemas.openxmlformats.org/officeDocument/2006/math'
    tag=lambda name:'{'+math_namespace+'}'+name
    for delimiter in list(doc._element.iter(tag('d'))):
        props=delimiter.find(tag('dPr'))
        begin=props.find(tag('begChr')) if props is not None else None
        end=props.find(tag('endChr')) if props is not None else None
        if (begin is not None and end is not None and
                begin.get(tag('val'))=='[' and end.get(tag('val'))==']'):
            parent=delimiter.getparent()
            position=parent.index(delimiter)
            replacement=[]
            for glyph in ['[',']']:
                run=OxmlElement('m:r')
                text=OxmlElement('m:t')
                text.text=glyph
                run.append(text)
                replacement.append(run)
            content=[]
            for entry in delimiter.findall(tag('e')):
                content.extend(list(entry))
            parent.remove(delimiter)
            for offset,element in enumerate([replacement[0],*content,replacement[1]]):
                parent.insert(position+offset,element)
    OUTPUT.parent.mkdir(exist_ok=True,parents=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__=='__main__':
    main()
