import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os,tempfile,shutil,sqlite3
from masar_core.app import MasarApplication
from masar_core.infrastructure.db import Database

def run():
 td=tempfile.mkdtemp(); app=MasarApplication(Database(os.path.join(td,'db.sqlite3')))
 cl=app.academic.create_class({'name':'A','grade':'السادس','section':'أ'}); s=app.students.create({'name':'x','guardian_phone':'1','class_id':cl['id']})
 app.attendance.mark({'student_id':s['id'],'class_id':cl['id'],'date':'2026-10-07','status':'absent'}); app.attendance.mark({'student_id':s['id'],'class_id':cl['id'],'date':'2026-10-07','status':'absent'})
 c=app.db.connect(); assert c.execute("SELECT count(*) n FROM notification_outbox WHERE event_type='ATTENDANCE_ABSENT'").fetchone()['n']==1; c.close()
 app.attendance.mark({'student_id':s['id'],'class_id':cl['id'],'date':'2026-10-07','status':'present'}); c=app.db.connect(); assert c.execute("SELECT status FROM notification_outbox WHERE event_type='ATTENDANCE_ABSENT'").fetchone()['status']=='cancelled'; c.close()
 app.students.archive(s['id'])
 for fn,args in [(app.academic.add_grade,{'student_id':s['id'],'subject':'x','value':50}),(app.attendance.mark,{'student_id':s['id'],'class_id':cl['id'],'date':'2026-10-08','status':'absent'})]:
  try: fn(args)
  except ValueError: pass
  else: raise AssertionError
 print('VERIFIED: hardening regression suite')
 shutil.rmtree(td,ignore_errors=True)
if __name__=='__main__': run()
