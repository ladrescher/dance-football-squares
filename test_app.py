from pathlib import Path
import unittest,tempfile,os,subprocess,sys,time,json,urllib.request,urllib.error,concurrent.futures
class BoardTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('server.py'))],env=dict(os.environ,PORT='8189',ADMIN_TOKEN='test-secret',DATABASE_PATH=cls.tmp.name+'/board.db'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(60):
   try:cls.req('board');break
   except Exception:time.sleep(.1)
 @classmethod
 def tearDownClass(cls):cls.p.terminate();cls.p.wait();cls.tmp.cleanup()
 @staticmethod
 def req(path,body=None,admin=False):
  req=urllib.request.Request('http://127.0.0.1:8189/api/'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer test-secret'} if admin else {})})
  try:
   with urllib.request.urlopen(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_workflow(self):
  self.assertEqual(self.req('status',{'id':'x','status':'paid'})[0],401)
  self.assertEqual(self.req('reserve',{'name':'','dancer':'A','squares':[0]})[0],400)
  with concurrent.futures.ThreadPoolExecutor() as pool:results=list(pool.map(lambda _:self.req('reserve',{'name':'Supporter','dancer':'Dancer','squares':[0,1]}),range(2)))
  self.assertEqual(sorted(x[0] for x in results),[200,400])
  b=self.req('board')[1];self.assertEqual(len(b['squares']),2);self.assertNotIn('reservations',b);self.assertNotIn('dancer',b['squares'][0])
  self.assertEqual(self.req('draw',{},True)[0],400);self.req('settings',{'open':False},True);self.assertEqual(self.req('draw',{},True)[0],400)
  r=self.req('board',admin=True)[1]['reservations'][0];self.req('status',{'id':r['id'],'status':'paid'},True)
  self.assertEqual(self.req('draw',{},True)[0],200)
  b=self.req('board')[1]['settings'];self.assertEqual(sorted(b['rows']),list(range(10)));self.assertEqual(sorted(b['cols']),list(range(10)))
  self.assertEqual(self.req('draw',{},True)[0],400);self.assertEqual(self.req('settings',{'open':True},True)[0],400);self.assertEqual(self.req('status',{'id':r['id'],'status':'cancelled'},True)[0],400)
 def test_y_axis_colors(self):
  self.assertEqual(self.req('settings',dict(homeColor='#ffffff',awayColor='#ffb612'))[0],401)
  self.assertEqual(self.req('settings',dict(homeColor='#ffffff',awayColor='#ffb612'),True)[0],200)
  s=self.req('board')[1]['settings'];self.assertEqual(s['homeColor'],'#ffffff');self.assertEqual(s['awayColor'],'#ffb612')
  self.assertEqual(self.req('settings',dict(homeColor='red; color:black'),True)[0],400)
  self.assertEqual(self.req('board')[1]['settings']['homeColor'],'#ffffff')
 def test_z_multiple_boards(self):
  self.assertEqual(self.req('boards',{},True)[0],400)
  # Board 1 has two locked squares from the previous test; fill remaining
  # through a separate fresh board fixture database state for this test.
  import sqlite3
  with sqlite3.connect(self.tmp.name+'/board.db') as c:
   c.execute('UPDATE boards SET data=? WHERE id=1',(json.dumps(dict(open=True,rows=None,cols=None)),))
  self.assertEqual(self.req('reserve',dict(name='Filler',dancer='A',squares=list(range(2,100))))[0],200)
  self.assertEqual(self.req('boards',{},False)[0],401)
  code,r=self.req('boards',{},True);self.assertEqual(code,200);self.assertEqual(r['board'],2)
  self.assertEqual(self.req('boards',{},True)[0],400)
  self.assertEqual(self.req('reserve',dict(board=2,name='Second',dancer='B',phone='555-123-4567',email='supporter@example.com',squares=[0]))[0],200)
  self.assertEqual(len(self.req('board?board=1')[1]['squares']),100)
  self.assertEqual(len(self.req('board?board=2')[1]['squares']),1)
  public=self.req('board?board=2')[1]
  self.assertNotIn('phone',public['squares'][0]);self.assertNotIn('email',public['squares'][0])
  contact=[r for r in self.req('board?board=2',admin=True)[1]['reservations'] if r['board']==2][0]
  self.assertEqual(contact['phone'],'555-123-4567');self.assertEqual(contact['email'],'supporter@example.com')
  self.assertEqual(self.req('reserve',dict(board=2,name='Bad',dancer='B',email='invalid',squares=[1]))[0],400)
  self.req('settings',dict(board=2,open=False),True)
  r=[r for r in self.req('board?board=2',admin=True)[1]['reservations'] if r['board']==2][0]
  self.req('status',dict(board=2,id=r['id'],status='paid'),True)
  self.assertEqual(self.req('draw',dict(board=2),True)[0],200)
  self.assertIsNone(self.req('board?board=1')[1]['settings']['rows'])
  self.assertIsNotNone(self.req('board?board=2')[1]['settings']['rows'])
 def test_zz_cancellation(self):
  self.assertEqual(self.req('cancel-board',dict(board=2),True)[0],400)
  import sqlite3
  with sqlite3.connect(self.tmp.name+'/board.db') as c:
   c.execute('UPDATE boards SET data=? WHERE id=2',(json.dumps(dict(open=True,rows=None,cols=None)),))
  self.assertEqual(self.req('cancel-board',dict(board=2))[0],401)
  self.assertEqual(self.req('cancel-board',dict(board=2),True)[0],200)
  b=self.req('board?board=2',admin=True)[1]
  self.assertTrue(b['settings']['cancelled']);self.assertFalse(b['settings']['open']);self.assertEqual(len(b['squares']),1)
  self.assertEqual(len(self.req('board?board=1')[1]['squares']),100)
  self.assertEqual(self.req('reserve',dict(board=2,name='N',dancer='D',squares=[1]))[0],400)
  self.assertEqual(self.req('settings',dict(board=2,open=True),True)[0],400)
  self.assertEqual(self.req('draw',dict(board=2),True)[0],400)
  r=[r for r in b['reservations'] if r['board']==2][0]
  self.assertEqual(self.req('status',dict(board=2,id=r['id'],status='cancelled'),True)[0],400)
  self.assertEqual(self.req('refund',dict(board=2,id=r['id'],refunded=True),True)[0],200)
  b=self.req('board?board=2',admin=True)[1];self.assertEqual([r for r in b['reservations'] if r['id']==r['id'] and r['board']==2][0]['refunded'],1)
  self.assertEqual(self.req('boards',dict(board=2),True)[0],200)
 def test_zzz_reset_fundraiser(self):
  before=self.req('board',admin=True)[1]
  self.assertEqual(self.req('reset-fundraiser',{'confirmation':'RESET ENTIRE FUNDRAISER'})[0],401)
  self.assertEqual(self.req('reset-fundraiser',{},True)[0],400)
  self.assertEqual(len(self.req('board',admin=True)[1]['reservations']),len(before['reservations']))
  self.assertEqual(self.req('reset-fundraiser',{'confirmation':'RESET ENTIRE FUNDRAISER'},True)[0],200)
  after=self.req('board',admin=True)[1]
  self.assertEqual([b['id'] for b in after['boards']],[1]);self.assertEqual(after['squares'],[]);self.assertEqual(after['reservations'],[])
  self.assertTrue(after['settings']['open']);self.assertIsNone(after['settings']['rows']);self.assertEqual(after['settings']['organizer'],before['settings']['organizer'])
  backups=list(Path(self.tmp.name).glob('backups/*.db'));self.assertEqual(len(backups),1)
  import sqlite3
  with sqlite3.connect(backups[0]) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],len(before['reservations']))
if __name__=='__main__':unittest.main()
