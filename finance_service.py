from datetime import date,timedelta
from ..infrastructure.db import uid, now, rowdict
from ..domain.events import audit, record_event

class FinanceService:
    def __init__(self,db): self.db=db
    def create_installment(self,data):
        sid=data['student_id']; amount=float(data['amount']); due=data['due_date']; period=int(data.get('period_days',30)); seq=int(data.get('sequence_no') or 1)
        if amount<=0 or period<=0: raise ValueError('invalid installment')
        with self.db.tx() as c:
            s=c.execute('SELECT * FROM students WHERE id=?',(sid,)).fetchone()
            if not s: raise KeyError('student not found')
            iid=uid('INS'); c.execute('INSERT INTO installments VALUES (?,?,?,?,?,?,?,?,?,?)',(iid,sid,amount,0,due,seq,'pending',period,now(),None)); audit(c,'create','installment',iid,data); record_event(c,'INSTALLMENT_CREATED','installment',iid,{'student_id':sid,'amount':amount,'due_date':due}); return rowdict(c.execute('SELECT * FROM installments WHERE id=?',(iid,)).fetchone())
    def pay(self,iid,amount,note=None):
        amount=float(amount)
        with self.db.tx() as c:
            r=c.execute('SELECT * FROM installments WHERE id=?',(iid,)).fetchone()
            if not r: raise KeyError('installment not found')
            remaining=max(0,float(r['amount'])-float(r['paid_amount']))
            if amount<=0 or amount>remaining: raise ValueError('invalid payment amount')
            pid=uid('PAY'); t=now(); newpaid=float(r['paid_amount'])+amount; paid=newpaid>=float(r['amount'])
            c.execute('INSERT INTO payments VALUES (?,?,?,?,?,?)',(pid,iid,r['student_id'],amount,t,note)); c.execute('UPDATE installments SET paid_amount=?,status=?,paid_at=? WHERE id=?',(newpaid,'paid' if paid else 'partial',t if paid else None,iid))
            audit(c,'payment','installment',iid,{'payment_id':pid,'amount':amount}); record_event(c,'PAYMENT_RECORDED','installment',iid,{'student_id':r['student_id'],'amount':amount,'paid':paid})
            if paid:
                # Any overdue alert for this installment becomes irrelevant immediately.
                c.execute("UPDATE notification_outbox SET status='cancelled',last_error='Installment paid before send' WHERE event_type='INSTALLMENT_OVERDUE' AND aggregate_id=? AND status='pending'",(iid,))
                next_id=uid('INS'); due=(date.fromisoformat(r['due_date'])+timedelta(days=int(r['period_days']))).isoformat()
                c.execute('INSERT INTO installments VALUES (?,?,?,?,?,?,?,?,?,?)',(next_id,r['student_id'],r['amount'],0,due,int(r['sequence_no'])+1,'pending',r['period_days'],t,None)); record_event(c,'INSTALLMENT_GENERATED','installment',next_id,{'student_id':r['student_id'],'previous_installment_id':iid,'amount':r['amount'],'due_date':due})
                s=c.execute('SELECT * FROM students WHERE id=?',(r['student_id'],)).fetchone()
                if s['guardian_phone']: c.execute('INSERT INTO notification_outbox(id,event_type,aggregate_id,recipient_phone,channel,message,next_attempt_at,created_at) VALUES (?,?,?,?,?,?,?,?)',(uid('NTF'),'NEXT_INSTALLMENT_CREATED',next_id,s['guardian_phone'],'whatsapp',f'تم سداد القسط للطالب {s["name"]}. القسط القادم {r["amount"]} وموعده {due}.',now(),now()))
                nxt=rowdict(c.execute('SELECT * FROM installments WHERE id=?',(next_id,)).fetchone())
            else: nxt=None
            return {'payment_id':pid,'installment':rowdict(c.execute('SELECT * FROM installments WHERE id=?',(iid,)).fetchone()),'next_installment':nxt}
    def scan_overdue(self):
        with self.db.tx() as c:
            rows=c.execute('SELECT i.*,s.name,s.guardian_phone FROM installments i JOIN students s ON s.id=i.student_id WHERE i.status IN ("pending","partial") AND i.due_date < ? AND i.paid_amount < i.amount',(now()[:10],)).fetchall(); n=0
            for r in rows:
                if not r['guardian_phone']: continue
                exists=c.execute("SELECT 1 FROM notification_outbox WHERE event_type='INSTALLMENT_OVERDUE' AND aggregate_id=? AND status IN ('pending','sent')",(r['id'],)).fetchone()
                if not exists:
                    c.execute('INSERT INTO notification_outbox(id,event_type,aggregate_id,recipient_phone,channel,message,next_attempt_at,created_at) VALUES (?,?,?,?,?,?,?,?)',(uid('NTF'),'INSTALLMENT_OVERDUE',r['id'],r['guardian_phone'],'whatsapp',f'تنبيه تأخر سداد: الطالب {r["name"]}. القسط {r["id"]} متأخر منذ {r["due_date"]}.',now(),now())); n+=1
            return n
