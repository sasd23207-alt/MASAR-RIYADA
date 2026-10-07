import os, sqlite3, shutil
from datetime import datetime
from pathlib import Path
from ..infrastructure.db import now

class BackupService:
    def __init__(self, db, directory=None):
        self.db=db; self.directory=Path(directory or os.environ.get('MASAR_BACKUP_DIR', Path(db.path).parent/'backups')); self.directory.mkdir(parents=True,exist_ok=True)
    def create(self):
        stamp=datetime.utcnow().strftime('%Y%m%d_%H%M%S'); target=self.directory/f'masar_{stamp}.sqlite3'
        src=sqlite3.connect(self.db.path); dst=sqlite3.connect(str(target))
        try: src.backup(dst)
        finally: dst.close(); src.close()
        # Validate backup before reporting success.
        c=sqlite3.connect(str(target)); ok=c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; c.close()
        if not ok: target.unlink(missing_ok=True); raise RuntimeError('backup integrity check failed')
        return {'file':str(target),'size':target.stat().st_size,'created_at':now(),'integrity':'ok'}
    def list(self):
        return [{'file':str(p),'name':p.name,'size':p.stat().st_size} for p in sorted(self.directory.glob('masar_*.sqlite3'),reverse=True)]
    def restore(self, path):
        p=Path(path).resolve(); root=self.directory.resolve()
        if root not in p.parents: raise ValueError('backup path outside backup directory')
        if not p.exists(): raise FileNotFoundError('backup not found')
        c=sqlite3.connect(str(p)); ok=c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; c.close()
        if not ok: raise ValueError('backup integrity check failed')
        # Replace via SQLite backup into a temp database to avoid partial target files.
        tmp=self.db.path+'.restore.tmp'; s=sqlite3.connect(str(p)); d=sqlite3.connect(tmp)
        try: s.backup(d)
        finally: d.close(); s.close()
        os.replace(tmp,self.db.path)
        return {'restored':str(p),'integrity':'ok'}
