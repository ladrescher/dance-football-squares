import os,json,sqlite3,secrets,hmac,time,re
from urllib.parse import urlparse,parse_qs
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from excel_export import export_totals
ROOT=Path(__file__).parent
DB=os.environ.get('DATABASE_PATH',str(ROOT/'data'/'board.db'))
Path(DB).parent.mkdir(parents=True,exist_ok=True)
KEY_FILE=Path(DB).parent/'organizer-key'
TOKEN=os.environ.get('ADMIN_TOKEN') or (KEY_FILE.read_text().strip() if KEY_FILE.exists() else secrets.token_urlsafe(24))
if not os.environ.get('ADMIN_TOKEN') and not KEY_FILE.exists(): print('Temporary organizer key: '+TOKEN,flush=True)
def connect():
 c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; return c
if os.environ.get('REQUIRE_ADMIN_TOKEN')=='1' and not os.environ.get('ADMIN_TOKEN'):
 raise RuntimeError('ADMIN_TOKEN must be configured before public hosting.')
with connect() as c:
 c.executescript('CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY, data TEXT); CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY,name TEXT,dancer TEXT,status TEXT,created INTEGER); CREATE TABLE IF NOT EXISTS squares(n INTEGER PRIMARY KEY,reservation TEXT REFERENCES reservations(id));')
 seed_path=ROOT/'fundraiser-settings.json'
 if seed_path.exists() and not c.execute('SELECT 1 FROM settings WHERE id=1').fetchone():
  seed=json.loads(seed_path.read_text());seed.update(open=True,rows=None,cols=None,cancelled=False)
  c.execute('INSERT INTO settings VALUES(1,?)',(json.dumps(seed),))
 c.execute('INSERT OR IGNORE INTO settings VALUES(1,?)',(json.dumps(dict(organizer='Sam Smith School of Dance',contact='',price=20,venmo='',payment='Payment instructions coming soon. Please wait for organizer confirmation.',rules='Prize and payout rules will be announced before sales open.',game='Buffalo Bills vs. Kansas City Chiefs • Thanksgiving',opponent='Kansas City Chiefs',open=True,rows=None,cols=None)),))
 # Migrate the original board without losing reservations or its draw.
 c.execute('CREATE TABLE IF NOT EXISTS boards(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT NOT NULL)')
 c.execute('INSERT OR IGNORE INTO boards VALUES(1,?)',(c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0],))
 if 'board' not in [r[1] for r in c.execute('PRAGMA table_info(reservations)')]:
  c.execute('ALTER TABLE reservations ADD COLUMN board INTEGER NOT NULL DEFAULT 1')
 if 'board' not in [r[1] for r in c.execute('PRAGMA table_info(squares)')]:
  c.execute('ALTER TABLE squares RENAME TO old_squares')
  c.execute('CREATE TABLE squares(board INTEGER NOT NULL,n INTEGER NOT NULL,reservation TEXT NOT NULL,PRIMARY KEY(board,n))')
  c.execute('INSERT INTO squares SELECT 1,n,reservation FROM old_squares')
  c.execute('DROP TABLE old_squares')
 if 'refunded' not in [r[1] for r in c.execute('PRAGMA table_info(reservations)')]:
  c.execute('ALTER TABLE reservations ADD COLUMN refunded INTEGER NOT NULL DEFAULT 0')
 for field in ['phone','email']:
  if field not in [r[1] for r in c.execute('PRAGMA table_info(reservations)')]:
   c.execute('ALTER TABLE reservations ADD COLUMN '+field+" TEXT NOT NULL DEFAULT ''")
def settings(c,board=1):
 global_settings=json.loads(c.execute('SELECT data FROM settings WHERE id=1').fetchone()[0])
 row=c.execute('SELECT data FROM boards WHERE id=?',(board,)).fetchone()
 if not row:raise ValueError('Board not found')
 local=json.loads(row[0])
 for k in ['open','rows','cols']:global_settings[k]=local[k]
 global_settings.setdefault('fundraiserHeading','Thanksgiving Football Squares')
 global_settings.setdefault('homeTeam','Buffalo Bills')
 global_settings.setdefault('homeColor','#00338d')
 global_settings.setdefault('awayColor','#c82242')
 global_settings.setdefault('boardMessage','Once a board has been sold out numbers will be drawn and a new board will be added to purchases squares')
 global_settings['cancelled']=local.get('cancelled',False)
 return global_settings
