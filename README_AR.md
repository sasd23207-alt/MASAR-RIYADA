# نشر MASAR

## Railway
- اربط GitHub repository بالخدمة.
- استخدم Dockerfile الموجود في جذر المشروع.
- أضف Volume إلى `/data`.
- اضبط `MASAR_DB=/data/masar.sqlite3` و`MASAR_BACKUP_DIR=/data/backups`.
- ضع `MASAR_ADMIN_EMAIL` و`MASAR_ADMIN_PASSWORD` و`MASAR_ADMIN_NAME` كمتغيرات سرية.
- Healthcheck: `/api/health`.
- لا تضبط `PORT` يدويًا؛ Railway يحقنه وتقرأه `main.py`.

## محليًا
يمكن تشغيل المشروع بـ `python main.py`، وسيستمع افتراضيًا على `0.0.0.0:8787` ما لم تضبط `MASAR_HOST` و`MASAR_PORT`.
