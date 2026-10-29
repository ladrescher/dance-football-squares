import unittest,sqlite3,json
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from excel_export import export_totals
class ExportTest(unittest.TestCase):
 def test_totals_and_literal_names(self):
  c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
  c.executescript('CREATE TABLE settings(id INTEGER,data TEXT); CREATE TABLE reservations(id TEXT,board INTEGER,dancer TEXT,status TEXT,name TEXT DEFAULT "Supporter",refunded INTEGER DEFAULT 0); CREATE TABLE boards(id INTEGER,data TEXT); CREATE TABLE squares(n INTEGER,reservation TEXT);')
  c.execute('INSERT INTO settings VALUES(1,?)',(json.dumps({'price':20}),))
  c.executemany('INSERT INTO reservations(id,board,dancer,status) VALUES(?,?,?,?)',[('a',1,'=Dancer & A','paid'),('b',2,'=Dancer & A','pending'),('c',2,'Cancelled','cancelled')])
  c.executemany('INSERT INTO boards VALUES(?,?)',[(1,'{}'),(2,'{}')])
  c.executemany('INSERT INTO squares VALUES(?,?)',[(0,'a'),(1,'a'),(0,'b'),(1,'c')])
  with ZipFile(BytesIO(export_totals(c))) as z:
   for name in z.namelist():ET.fromstring(z.read(name))
   ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
   sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));cells=sheet.findall('s:sheetData/s:row',ns)[1].findall('s:c',ns)
   self.assertEqual(cells[0].find('s:is/s:t',ns).text,'=Dancer & A')
   self.assertEqual([float(x.find('s:v',ns).text) for x in cells[1:]],[3,60,40,20])
   self.assertNotIn(b'<f>',z.read('xl/worksheets/sheet1.xml'))
   self.assertNotIn(b'Cancelled',z.read('xl/worksheets/sheet1.xml'))
   self.assertEqual(len(ET.fromstring(z.read('xl/worksheets/sheet2.xml')).findall('s:sheetData/s:row',ns)),3)
  c.execute('UPDATE boards SET data=? WHERE id=1',('{"cancelled":true}',))
  with ZipFile(BytesIO(export_totals(c))) as z:
   sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));cells=sheet.findall('s:sheetData/s:row',ns)[1].findall('s:c',ns)
   self.assertEqual([float(x.find('s:v',ns).text) for x in cells[1:]],[1,20,0,20])
   self.assertIn(b'Cancelled',z.read('xl/worksheets/sheet2.xml'))
   self.assertIn(b'Refund due',z.read('xl/worksheets/sheet3.xml'))
if __name__=='__main__':unittest.main()