class Handler(BaseHTTPRequestHandler):
 def send(self,status,data):
  b=json.dumps(data).encode(); self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def admin(self): return hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+TOKEN)
 def do_GET(self):
  if self.path.split('?')[0]=='/api/export':
   if not self.admin():return self.send(401,{'error':'Organizer key required'})
   with connect() as c:
    c.execute('BEGIN');b=export_totals(c)
   self.send_response(200);self.send_header('Content-Type','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');self.send_header('Content-Disposition','attachment; filename="dancer-totals.xlsx"');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  if self.path.split('?')[0]=='/api/board':
   with connect() as c:
    raw=parse_qs(urlparse(self.path).query).get('board',['1'])[0]
    if not raw.isdigit() or not c.execute('SELECT 1 FROM boards WHERE id=?',(raw,)).fetchone():return self.send(404,{'error':'Board not found'})
    board=int(raw);s=settings(c,board); squares=[dict(x) for x in c.execute('SELECT squares.n,reservations.name,reservations.status FROM squares JOIN reservations ON reservation=id WHERE squares.board=?',(board,))]
    data=dict(settings=s,squares=squares,board=board,boards=[dict(id=x['id'],reserved=c.execute('SELECT COUNT(*) FROM squares WHERE board=?',(x['id'],)).fetchone()[0],cancelled=json.loads(x['data']).get('cancelled',False),**{k:json.loads(x['data'])[k] for k in ['open','rows']}) for x in c.execute('SELECT * FROM boards ORDER BY id')])
    if self.admin(): data['reservations']=[dict(x)|{'squares':[r[0] for r in c.execute('SELECT n FROM squares WHERE reservation=?',(x['id'],))]} for x in c.execute('SELECT * FROM reservations ORDER BY created DESC')]
   return self.send(200,data)
  p={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(self.path.split('?')[0])
  if not p:return self.send(404,{'error':'Not found'})
  b=(ROOT/'static'/p).read_bytes();self.send_response(200);self.send_header('Content-Type',{'html':'text/html','js':'text/javascript','css':'text/css'}[p.split('.')[-1]]);self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'");self.end_headers();self.wfile.write(b)
 def do_POST(self):
  try:
   if int(self.headers.get('Content-Length',0))>16384: return self.send(413,{'error':'Request too large'})
   d=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
   with connect() as c:
    c.execute('BEGIN IMMEDIATE');board=d.get('board',1)
    if type(board)!=int:raise ValueError('Invalid board')
    s=settings(c,board)
    if self.path=='/api/reserve':
     name=str(d.get('name','')).strip();dancer=str(d.get('dancer','')).strip();ns=d.get('squares',[])
     if not name or not dancer or len(name)>80 or len(dancer)>80 or not isinstance(ns,list) or not ns or len(ns)>100 or any(type(n)!=int or n<0 or n>99 for n in ns) or len(set(ns))!=len(ns):raise ValueError('Enter your name, supported dancer, and valid squares.')
     phone=str(d.get('phone','')).strip();email=str(d.get('email','')).strip()
     if phone and (len(phone)>40 or not re.fullmatch(r'[0-9+(). xX-]+',phone) or sum(ch.isdigit() for ch in phone)<7):raise ValueError('Enter a valid phone number or leave it blank.')
     if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):raise ValueError('Enter a valid email address or leave it blank.')
     if s['cancelled'] or not s['open'] or s['rows']:raise ValueError('Sales are closed.')
     rid=secrets.token_urlsafe(12);c.execute('INSERT INTO reservations(id,name,dancer,status,created,board,phone,email) VALUES(?,?,?,?,?,?,?,?)',(rid,name,dancer,'pending',int(time.time()),board,phone,email))
     try:c.executemany('INSERT INTO squares VALUES(?,?,?)',[(board,n,rid) for n in ns])
     except sqlite3.IntegrityError:raise ValueError('A selected square was just reserved. Refresh and choose again.')
     return self.send(200,{'message':'Squares reserved. Payment is pending organizer confirmation.','reference':rid,'board':board})
    if not self.admin():return self.send(401,{'error':'Organizer key required'})
    if self.path=='/api/reset-fundraiser':
     if d.get('confirmation')!='RESET ENTIRE FUNDRAISER':raise ValueError('Reset confirmation required.')
     # Capture a consistent database backup before changing any records.
     backup_dir=Path(DB).parent/'backups';backup_dir.mkdir(parents=True,exist_ok=True)
     backup_path=backup_dir/('before-fundraiser-reset-'+str(time.time_ns())+'.db')
     with connect() as source:
      with sqlite3.connect(backup_path) as backup:source.backup(backup)
     c.execute('DELETE FROM squares');c.execute('DELETE FROM reservations');c.execute('DELETE FROM boards')
     c.execute("DELETE FROM sqlite_sequence WHERE name='boards'")
     c.execute('INSERT INTO boards(id,data) VALUES(1,?)',(json.dumps(dict(open=True,rows=None,cols=None,cancelled=False)),))
     s.update(open=True,rows=None,cols=None,cancelled=False)
     c.execute('UPDATE settings SET data=? WHERE id=1',(json.dumps(s),))
     c.commit()
     return self.send(200,{'message':'Fundraiser reset. A backup was saved; Board 1 is empty and open for sales.','board':1})
    if self.path=='/api/boards':
     latest=c.execute('SELECT MAX(id) FROM boards').fetchone()[0]
     if not settings(c,latest)['cancelled'] and c.execute('SELECT COUNT(*) FROM squares WHERE board=?',(latest,)).fetchone()[0]!=100:raise ValueError('Sell out the latest board before adding another.')
     cur=c.execute('INSERT INTO boards(data) VALUES(?)',(json.dumps(dict(open=True,rows=None,cols=None)),))
     new_board=cur.lastrowid
     c.commit()
     return self.send(200,{'message':'Board '+str(new_board)+' created','board':new_board})
    if self.path=='/api/cancel-board':
     if s['cancelled']:raise ValueError('This board is already cancelled.')
     if s['rows']:raise ValueError('Cannot cancel a board after score digits are drawn.')
     if c.execute('SELECT COUNT(*) FROM squares WHERE board=?',(board,)).fetchone()[0]>=100:raise ValueError('Only an incomplete board can be cancelled.')
     s['cancelled']=True;s['open']=False
    elif self.path=='/api/refund':
     reservation=c.execute('SELECT * FROM reservations WHERE id=? AND board=?',(d.get('id'),board)).fetchone()
     if not s['cancelled'] or not reservation or reservation['status']!='paid':raise ValueError('Refund tracking is only available for paid reservations on a cancelled board.')
     if type(d.get('refunded'))!=bool:raise ValueError('Invalid refund state')
     c.execute('UPDATE reservations SET refunded=? WHERE id=?',(int(d['refunded']),reservation['id']))
    elif self.path=='/api/status':
     reservation=c.execute('SELECT * FROM reservations WHERE id=?',(d.get('id'),)).fetchone()
     if not reservation:raise ValueError('Reservation not found')
     s_for_reservation=settings(c,reservation['board'])
     if s_for_reservation['cancelled']:raise ValueError('Board cancelled. Use refund tracking; payment records are preserved.')
     if reservation['status']=='cancelled':raise ValueError('Cancelled reservations cannot be reactivated.')
     if d.get('status') not in ['paid','pending','cancelled']:raise ValueError('Invalid status')
     if s_for_reservation['rows'] and d['status']=='cancelled':raise ValueError('Cannot release squares after numbers are drawn.')
     c.execute('UPDATE reservations SET status=? WHERE id=?',(d['status'],d.get('id')))
     if d['status']=='cancelled':c.execute('DELETE FROM squares WHERE reservation=?',(d.get('id'),))
    elif self.path=='/api/settings':
     for k in ['organizer','contact','payment','rules','game','opponent','venmo','fundraiserHeading','homeTeam','boardMessage','homeColor','awayColor']:
      if k in d:s[k]=str(d[k]).strip()[:2000]
     for color in ['homeColor','awayColor']:
      if not re.fullmatch(r'#[0-9a-fA-F]{6}',s[color]):raise ValueError('Choose a valid team color.')
     if s.get('venmo') and not all(ch.isalnum() or ch in '-_' for ch in s['venmo']):raise ValueError('Enter only the Venmo username without @.')
     if 'price' in d:
      price=float(d['price'])
      if not 0<=price<=10000:raise ValueError('Invalid price')
      if c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0] and price!=s['price']:raise ValueError('Price is locked after the first reservation.')
      s['price']=price
     if 'open' in d:
      if type(d['open'])!=bool:raise ValueError('Invalid sales status')
      if s['cancelled'] and d['open']:raise ValueError('Cancelled boards cannot reopen.')
      if s['rows'] and d['open']:raise ValueError('Numbers already drawn; sales cannot reopen.')
      s['open']=d['open']
    elif self.path=='/api/draw':
     if s['cancelled']:raise ValueError('Cancelled boards cannot draw numbers.')
     if s['open']:raise ValueError('Close sales before drawing numbers.')
     if s['rows']:raise ValueError('Numbers have already been drawn and are locked.')
     if c.execute("SELECT COUNT(*) FROM reservations WHERE status='pending' AND board=?",(board,)).fetchone()[0]:raise ValueError('Resolve pending payments before drawing.')
     if not c.execute('SELECT COUNT(*) FROM squares WHERE board=?',(board,)).fetchone()[0]:raise ValueError('Reserve and confirm at least one square first.')
     s['rows']=list(range(10));s['cols']=list(range(10));secrets.SystemRandom().shuffle(s['rows']);secrets.SystemRandom().shuffle(s['cols'])
    else:return self.send(404,{'error':'Not found'})
    c.execute('UPDATE boards SET data=? WHERE id=?',(json.dumps({k:s[k] for k in ['open','rows','cols','cancelled']}),board))
    c.execute('UPDATE settings SET data=? WHERE id=1',(json.dumps(s),))
   self.send(200,{'message':'Saved'})
  except (ValueError,TypeError,KeyError) as e:self.send(400,{'error':str(e)})
  except Exception:self.send(500,{'error':'Unable to save. Please try again.'})
if __name__=='__main__':
 print('Local: http://127.0.0.1:'+os.environ.get('PORT','8000'),flush=True)
 ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),Handler).serve_forever()
