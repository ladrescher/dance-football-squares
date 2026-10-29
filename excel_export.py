"""Dependency-free Excel export for the deployed app."""
from io import BytesIO
from zipfile import ZipFile,ZIP_DEFLATED
from xml.sax.saxutils import escape
from collections import defaultdict
from decimal import Decimal

def export_totals(c):
 price=Decimal(str(__import__('json').loads(c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0])['price']))
 cancelled={r['id'] for r in c.execute('SELECT * FROM boards') if __import__('json').loads(r['data']).get('cancelled',False)}
 groups=defaultdict(lambda:[0,0])
 for r in c.execute("SELECT r.board,r.dancer,r.status,COUNT(s.n) AS n FROM reservations r JOIN squares s ON s.reservation=r.id WHERE r.status!='cancelled' GROUP BY r.board,r.dancer,r.status"):
  t=groups[(r['board'],r['dancer'])];t[0]+=r['n'];t[1]+=r['n'] if r['status']=='paid' else 0
 combined=defaultdict(lambda:[0,0])
 for (board,d),v in groups.items():
  if board in cancelled:continue
  combined[d][0]+=v[0];combined[d][1]+=v[1]
 def values(name,v):return [name,v[0],float(v[0]*price),float(v[1]*price),float((v[0]-v[1])*price)]
 headers=['Dancer','Squares reserved','Total pledged (USD)','Collected (USD)','Outstanding (USD)']
 summary=[headers]+[values(d,v) for d,v in sorted(combined.items(),key=lambda x:x[0].casefold())]
 detail=[['Board']+headers+['Board status']]+[[b]+values(d,v)+['Cancelled — excluded from summary' if b in cancelled else 'Active'] for (b,d),v in sorted(groups.items(),key=lambda x:(x[0][0],x[0][1].casefold()))]
 refunds=[['Board','Supporter','Dancer','Paid amount (USD)','Refund status']]
 for row in c.execute("SELECT r.*,COUNT(s.n) AS n FROM reservations r JOIN squares s ON s.reservation=r.id WHERE r.status='paid' GROUP BY r.id"):
  if row['board'] in cancelled:refunds.append([row['board'],row['name'],row['dancer'],float(row['n']*price),'Refund recorded' if row['refunded'] else 'Refund due'])
 def column(n):
  result=''
  while n:n,r=divmod(n-1,26);result=chr(65+r)+result
  return result
 def sheet(rows,offset):
  out=['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>']
  for i in range(len(rows[0])):out.append(f'<col min="{i+1}" max="{i+1}" width="{32 if i==offset else 24}" customWidth="1"/>')
  out.append('</cols><sheetData>')
  for rn,row in enumerate(rows,1):
   out.append(f'<row r="{rn}" ht="{28 if rn==1 else 21}" customHeight="1">')
   for cn,value in enumerate(row,1):
    ref=f'{column(cn)}{rn}';style=1 if rn==1 else 2 if cn>=3+offset and isinstance(value,(int,float)) else 0
    if isinstance(value,(int,float)):out.append(f'<c r="{ref}" s="{style}"><v>{value}</v></c>')
    else:out.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>')
   out.append('</row>')
  out.append(f'</sheetData><autoFilter ref="A1:{column(len(rows[0]))}{len(rows)}"/></worksheet>')
  return ''.join(out)
 styles='''<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF00338D"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs></styleSheet>'''
 buf=BytesIO()
 with ZipFile(buf,'w',ZIP_DEFLATED) as z:
  z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in [1,2,3])+'</Types>')
  z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
  z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="All boards" sheetId="1" r:id="rId1"/><sheet name="By board" sheetId="2" r:id="rId2"/><sheet name="Refund tracking" sheetId="3" r:id="rId3"/></sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in [1,2,3])+'<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
  z.writestr('xl/styles.xml',styles)
  z.writestr('xl/worksheets/sheet3.xml',sheet(refunds,1))
  z.writestr('xl/worksheets/sheet1.xml',sheet(summary,0));z.writestr('xl/worksheets/sheet2.xml',sheet(detail,1))
 return buf.getvalue()
