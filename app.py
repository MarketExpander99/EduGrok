App init failed: [Errno 13] Permission denied: '/home/Edugrok'
Traceback (most recent call last):
  File "/workspaces/EduGrok/app.py", line 81, in <module>
    init_app()
  File "/workspaces/EduGrok/app.py", line 70, in init_app
    init_db()
  File "/workspaces/EduGrok/db.py", line 125, in init_db
    conn = get_db()
           ^^^^^^^^
  File "/workspaces/EduGrok/db.py", line 27, in get_db
    os.makedirs(db_dir)
  File "<frozen os>", line 215, in makedirs
  File "<frozen os>", line 225, in makedirs
PermissionError: [Errno 13] Permission denied: '/home/Edugrok'