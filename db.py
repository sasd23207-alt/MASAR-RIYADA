import json, os, sqlite3, uuid
from contextlib import contextmanager
from datetime import datetime

def _default_db_path():
    env = os.environ.get('MASAR_DB')
    if env:
        return env
    if os.name == 'nt':
        root = os.environ.get('PROGRAMDATA') or os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        return os.path.join(root, 'MASAR', 'data', 'masar.sqlite3')
    return os.path.join(os.path.dirname(__file__), '..', '..', 'masar.sqlite3')

DB_PATH = _default_db_path()

def now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

def uid(prefix):
    return prefix + '_' + uuid.uuid4().hex[:16]

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, last_login_at TEXT);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, last_seen_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash,expires_at);

CREATE TABLE IF NOT EXISTS students(id TEXT PRIMARY KEY, name TEXT NOT NULL, age INTEGER, phone TEXT, guardian_phone TEXT, address TEXT, grade TEXT, section TEXT, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, archived_at TEXT);
CREATE INDEX IF NOT EXISTS idx_students_name ON students(name);
CREATE INDEX IF NOT EXISTS idx_students_grade ON students(grade,section);
CREATE TABLE IF NOT EXISTS classes(id TEXT PRIMARY KEY, name TEXT NOT NULL, grade TEXT NOT NULL, section TEXT NOT NULL, room TEXT, teacher_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS teachers(id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT, specialty TEXT, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_teachers_name ON teachers(name);
CREATE TABLE IF NOT EXISTS subjects(id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, max_grade REAL NOT NULL DEFAULT 100, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY, class_id TEXT NOT NULL REFERENCES classes(id), teacher_id TEXT REFERENCES teachers(id), subject_id TEXT REFERENCES subjects(id), day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6), start_time TEXT NOT NULL, end_time TEXT NOT NULL, room TEXT, notes TEXT, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_schedule_class_day ON schedules(class_id,day_of_week,start_time);
CREATE INDEX IF NOT EXISTS idx_schedule_teacher_day ON schedules(teacher_id,day_of_week,start_time);
CREATE TABLE IF NOT EXISTS class_enrollments(id TEXT PRIMARY KEY, class_id TEXT NOT NULL REFERENCES classes(id), student_id TEXT NOT NULL REFERENCES students(id), start_date TEXT NOT NULL, end_date TEXT, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, UNIQUE(class_id,student_id,start_date));
CREATE INDEX IF NOT EXISTS idx_enroll_student ON class_enrollments(student_id,status);
CREATE INDEX IF NOT EXISTS idx_enroll_class ON class_enrollments(class_id,status);
CREATE TABLE IF NOT EXISTS attendance(id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), class_id TEXT REFERENCES classes(id), attendance_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('present','absent','late','excused')), note TEXT, created_at TEXT NOT NULL, UNIQUE(student_id,attendance_date));
CREATE INDEX IF NOT EXISTS idx_attendance_student_date ON attendance(student_id,attendance_date);
CREATE TABLE IF NOT EXISTS installments(id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), amount REAL NOT NULL, paid_amount REAL NOT NULL DEFAULT 0, due_date TEXT NOT NULL, sequence_no INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', period_days INTEGER NOT NULL DEFAULT 30, created_at TEXT NOT NULL, paid_at TEXT);
CREATE INDEX IF NOT EXISTS idx_installments_student ON installments(student_id,sequence_no);
CREATE INDEX IF NOT EXISTS idx_installments_due ON installments(due_date,status);
CREATE TABLE IF NOT EXISTS payments(id TEXT PRIMARY KEY, installment_id TEXT NOT NULL REFERENCES installments(id), student_id TEXT NOT NULL REFERENCES students(id), amount REAL NOT NULL, paid_at TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS grades(id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), subject TEXT NOT NULL, value REAL NOT NULL, note TEXT, grade_date TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_grades_student ON grades(student_id,grade_date);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, event_type TEXT NOT NULL, aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_events_aggregate ON events(aggregate_type,aggregate_id,created_at);
CREATE TABLE IF NOT EXISTS notification_outbox(id TEXT PRIMARY KEY, event_type TEXT NOT NULL, aggregate_id TEXT, recipient_phone TEXT, channel TEXT NOT NULL DEFAULT 'whatsapp', message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT NOT NULL, last_error TEXT, created_at TEXT NOT NULL, sent_at TEXT);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON notification_outbox(status,next_attempt_at);
CREATE TABLE IF NOT EXISTS audit_log(id TEXT PRIMARY KEY, action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT, details TEXT NOT NULL, created_at TEXT NOT NULL);
'''

class Database:
    def __init__(self, path=None): self.path = path or DB_PATH
    def connect(self):
        c=sqlite3.connect(self.path,timeout=30,isolation_level=None)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA synchronous=FULL')
        return c
    def init(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        c=self.connect(); c.executescript(SCHEMA); c.close()
    @contextmanager
    def tx(self):
        c=self.connect(); c.execute('BEGIN IMMEDIATE')
        try:
            yield c; c.execute('COMMIT')
        except Exception:
            c.execute('ROLLBACK'); raise
        finally: c.close()

def rowdict(row): return dict(row) if row else None
