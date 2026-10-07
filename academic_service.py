from ..infrastructure.db import uid,now,rowdict
from ..domain.events import audit,record_event

class AcademicService:
    def __init__(self,db): self.db=db
    def create_class(self,data):
        if not data.get('grade') or not data.get('section'): raise ValueError('grade and section are required')
        cid=uid('CLS')
        with self.db.tx() as c:
            c.execute('INSERT INTO classes VALUES (?,?,?,?,?,?,?)',(cid,data.get('name') or data['grade'],data['grade'],data['section'],data.get('room'),data.get('teacher_id'),now())); audit(c,'create','class',cid,data); record_event(c,'CLASS_CREATED','class',cid,{'class_id':cid}); return rowdict(c.execute('SELECT * FROM classes WHERE id=?',(cid,)).fetchone())

    def teachers(self, active_only=False):
        c=self.db.connect(); sql='SELECT * FROM teachers'
        if active_only: sql+=' WHERE status="active"'
        rows=[rowdict(r) for r in c.execute(sql+' ORDER BY name').fetchall()]; c.close(); return rows

    def create_teacher(self,data):
        name=(data.get('name') or '').strip()
        if not name: raise ValueError('teacher name is required')
        tid=uid('TCH')
        with self.db.tx() as c:
            c.execute('INSERT INTO teachers VALUES (?,?,?,?,?,?,?)',(tid,name,data.get('phone'),data.get('email'),data.get('specialty'),'active',now()))
            audit(c,'create','teacher',tid,data); record_event(c,'TEACHER_CREATED','teacher',tid,{'teacher_id':tid})
            return rowdict(c.execute('SELECT * FROM teachers WHERE id=?',(tid,)).fetchone())

    def subjects(self, active_only=False):
        c=self.db.connect(); sql='SELECT * FROM subjects'
        if active_only: sql+=' WHERE status="active"'
        rows=[rowdict(r) for r in c.execute(sql+' ORDER BY name').fetchall()]; c.close(); return rows

    def create_subject(self,data):
        name=(data.get('name') or '').strip()
        if not name: raise ValueError('subject name is required')
        sid=uid('SUB')
        with self.db.tx() as c:
            c.execute('INSERT INTO subjects VALUES (?,?,?,?,?)',(sid,name,float(data.get('max_grade') or 100),'active',now()))
            audit(c,'create','subject',sid,data); record_event(c,'SUBJECT_CREATED','subject',sid,{'subject_id':sid})
            return rowdict(c.execute('SELECT * FROM subjects WHERE id=?',(sid,)).fetchone())

    def schedules(self, class_id=None, teacher_id=None, day=None):
        c=self.db.connect(); sql='SELECT s.*,c.name class_name,c.grade,c.section,t.name teacher_name,sub.name subject_name FROM schedules s JOIN classes c ON c.id=s.class_id LEFT JOIN teachers t ON t.id=s.teacher_id LEFT JOIN subjects sub ON sub.id=s.subject_id WHERE 1=1'; args=[]
        if class_id: sql+=' AND s.class_id=?'; args.append(class_id)
        if teacher_id: sql+=' AND s.teacher_id=?'; args.append(teacher_id)
        if day is not None: sql+=' AND s.day_of_week=?'; args.append(int(day))
        rows=[rowdict(r) for r in c.execute(sql+' ORDER BY s.day_of_week,s.start_time',args).fetchall()]; c.close(); return rows

    def create_schedule(self,data):
        class_id=data.get('class_id')
        if not class_id: raise ValueError('class_id is required')
        day=int(data.get('day_of_week'))
        if day<0 or day>6: raise ValueError('day_of_week must be 0..6')
        start=(data.get('start_time') or '').strip(); end=(data.get('end_time') or '').strip()
        if not start or not end or start>=end: raise ValueError('invalid schedule time')
        sid=uid('SCH')
        with self.db.tx() as c:
            if not c.execute('SELECT 1 FROM classes WHERE id=?',(class_id,)).fetchone(): raise KeyError('class not found')
            if data.get('teacher_id') and not c.execute('SELECT 1 FROM teachers WHERE id=?',(data['teacher_id'],)).fetchone(): raise KeyError('teacher not found')
            if data.get('subject_id') and not c.execute('SELECT 1 FROM subjects WHERE id=?',(data['subject_id'],)).fetchone(): raise KeyError('subject not found')
            conflict=c.execute('SELECT 1 FROM schedules WHERE status="active" AND day_of_week=? AND start_time<? AND end_time>? AND ((teacher_id IS NOT NULL AND teacher_id=?) OR class_id=?) LIMIT 1',(day,end,start,data.get('teacher_id'),class_id)).fetchone()
            if conflict: raise ValueError('schedule conflict')
            c.execute('INSERT INTO schedules VALUES (?,?,?,?,?,?,?,?,?,?,?)',(sid,class_id,data.get('teacher_id'),data.get('subject_id'),day,start,end,data.get('room'),data.get('notes'),'active',now()))
            audit(c,'create','schedule',sid,data); record_event(c,'SCHEDULE_CREATED','schedule',sid,{'schedule_id':sid})
            return rowdict(c.execute('SELECT * FROM schedules WHERE id=?',(sid,)).fetchone())

    def enrollments(self,class_id=None,student_id=None):
        c=self.db.connect(); sql='SELECT e.*,c.name class_name,c.grade,c.section,s.name student_name FROM class_enrollments e JOIN classes c ON c.id=e.class_id JOIN students s ON s.id=e.student_id WHERE 1=1'; args=[]
        if class_id: sql+=' AND e.class_id=?'; args.append(class_id)
        if student_id: sql+=' AND e.student_id=?'; args.append(student_id)
        rows=[rowdict(r) for r in c.execute(sql,args).fetchall()]; c.close(); return rows
    def add_grade(self,data):
        sid=data['student_id']; gid=uid('GRD')
        with self.db.tx() as c:
            student=c.execute('SELECT * FROM students WHERE id=?',(sid,)).fetchone()
            if not student: raise KeyError('student not found')
            if student['status'] != 'active': raise ValueError('student is archived')
            value=float(data['value'])
            if not 0 <= value <= 100: raise ValueError('grade value must be between 0 and 100')
            c.execute('INSERT INTO grades VALUES (?,?,?,?,?,?,?)',(gid,sid,data['subject'],value,data.get('note'),data.get('date') or now()[:10],now())); audit(c,'create','grade',gid,data); record_event(c,'GRADE_RECORDED','student',sid,{'student_id':sid,'grade_id':gid}); return rowdict(c.execute('SELECT * FROM grades WHERE id=?',(gid,)).fetchone())
