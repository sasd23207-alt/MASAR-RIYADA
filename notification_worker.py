import os,time
from datetime import datetime,timedelta
class Provider:
    def send(self,row):
        if not os.environ.get('MASAR_WHATSAPP_URL') or not os.environ.get('MASAR_WHATSAPP_TOKEN'): raise RuntimeError('WhatsApp provider credentials are not configured')
        raise RuntimeError('WhatsApp provider adapter requires provider-specific payload configuration')
class NotificationWorker:
    def __init__(self,db,finance): self.db=db; self.finance=finance; self.provider=Provider(); self.stop=False
    def tick(self):
        self.finance.scan_overdue()
        c=self.db.connect(); row=c.execute("SELECT * FROM notification_outbox WHERE status='pending' AND next_attempt_at<=? ORDER BY created_at LIMIT 1",(self._now(),)).fetchone(); c.close()
        if not row: return False
        row=dict(row)
        # Revalidate business state before sending: cancelled/paid items must never escape the queue.
        if row['event_type']=='INSTALLMENT_OVERDUE':
            c=self.db.connect(); live=c.execute('SELECT status,paid_amount,amount FROM installments WHERE id=?',(row['aggregate_id'],)).fetchone(); c.close()
            if not live or live['status']=='paid' or live['paid_amount']>=live['amount']:
                c=self.db.connect(); c.execute("UPDATE notification_outbox SET status='cancelled',last_error='Business state no longer requires notification' WHERE id=?",(row['id'],)); c.close(); return True
        try:
            self.provider.send(row)
            c=self.db.connect(); c.execute("UPDATE notification_outbox SET status='sent',sent_at=?,attempts=attempts+1 WHERE id=?",(self._now(),row['id'])); c.close()
        except Exception as e:
            delay=min(3600,2**min(int(row['attempts']),8)); nxt=(datetime.utcnow()+timedelta(seconds=delay)).replace(microsecond=0).isoformat()+'Z'; c=self.db.connect(); c.execute('UPDATE notification_outbox SET attempts=attempts+1,last_error=?,next_attempt_at=? WHERE id=?',(str(e),nxt,row['id'])); c.close()
        return True
    def _now(self): return datetime.utcnow().replace(microsecond=0).isoformat()+'Z'
