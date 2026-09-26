from flask import Flask,request,jsonify,send_from_directory,send_file
import sqlite3,os,sys,secrets,hashlib,json,shutil,socket
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side

BUNDLE=getattr(sys,"_MEIPASS",os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNTIME=os.path.dirname(sys.executable) if getattr(sys,"frozen",False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT=os.environ.get("FAYOUM_SCAN_DATA_DIR",RUNTIME)
DB=os.path.join(DATA_ROOT,"data","fayoum_scan.db"); BACKUPS=os.path.join(DATA_ROOT,"backups")
SCHEMA=os.path.join(BUNDLE,"server","schema.sql"); WEB=os.path.join(BUNDLE,"web")
app=Flask(__name__,static_folder=WEB); TOKENS={}

def con():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
def hp(p,s=None):
 s=s or secrets.token_hex(16); return s+"$"+hashlib.pbkdf2_hmac("sha256",p.encode(),s.encode(),200000).hex()
def vp(p,h):
 try:s,x=h.split("$",1);return secrets.compare_digest(hp(p,s).split("$",1)[1],x)
 except:return False
def user():
 return TOKENS.get(request.headers.get("Authorization","").replace("Bearer ",""))
def admin(): return user() if user() and user()["role"]=="admin" else None
def allowed(permission):
 u=user()
 if not u:return False
 if u["role"]=="admin":return True
 with con() as c:return bool(c.execute("select 1 from role_permissions where role=? and permission=? and allowed=1",(u["role"],permission)).fetchone())
@app.before_request
def protect_api():
 if not request.path.startswith("/api/"):return None
 if request.path in ("/api/health","/api/login"):return None
 if not user():return jsonify(error="authentication required"),401

def init():
 os.makedirs(os.path.dirname(DB),exist_ok=True);os.makedirs(BACKUPS,exist_ok=True)
 with con() as c:
  c.executescript(open(SCHEMA,encoding="utf-8").read())
  cols={x["name"] for x in c.execute("pragma table_info(patients)")}
  for name,sqltype,default in [("paid_amount","REAL","0"),("remaining_amount","REAL","0"),("payment_method","TEXT","\'Cash\'")]:
   if name not in cols:c.execute(f"alter table patients add column {name} {sqltype} default {default}")
  for p in ["patient_edit","booking_manage","export","view_financial"]:
   c.execute("insert or ignore into role_permissions(role,permission,allowed) values(?,?,1)",("user",p))
  if not c.execute("select count(*) from users").fetchone()[0]:
   c.execute("insert into users(username,password_hash,role) values(?,?,?)",("admin",hp("admin123"),"admin"))

def lan_ip():
 try:
  sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.connect(("8.8.8.8",80));ip=sock.getsockname()[0];sock.close();return ip
 except:
  try:return socket.gethostbyname(socket.gethostname())
  except:return "127.0.0.1"
@app.get("/api/health")
def health():
 port=int(os.getenv("PORT","8787"));ip=lan_ip()
 with con() as c:return jsonify(ok=True,server="FAYOUM SCAN RIS",version="Beta 0.5",patients=c.execute("select count(*) from patients").fetchone()[0],lan_ip=ip,lan_url=f"http://{ip}:{port}",local_url=f"http://127.0.0.1:{port}")
@app.post("/api/login")
def login():
 d=request.json or {}
 with con() as c:
  r=c.execute("select * from users where username=? and active=1",(d.get("username"),)).fetchone()
  if not r or not vp(d.get("password",""),r["password_hash"]):return jsonify(error="invalid credentials"),401
  t=secrets.token_urlsafe(32);TOKENS[t]={"id":r["id"],"username":r["username"],"role":r["role"]}
  c.execute("update users set last_login=CURRENT_TIMESTAMP where id=?",(r["id"],));return jsonify(token=t,user=TOKENS[t])
@app.post("/api/logout")
def logout(): TOKENS.pop(request.headers.get("Authorization","").replace("Bearer ",""),None);return jsonify(ok=True)
@app.get("/api/users")
def users():
 if not admin():return jsonify(error="admin required"),403
 with con() as c:return jsonify([dict(x) for x in c.execute("select id,username,role,active,last_login,created_at from users order by username")])
@app.post("/api/users")
def adduser():
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 with con() as c:
  try:r=c.execute("insert into users(username,password_hash,role) values(?,?,?)",(d["username"],hp(d["password"]),d.get("role","user")));return jsonify(id=r.lastrowid),201
  except sqlite3.IntegrityError:return jsonify(error="username exists"),409
@app.get("/api/payment-types")
def pays():
 with con() as c:return jsonify([dict(x) for x in c.execute("select * from payment_types where active=1 order by name")])
@app.get("/api/exams")
def exams():
 u=request.args.get("unit");q="select * from exams where active=1";a=[]
 if u:q+=" and unit=?";a=[u]
 with con() as c:return jsonify([dict(x) for x in c.execute(q+" order by unit,name",a)])
@app.post("/api/payment-types")
def addpay():
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 try:
  with con() as c:r=c.execute("insert into payment_types(name,category,notes) values(?,?,?)",(d["name"],d.get("category"),d.get("notes")));return jsonify(id=r.lastrowid),201
 except sqlite3.IntegrityError:return jsonify(error="payment type exists"),409
@app.post("/api/exams")
def addexam():
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 try:
  with con() as c:r=c.execute("insert into exams(unit,name,base_price) values(?,?,?)",(d["unit"],d["name"],float(d.get("base_price",0))));return jsonify(id=r.lastrowid),201
 except sqlite3.IntegrityError:return jsonify(error="exam exists"),409
@app.put("/api/payment-types/<int:i>")
def editpay(i):
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 with con() as c:
  old=c.execute("select * from payment_types where id=?",(i,)).fetchone()
  if not old:return jsonify(error="payment type not found"),404
  try:c.execute("update payment_types set name=?,category=?,notes=?,active=? where id=?",(d.get("name",old["name"]),d.get("category",old["category"]),d.get("notes",old["notes"]),int(d.get("active",old["active"])),i))
  except sqlite3.IntegrityError:return jsonify(error="payment type exists"),409
 return jsonify(ok=True)
@app.put("/api/exams/<int:i>")
def editexam(i):
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 with con() as c:
  old=c.execute("select * from exams where id=?",(i,)).fetchone()
  if not old:return jsonify(error="exam not found"),404
  try:c.execute("update exams set unit=?,name=?,base_price=?,active=? where id=?",(d.get("unit",old["unit"]),d.get("name",old["name"]),float(d.get("base_price",old["base_price"] or 0)),int(d.get("active",old["active"])),i))
  except sqlite3.IntegrityError:return jsonify(error="exam exists"),409
 return jsonify(ok=True)
@app.get("/api/price-plans")
def plans():
 with con() as c:return jsonify([dict(x) for x in c.execute("select p.*,t.name payment_type from price_plans p join payment_types t on t.id=p.payment_type_id order by p.id desc")])
@app.post("/api/price-plans")
def addplan():
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 with con() as c:r=c.execute("insert into price_plans(payment_type_id,name,version,valid_from,valid_to,active) values(?,?,?,?,?,?)",(d["payment_type_id"],d["name"],int(d.get("version",1)),d["valid_from"],d.get("valid_to"),int(d.get("active",1))));return jsonify(id=r.lastrowid),201
@app.put("/api/price-plans/<int:pid>")
def editplan(pid):
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 with con() as c:
  old=c.execute("select * from price_plans where id=?",(pid,)).fetchone()
  if not old:return jsonify(error="price plan not found"),404
  c.execute("update price_plans set payment_type_id=?,name=?,version=?,valid_from=?,valid_to=?,active=? where id=?",(int(d.get("payment_type_id",old["payment_type_id"])),d.get("name",old["name"]),int(d.get("version",old["version"])),d.get("valid_from",old["valid_from"]),d.get("valid_to",old["valid_to"]),int(d.get("active",old["active"])),pid))
 return jsonify(ok=True)
@app.get("/api/price-plans/<int:pid>/items")
def planitems(pid):
 with con() as c:
  if not c.execute("select 1 from price_plans where id=?",(pid,)).fetchone():return jsonify(error="price plan not found"),404
  return jsonify([dict(x) for x in c.execute("select i.*,e.unit,e.name exam_name from price_plan_items i join exams e on e.id=i.exam_id where i.price_plan_id=? order by e.unit,e.name",(pid,))])
@app.post("/api/price-plans/<int:pid>/items")
def planitem(pid):
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 with con() as c:c.execute("insert into price_plan_items(price_plan_id,exam_id,price,coverage_percentage,active) values(?,?,?,?,1) on conflict(price_plan_id,exam_id) do update set price=excluded.price,coverage_percentage=excluded.coverage_percentage,active=1",(pid,d["exam_id"],float(d["price"]),float(d.get("coverage_percentage",0))))
 return jsonify(ok=True)
@app.get("/api/pricing/resolve")
def resolve():
 pt=request.args.get("payment_type","");ex=request.args.get("exam","");day=request.args.get("date") or datetime.now().date().isoformat()
 with con() as c:
  r=c.execute("select i.id item_id,p.id plan_id,p.name plan_name,p.version,i.price,i.coverage_percentage from price_plan_items i join price_plans p on p.id=i.price_plan_id join payment_types t on t.id=p.payment_type_id join exams e on e.id=i.exam_id where t.name=? and e.name=? and p.active=1 and i.active=1 and p.valid_from<=? and (p.valid_to is null or p.valid_to='' or p.valid_to>=?) order by p.version desc,p.id desc limit 1",(pt,ex,day,day)).fetchone()
  if r:return jsonify(found=True,**dict(r))
  e=c.execute("select base_price from exams where name=? and active=1 order by id desc limit 1",(ex,)).fetchone()
  return jsonify(found=False,price=(e["base_price"] if e else 0),coverage_percentage=0)
@app.get("/api/patients")
def patients():
 q="select * from patients where 1=1";a=[]
 for col,arg in [("case_date","date"),("unit","unit")]:
  v=request.args.get(arg)
  if v and v!="all":q+=f" and {col}=?";a.append(v)
 s=request.args.get("search","")
 if s:q+=" and (name like ? or phone like ? or exam like ? or doctor like ?)";a += [f"%{s}%"]*4
 with con() as c:return jsonify([dict(x) for x in c.execute(q+" order by id desc limit 3000",a)])
@app.post("/api/patients")
def patientadd():
 d=request.json or {}; cols=["name","payment_type","phone","exam","exam_price","coverage_percentage","coverage_amount","additional_fees","discount","total_amount","paid_amount","remaining_amount","payment_method","doctor","notes","username","unit","case_date","timestamp","price_plan_id","price_plan_item_id","price_snapshot"]
 with con() as c:
  r=c.execute(f"insert into patients({','.join(cols)}) values({','.join(['?']*len(cols))})",[d.get(k) for k in cols])
  c.execute("insert into audit_log(username,action,entity_type,entity_id,new_data) values(?,?,?,?,?)",(d.get("username"),"CREATE","patient",r.lastrowid,json.dumps(d,ensure_ascii=False)));return jsonify(id=r.lastrowid),201
@app.put("/api/patients/<int:i>")
def patientedit(i):
 if not allowed("patient_edit"):return jsonify(error="permission denied"),403
 d=request.json or {};expected=int(d.get("row_version",1));u=user();editable_fields=["name","payment_type","phone","exam","exam_price","coverage_percentage","coverage_amount","additional_fees","discount","total_amount","paid_amount","remaining_amount","payment_method","doctor","notes","unit","case_date"]
 with con() as c:
  old=c.execute("select * from patients where id=?",(i,)).fetchone()
  if not old:return jsonify(error="patient not found"),404
  vals=[d.get(k,old[k]) for k in editable_fields]+[((u or {}).get("username") or d.get("username")),i,expected]
  cur=c.execute("update patients set "+",".join(k+"=?" for k in editable_fields)+",username=?,row_version=row_version+1,updated_at=CURRENT_TIMESTAMP where id=? and row_version=?",vals)
  if not cur.rowcount:return jsonify(error="record changed by another user"),409
  c.execute("insert into audit_log(username,action,entity_type,entity_id,old_data,new_data) values(?,?,?,?,?,?)",((u or {}).get("username"),"UPDATE","patient",i,json.dumps(dict(old),ensure_ascii=False),json.dumps(d,ensure_ascii=False)))
 return jsonify(ok=True)
@app.delete("/api/patients/<int:i>")
def patientdelete(i):
 a=admin()
 if not a:return jsonify(error="admin required"),403
 with con() as c:
  old=c.execute("select * from patients where id=?",(i,)).fetchone()
  if not old:return jsonify(error="patient not found"),404
  c.execute("delete from patients where id=?",(i,));c.execute("insert into audit_log(username,action,entity_type,entity_id,old_data) values(?,?,?,?,?)",(a["username"],"DELETE","patient",i,json.dumps(dict(old),ensure_ascii=False)))
 return jsonify(ok=True)
@app.post("/api/migration/rev7")
def migrate():
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {};stats={}
 with con() as c:
  for p in d.get("paymentTypes",[]):
   try:c.execute("insert into payment_types(name,category,notes) values(?,?,?)",(p.get("name"),p.get("category"),p.get("notes")))
   except sqlite3.IntegrityError:pass
  for e in d.get("exams",[]):
   try:c.execute("insert into exams(unit,name,base_price) values(?,?,?)",(e.get("unit"),e.get("name"),float(e.get("price") or 0)))
   except sqlite3.IntegrityError:pass
  inserted=0
  for p in d.get("patients",[]):
   if p.get("id") is not None and c.execute("select 1 from patients where legacy_id=?",(p.get("id"),)).fetchone():continue
   cols=["legacy_id","name","payment_type","phone","exam","exam_price","coverage_percentage","coverage_amount","additional_fees","discount","total_amount","doctor","notes","username","unit","case_date","timestamp"]
   vals=[p.get("id"),p.get("name"),p.get("paymentType"),p.get("phone"),p.get("exam"),p.get("examPrice"),p.get("coveragePercentage"),p.get("coverageAmount"),p.get("additionalFees"),p.get("discount"),p.get("totalAmount"),p.get("doctor"),p.get("notes"),p.get("user"),p.get("unit"),p.get("date"),p.get("timestamp")]
   c.execute("insert into patients("+",".join(cols)+") values("+",".join(["?"]*len(cols))+")",vals);inserted+=1
  stats={"patients_inserted":inserted,"patients_received":len(d.get("patients",[])),"exams_received":len(d.get("exams",[])),"payment_types_received":len(d.get("paymentTypes",[]))}
 return jsonify(ok=True,**stats)
@app.get("/api/patients/by-phone/<path:phone>")
def patientphone(phone):
 with con() as c:
  rows=[dict(x) for x in c.execute("select id,name,phone,payment_type,unit,exam,doctor,case_date,total_amount,paid_amount,remaining_amount from patients where phone=? order by case_date desc,id desc limit 20",(phone,))]
 return jsonify(found=bool(rows),history=rows)
@app.get("/api/appointments")
def appts():
 if not allowed("booking_manage"):return jsonify(error="permission denied"),403
 q="select * from appointments where 1=1";a=[]
 if request.args.get("date"):q+=" and appointment_date=?";a.append(request.args["date"])
 if request.args.get("status") not in (None,"all"):q+=" and status=?";a.append(request.args["status"])
 with con() as c:return jsonify([dict(x) for x in c.execute(q+" order by appointment_date,appointment_time,id desc",a)])
@app.post("/api/appointments")
def apptadd():
 if not allowed("booking_manage"):return jsonify(error="permission denied"),403
 d=request.json or {};u=user();cols=["patient_name","phone","payment_type","unit","exam","appointment_date","appointment_time","period","doctor","notes","status","created_by","updated_by"];v=[d.get(k) for k in cols];v[10]=v[10] or "Booked";v[11]=v[11] or (u["username"] if u else "");v[12]=v[11]
 with con() as c:r=c.execute(f"insert into appointments({','.join(cols)}) values({','.join(['?']*len(cols))})",v);return jsonify(id=r.lastrowid),201
@app.put("/api/appointments/<int:i>")
def apptedit(i):
 if not allowed("booking_manage"):return jsonify(error="permission denied"),403
 d=request.json or {};u=user();expected=int(d.get("row_version",1));editable_fields=["patient_name","phone","payment_type","unit","exam","appointment_date","appointment_time","period","doctor","notes","status"]
 with con() as c:
  old=c.execute("select * from appointments where id=?",(i,)).fetchone()
  if not old:return jsonify(error="appointment not found"),404
  vals=[d.get(k,old[k]) for k in editable_fields]+[((u or {}).get("username")),i,expected]
  cur=c.execute("update appointments set "+",".join(k+"=?" for k in editable_fields)+",updated_by=?,row_version=row_version+1,updated_at=CURRENT_TIMESTAMP where id=? and row_version=?",vals)
  if not cur.rowcount:return jsonify(error="appointment changed by another user"),409
  c.execute("insert into audit_log(username,action,entity_type,entity_id,old_data,new_data) values(?,?,?,?,?,?)",((u or {}).get("username"),"UPDATE","appointment",i,json.dumps(dict(old),ensure_ascii=False),json.dumps(d,ensure_ascii=False)))
 return jsonify(ok=True)
@app.post("/api/appointments/<int:i>/convert")
def apptconvert(i):
 if not allowed("booking_manage"):return jsonify(error="permission denied"),403
 u=user()
 with con() as c:
  a=c.execute("select * from appointments where id=?",(i,)).fetchone()
  if not a:return jsonify(error="appointment not found"),404
  if a["converted_patient_id"]:return jsonify(error="already converted",patient_id=a["converted_patient_id"]),409
  pt=a["payment_type"] or ""; ex=a["exam"] or ""; day=a["appointment_date"]
  pr=c.execute("select i.id item_id,p.id plan_id,p.name plan_name,p.version,i.price,i.coverage_percentage from price_plan_items i join price_plans p on p.id=i.price_plan_id join payment_types t on t.id=p.payment_type_id join exams e on e.id=i.exam_id where t.name=? and e.name=? and p.active=1 and i.active=1 and p.valid_from<=? and (p.valid_to is null or p.valid_to='' or p.valid_to>=?) order by p.version desc,p.id desc limit 1",(pt,ex,day,day)).fetchone()
  if pr: price=float(pr["price"] or 0);cov=float(pr["coverage_percentage"] or 0);plan_id=pr["plan_id"];item_id=pr["item_id"];plan_name=pr["plan_name"];plan_version=pr["version"]
  else:
   er=c.execute("select id,base_price from exams where name=? and unit=? and active=1 order by id desc limit 1",(ex,a["unit"])).fetchone();price=float(er["base_price"] or 0) if er else 0;cov=0;plan_id=None;item_id=None;plan_name=None;plan_version=None
  covamt=price*cov/100;total=max(0,price-covamt)
  snap=json.dumps({"price":price,"coverage_percentage":cov,"coverage_amount":covamt,"additional_fees":0,"discount":0,"total_amount":total,"plan_id":plan_id,"item_id":item_id,"plan_name":plan_name,"plan_version":plan_version,"payment_type":pt,"exam":ex,"source":"appointment_conversion","captured_at":datetime.now().isoformat()},ensure_ascii=False)
  r=c.execute("insert into patients(name,payment_type,phone,exam,exam_price,coverage_percentage,coverage_amount,additional_fees,discount,total_amount,paid_amount,remaining_amount,payment_method,doctor,notes,username,unit,case_date,timestamp,price_plan_id,price_plan_item_id,price_snapshot) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(a["patient_name"],pt,a["phone"],ex,price,cov,covamt,0,0,total,0,total,"Contract" if pt else "Cash",a["doctor"] or "",a["notes"] or "",(u or {}).get("username"),a["unit"],day,datetime.now().isoformat(),plan_id,item_id,snap))
  c.execute("update appointments set status='Converted',converted_patient_id=?,updated_by=?,row_version=row_version+1,updated_at=CURRENT_TIMESTAMP where id=?",(r.lastrowid,(u or {}).get("username"),i))
  c.execute("insert into audit_log(username,action,entity_type,entity_id,new_data) values(?,?,?,?,?)",((u or {}).get("username"),"CONVERT","appointment",i,json.dumps({"patient_id":r.lastrowid,"price":price,"coverage_percentage":cov,"total_amount":total,"price_plan_id":plan_id},ensure_ascii=False)))
 return jsonify(ok=True,patient_id=r.lastrowid)
@app.delete("/api/appointments/<int:i>")
def apptdelete(i):
 a=admin()
 if not a:return jsonify(error="admin required"),403
 with con() as c:
  old=c.execute("select * from appointments where id=?",(i,)).fetchone()
  if not old:return jsonify(error="appointment not found"),404
  c.execute("delete from appointments where id=?",(i,));c.execute("insert into audit_log(username,action,entity_type,entity_id,old_data) values(?,?,?,?,?)",(a["username"],"DELETE","appointment",i,json.dumps(dict(old),ensure_ascii=False)))
 return jsonify(ok=True)
@app.get("/api/export/patients.xlsx")
def exportpatients():
 if not allowed("export"):return jsonify(error="permission denied"),403
 q="select * from patients where 1=1";a=[]
 for col,arg in [("case_date","date"),("unit","unit")]:
  v=request.args.get(arg)
  if v and v!="all":q+=" and "+col+"=?";a.append(v)
 with con() as c:rows=[dict(x) for x in c.execute(q+" order by id",a)]
 wb=Workbook();ws=wb.active;ws.title="Patients"
 headers=["ID","Date","Name","Phone","Payment Type","Unit","Exam","Exam Price","Coverage %","Coverage Amount","Additional Fees","Discount","Total","Doctor","User"]
 keys=["id","case_date","name","phone","payment_type","unit","exam","exam_price","coverage_percentage","coverage_amount","additional_fees","discount","total_amount","doctor","username"]
 ws.append(headers)
 for r in rows:ws.append([r.get(k) for k in keys])
 fill=PatternFill("solid",fgColor="1B2A6B");font=Font(color="FFFFFF",bold=True)
 for cell in ws[1]:cell.fill=fill;cell.font=font;cell.alignment=Alignment(horizontal="center")
 widths=[8,14,28,16,22,14,28,14,12,16,16,12,14,24,18]
 for i,w in enumerate(widths,1):ws.column_dimensions[chr(64+i)].width=w
 ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
 out=BytesIO();wb.save(out);out.seek(0)
 return send_file(out,as_attachment=True,download_name="FayoumScan_Patients_"+(request.args.get("date") or "All")+".xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
@app.get("/api/price-plans/<int:pid>/export.xlsx")
def exportplan(pid):
 with con() as c:
  p=c.execute("select p.*,t.name payment_type from price_plans p join payment_types t on t.id=p.payment_type_id where p.id=?",(pid,)).fetchone()
  if not p:return jsonify(error="plan not found"),404
  rows=c.execute("select e.unit,e.id exam_id,e.name,i.price,i.coverage_percentage,i.active from exams e left join price_plan_items i on i.exam_id=e.id and i.price_plan_id=? where e.active=1 order by e.unit,e.name",(pid,)).fetchall()
 wb=Workbook();ws=wb.active;ws.title="Price Plan";ws.append(["Unit","Exam ID","Exam Name","Price","Coverage %","Active"])
 for r in rows:ws.append([r["unit"],r["exam_id"],r["name"],r["price"] if r["price"] is not None else "",r["coverage_percentage"] if r["coverage_percentage"] is not None else 0,r["active"] if r["active"] is not None else 1])
 for c in ws[1]:c.fill=PatternFill("solid",fgColor="1B2A6B");c.font=Font(color="FFFFFF",bold=True);c.alignment=Alignment(horizontal="center")
 for col,w in {"A":18,"B":12,"C":36,"D":16,"E":16,"F":12}.items():ws.column_dimensions[col].width=w
 info=wb.create_sheet("Instructions");info.append(["FAYOUM SCAN RIS - Price Plan"]);info.append(["Payment Type",p["payment_type"]]);info.append(["Plan",p["name"]]);info.append(["Version",p["version"]]);info.append(["Valid From",p["valid_from"]]);info.append(["Do not change Exam ID. Enter Price and Coverage %, then import this workbook."])
 out=BytesIO();wb.save(out);out.seek(0);return send_file(out,as_attachment=True,download_name="PricePlan_"+str(pid)+".xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
@app.post("/api/price-plans/<int:pid>/import.xlsx")
def importplan(pid):
 if not admin():return jsonify(error="admin required"),403
 if "file" not in request.files:return jsonify(error="xlsx file required"),400
 try:wb=load_workbook(request.files["file"],data_only=True);ws=wb["Price Plan"]
 except Exception as e:return jsonify(error="invalid xlsx: "+str(e)),400
 parsed=[];errors=[]
 for n,row in enumerate(ws.iter_rows(min_row=2,values_only=True),2):
  if not any(v is not None and v!="" for v in row):continue
  try:
   exam_id=int(row[1]);price=float(row[3]);coverage=float(row[4] or 0);active=1 if row[5] in (None,"",1,True,"1","Yes","YES") else 0
   if price<0 or not 0<=coverage<=100:raise ValueError("invalid price/coverage")
   parsed.append((pid,exam_id,price,coverage,active))
  except Exception as e:errors.append({"row":n,"error":str(e)})
 if errors:return jsonify(error="validation failed",errors=errors),422
 with con() as c:
  if not c.execute("select 1 from price_plans where id=?",(pid,)).fetchone():return jsonify(error="plan not found"),404
  for x in parsed:c.execute("insert into price_plan_items(price_plan_id,exam_id,price,coverage_percentage,active) values(?,?,?,?,?) on conflict(price_plan_id,exam_id) do update set price=excluded.price,coverage_percentage=excluded.coverage_percentage,active=excluded.active",x)
 return jsonify(ok=True,imported=len(parsed))
@app.get("/api/permissions")
def permissions():
 u=user()
 if not u:return jsonify(error="login required"),401
 if u["role"]=="admin":return jsonify(role="admin",permissions=["*"])
 with con() as c:return jsonify(role=u["role"],permissions=[x["permission"] for x in c.execute("select permission from role_permissions where role=? and allowed=1",(u["role"],))])
@app.put("/api/permissions/<role>")
def setpermissions(role):
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {};perms=d.get("permissions",[])
 with con() as c:
  c.execute("delete from role_permissions where role=?",(role,))
  for p in perms:c.execute("insert into role_permissions(role,permission,allowed) values(?,?,1)",(role,p))
 return jsonify(ok=True)
@app.get("/api/settings")
def getsettings():
 with con() as c:return jsonify({x["key"]:x["value"] for x in c.execute("select key,value from settings")})
@app.put("/api/settings")
def putsettings():
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 with con() as c:
  for k,v in d.items():c.execute("insert into settings(key,value) values(?,?) on conflict(key) do update set value=excluded.value",(k,str(v)))
 return jsonify(ok=True)
@app.put("/api/users/<int:i>")
def edituser(i):
 if not admin():return jsonify(error="admin required"),403
 d=request.json or {}
 with con() as c:
  if "password" in d and d["password"]:c.execute("update users set password_hash=? where id=?",(hp(d["password"]),i))
  if "role" in d:c.execute("update users set role=? where id=?",(d["role"],i))
  if "active" in d:c.execute("update users set active=? where id=?",(int(bool(d["active"])),i))
 return jsonify(ok=True)
@app.get("/api/dashboard")
def dashboard():
 if not allowed("view_financial"):return jsonify(error="permission denied"),403
 day=request.args.get("date");unit=request.args.get("unit");q=" from patients where 1=1";a=[]
 if day:q+=" and case_date=?";a.append(day)
 if unit and unit!="all":q+=" and unit=?";a.append(unit)
 with con() as c:
  r=c.execute("select count(*) cases,coalesce(sum(total_amount),0) total,coalesce(sum(paid_amount),0) paid,coalesce(sum(remaining_amount),0) remaining,coalesce(sum(discount),0) discounts"+q,a).fetchone()
  contracts=c.execute("select count(*)"+q+" and coalesce(payment_type,'') not in ('','Cash','CASH','نقدي')",a).fetchone()[0]
 return jsonify(**dict(r),contracts=contracts)
@app.post("/api/backups/<path:name>/restore")
def restore(name):
 if not admin():return jsonify(error="admin required"),403
 safe=os.path.basename(name);src=os.path.join(BACKUPS,safe)
 if not os.path.isfile(src):return jsonify(error="backup not found"),404
 check=sqlite3.connect(src)
 try:
  ok=check.execute("pragma integrity_check").fetchone()[0]
 finally:check.close()
 if ok!="ok":return jsonify(error="backup integrity check failed"),422
 safety=os.path.join(BACKUPS,"before_restore_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".db")
 with con() as live:
  out=sqlite3.connect(safety);live.backup(out);out.close()
  source=sqlite3.connect(src);source.backup(live);source.close()
 return jsonify(ok=True,safety_backup=os.path.basename(safety))
@app.get("/api/audit")
def audit():
 if not admin():return jsonify(error="admin required"),403
 with con() as c:return jsonify([dict(x) for x in c.execute("select * from audit_log order by id desc limit 300")])
@app.post("/api/backup")
def backup():
 if not admin():return jsonify(error="admin required"),403
 f="fayoum_scan_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".db";dest=os.path.join(BACKUPS,f)
 with con() as s:d=sqlite3.connect(dest);s.backup(d);d.close()
 return jsonify(ok=True,file=f)
@app.get("/api/backups")
def backups():
 if not admin():return jsonify(error="admin required"),403
 return jsonify(sorted([x for x in os.listdir(BACKUPS) if x.endswith(".db")],reverse=True))
@app.get("/")
def index():return send_from_directory(WEB,"index.html")
@app.get("/<path:p>")
def staticfiles(p):return send_from_directory(WEB,p)

if __name__=="__main__":
 init()
 try:
  from waitress import serve;serve(app,host="0.0.0.0",port=int(os.getenv("PORT","8787")),threads=8)
 except ImportError:app.run(host="0.0.0.0",port=8787,threaded=True)
