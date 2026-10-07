import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os, tempfile, sqlite3, json, urllib.request, threading, time, shutil
from pathlib import Path
from masar_core.app import MasarApplication
from masar_core.infrastructure.db import Database
from masar_core.api.server import ApiServer

def req(base,path,method='GET',data=None,token=None):
    body=None if data is None else json.dumps(data,ensure_ascii=False).encode()
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    r=urllib.request.Request(base+path,data=body,method=method,headers=headers)
    with urllib.request.urlopen(r,timeout=5) as x:
        raw=x.read()
        return x.status,(json.loads(raw) if 'application/json' in x.headers.get('Content-Type','') else raw)

def run():
    td=tempfile.mkdtemp(); db=os.path.join(td,'masar.sqlite3'); bdir=os.path.join(td,'backups'); os.environ.update(MASAR_DB=db,MASAR_BACKUP_DIR=bdir,MASAR_ADMIN_EMAIL='admin@prod.test',MASAR_ADMIN_PASSWORD='ProductionPassword123!',MASAR_ADMIN_NAME='مدير الإنتاج')
    app=MasarApplication(Database(db)); s=ApiServer(app,'127.0.0.1',18801).start(); threading.Thread(target=s.serve_forever,daemon=True).start(); time.sleep(.2); base='http://127.0.0.1:18801'
    assert req(base,'/')[0]==200
    code,login=req(base,'/api/auth/login','POST',{'email':'admin@prod.test','password':'ProductionPassword123!'}); assert code==200; token=login['token']
    code,stu=req(base,'/api/students','POST',{'name':'طالب اختبار إنتاج','grade':'السادس','section':'أ'},token); assert code==201
    sid=stu['id']
    assert req(base,'/api/reports/students',token=token)[1][0]['name']=='طالب اختبار إنتاج'
    code,b=req(base,'/api/backups','POST',{},token); assert code==201 and b['integrity']=='ok'
    assert sqlite3.connect(b['file']).execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    s.shutdown(); s.server_close(); time.sleep(.1)
    # Delete current DB, restore exact backup, reopen and prove record survived.
    os.remove(db); app2=MasarApplication(Database(db)); restored=app2.backups.restore(b['file']); assert restored['integrity']=='ok'
    c=app2.db.connect(); row=c.execute('SELECT name FROM students WHERE id=?',(sid,)).fetchone(); c.close(); assert row and row['name']=='طالب اختبار إنتاج'
    print('VERIFIED: production UI serving, authenticated API, direct reports, atomic backup creation, backup integrity, restore and data recovery')
    print('RESTORED_STUDENT=',sid)
    shutil.rmtree(td,ignore_errors=True)
if __name__=='__main__': run()
