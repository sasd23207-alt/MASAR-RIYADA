import os, tempfile
from pathlib import Path
from masar_core.infrastructure.db import Database
from masar_core.services.academic_service import AcademicService
from masar_core.services.backup_service import BackupService

with tempfile.TemporaryDirectory() as td:
    db=Database(str(Path(td)/'masar.sqlite3')); db.init(); a=AcademicService(db)
    t=a.create_teacher({'name':'أحمد اختبار','phone':'218900000001','specialty':'رياضيات'})
    sub=a.create_subject({'name':'رياضيات','max_grade':100})
    c=a.create_class({'name':'السابع أ','grade':'السابع','section':'أ','room':'101','teacher_id':t['id']})
    sch=a.create_schedule({'class_id':c['id'],'teacher_id':t['id'],'subject_id':sub['id'],'day_of_week':0,'start_time':'08:00','end_time':'09:00','room':'101'})
    try:
        a.create_schedule({'class_id':c['id'],'teacher_id':t['id'],'subject_id':sub['id'],'day_of_week':0,'start_time':'08:30','end_time':'09:30','room':'101'})
        raise AssertionError('conflict was not rejected')
    except ValueError as e:
        assert 'conflict' in str(e)
    assert a.schedules()[0]['id']==sch['id']
    b=BackupService(db, Path(td)/'backups'); backup=b.create(); assert backup['integrity']=='ok'; assert Path(backup['file']).exists()
    print('VERIFIED: teachers, subjects, persistent schedule, conflict prevention, backup integrity')
    print('TEACHER=', t['name'])
    print('SCHEDULE=', sch['start_time'], sch['end_time'])
    print('BACKUP=', Path(backup['file']).name)
