import os,sys,tempfile,json
os.environ["FAYOUM_SCAN_DATA_DIR"]=tempfile.mkdtemp(prefix="fayoum_test_")
sys.path.insert(0,os.path.abspath("."))
from server.app import app,init
init()
c=app.test_client()
def ok(r,code=None):
 if code is None: assert 200 <= r.status_code < 300,(r.status_code,r.get_data(as_text=True))
 else: assert r.status_code==code,(r.status_code,r.get_data(as_text=True))
r=c.get("/api/health");ok(r)
r=c.get("/api/patients");ok(r,401)
r=c.get("/api/payment-types");ok(r,401)
r=c.get("/api/exams");ok(r,401)
r=c.get("/api/price-plans");ok(r,401)
r=c.get("/api/settings");ok(r,401)
r=c.get("/api/pricing/resolve?payment_type=Cash&exam=X");ok(r,401)
r=c.get("/api/patients/by-phone/01000000000");ok(r,401)

r=c.get("/api/export/patients.xlsx");ok(r,401)
r=c.post("/api/login",json={"username":"admin","password":"admin123"});ok(r)
j=r.get_json();assert j.get("token")
H={"Authorization":"Bearer "+j["token"]}
r=c.get("/api/patients",headers=H);ok(r,428)
r=c.post("/api/change-password",headers=H,json={"current_password":"admin123","new_password":"BetaPass987"});ok(r)
r=c.get("/api/patients",headers=H);ok(r)
r=c.get("/api/permissions",headers=H);ok(r);assert "*" in r.get_json()["permissions"]
r=c.get("/api/permissions/user",headers=H);ok(r);assert "patient_edit" in r.get_json()["permissions"]

r=c.post("/api/payment-types",headers=H,json={"name":"TEST CONTRACT","category":"Contract"});ok(r); payid=r.get_json()["id"]
r=c.post("/api/exams",headers=H,json={"unit":"CT","name":"TEST CT","base_price":1000});ok(r); examid=r.get_json()["id"]
r=c.post("/api/patients",headers=H,json={"name":"TEST PATIENT","phone":"01000000000","payment_type":"Cash","unit":"CT","exam":"TEST CT","exam_price":1000,"coverage_percentage":10,"coverage_amount":100,"additional_fees":50,"discount":25,"paid_amount":500,"remaining_amount":425,"total_amount":925,"price_snapshot":"{\"price\":1000,\"coverage_percentage\":10,\"total_amount\":925}","case_date":"2026-09-26"});ok(r)
pid=r.get_json().get("id");assert pid
r=c.get("/api/patients?date=2026-09-26",headers=H);ok(r)
rows=r.get_json();assert any(x["id"]==pid for x in rows)
row=next(x for x in rows if x["id"]==pid)
assert row["exam_price"]==1000 and row["coverage_percentage"]==0 and row["coverage_amount"]==0 and row["additional_fees"]==50 and row["total_amount"]==1025 and row["remaining_amount"]==525; snap=json.loads(row["price_snapshot"]);assert snap["price"]==1000 and snap["coverage_percentage"]==0 and snap["total_amount"]==1025 and snap["payment_type"]=="Cash"
r=c.put(f"/api/patients/{pid}",headers=H,json={"name":"TEST PATIENT UPDATED","row_version":row["row_version"]});ok(r)
r=c.get("/api/dashboard?date=2026-09-26",headers=H);ok(r);assert r.get_json()["cases"]>=1
r=c.get("/api/export/patients.xlsx?date=2026-09-26",headers=H);ok(r);assert "spreadsheetml" in r.content_type
r=c.post("/api/appointments",headers=H,json={"patient_name":"BOOKING TEST","phone":"01111111111","unit":"MRI","appointment_date":"2026-09-27","status":"Booked"});ok(r)
r=c.get("/api/appointments?date=2026-09-27",headers=H);ok(r);assert len(r.get_json())>=1
print("FAYOUM SCAN RIS smoke tests passed")

r=c.post("/api/price-plans",headers=H,json={"payment_type_id":payid,"name":"TEST PLAN","version":1,"valid_from":"2026-01-01","active":1});ok(r); planid=r.get_json()["id"]
r=c.post(f"/api/price-plans/{planid}/items",headers=H,json={"exam_id":examid,"price":800,"coverage_percentage":25});ok(r)
r=c.post("/api/patients",headers=H,json={"name":"TAMPER TEST","phone":"01555555555","payment_type":"TEST CONTRACT","unit":"CT","exam":"TEST CT","exam_price":1,"coverage_percentage":99,"case_date":"2026-09-26","paid_amount":0});ok(r); tamperid=r.get_json()["id"]
r=c.get("/api/patients?date=2026-09-26",headers=H);ok(r); trow=next(x for x in r.get_json() if x["id"]==tamperid);assert trow["exam_price"]==800 and trow["coverage_percentage"]==25 and trow["total_amount"]==600

r=c.put(f"/api/patients/{tamperid}",headers=H,json={"exam_price":1,"coverage_percentage":99,"additional_fees":40,"discount":10,"row_version":trow["row_version"]});ok(r)
r=c.get("/api/patients?date=2026-09-26",headers=H);ok(r)
et=next(x for x in r.get_json() if x["id"]==tamperid)
assert et["exam_price"]==800 and et["coverage_percentage"]==25 and et["coverage_amount"]==200 and et["total_amount"]==630
es=json.loads(et["price_snapshot"]);assert es["source"]=="patient_edit" and es["plan_id"]==planid and es["price"]==800
r=c.get("/api/pricing/resolve?payment_type=TEST%20CONTRACT&exam=TEST%20CT&unit=CT&date=2026-09-26",headers=H);ok(r); pricing=r.get_json();assert pricing["found"] and pricing["price"]==800 and pricing["coverage_percentage"]==25
r=c.get(f"/api/price-plans/{planid}/items",headers=H);ok(r);assert len(r.get_json())==1
r=c.post("/api/appointments",headers=H,json={"patient_name":"PRICED BOOKING","phone":"01222222222","payment_type":"TEST CONTRACT","unit":"CT","exam":"TEST CT","appointment_date":"2026-09-28","status":"Booked"});ok(r); apid=r.get_json()["id"]
r=c.get("/api/appointments?date=2026-09-28",headers=H);ok(r); arow=next(x for x in r.get_json() if x["id"]==apid); oldver=arow["row_version"]
r=c.put(f"/api/appointments/{apid}",headers=H,json={"appointment_time":"11:30","row_version":oldver});ok(r)
r=c.put(f"/api/appointments/{apid}",headers=H,json={"appointment_time":"12:00","row_version":oldver});ok(r,409)
r=c.get("/api/appointments?date=2026-09-28",headers=H);ok(r); arow=next(x for x in r.get_json() if x["id"]==apid); assert arow["appointment_time"]=="11:30"
r=c.post(f"/api/appointments/{apid}/convert",headers=H);ok(r); converted=r.get_json()["patient_id"]
r=c.get("/api/patients?date=2026-09-28",headers=H);ok(r); prow=next(x for x in r.get_json() if x["id"]==converted);assert prow["exam_price"]==800 and prow["coverage_percentage"]==25 and prow["coverage_amount"]==200 and prow["total_amount"]==600 and prow["remaining_amount"]==600 and prow["price_plan_id"]==planid; ps=json.loads(prow["price_snapshot"]);assert ps["plan_id"]==planid and ps["plan_version"]==1 and ps["price"]==800 and ps["source"]=="appointment_conversion"

r=c.put(f"/api/price-plans/{planid}",headers=H,json={"version":2,"valid_to":"2026-12-31"});ok(r)
r=c.put(f"/api/payment-types/{payid}",headers=H,json={"name":"TEST CONTRACT UPDATED","category":"Contract"});ok(r)
r=c.put(f"/api/exams/{examid}",headers=H,json={"unit":"CT","name":"TEST CT UPDATED","base_price":1100});ok(r)
r=c.put(f"/api/exams/{examid}",headers=H,json={"active":0});ok(r)
r=c.get("/api/exams?unit=CT",headers=H);ok(r);assert not any(x["id"]==examid for x in r.get_json())
r=c.post("/api/backup",headers=H);ok(r); backup_name=r.get_json()["file"]
r=c.put("/api/settings",headers=H,json={"restore_probe":"before"});ok(r)
r=c.post("/api/backup",headers=H);ok(r); restore_name=r.get_json()["file"]
r=c.put("/api/settings",headers=H,json={"restore_probe":"after"});ok(r)
r=c.post("/api/backups/"+restore_name+"/restore",headers=H);ok(r);assert r.get_json().get("safety_backup")
r=c.get("/api/settings",headers=H);ok(r);assert r.get_json().get("restore_probe")=="before"



# REV.7 JSON migration: preserve patients/exams/payment types/settings and archive legacy user metadata.
legacy={"paymentTypes":[{"name":"LEGACY CASH","category":"Cash","notes":"REV7"}],"exams":[{"unit":"MRI","name":"LEGACY MRI","price":777}],"patients":[{"id":7001,"name":"LEGACY PATIENT","paymentType":"LEGACY CASH","phone":"01070010000","exam":"LEGACY MRI","examPrice":777,"coveragePercentage":0,"coverageAmount":0,"additionalFees":10,"discount":7,"totalAmount":780,"doctor":"DR LEGACY","notes":"REV7 IMPORT","user":"legacyuser","unit":"MRI","date":"2025-01-17","timestamp":"2025-01-17T10:00:00"}],"settings":[{"key":"legacy_center","value":"Fayoum Scan REV7"}],"users":[{"username":"legacyuser","type":"admin","lastLogin":"2025-01-17"}],"backups":[{"id":1,"name":"legacy backup"}]}
r=c.post("/api/migration/rev7",headers=H,json=legacy);ok(r);mj=r.get_json();assert mj["patients_inserted"]==1 and mj["settings_saved"]==1 and mj["legacy_users_archived"]==1 and mj["legacy_backups_received"]==1
r=c.get("/api/patients?date=2025-01-17",headers=H);ok(r);lr=next(x for x in r.get_json() if x["legacy_id"]==7001);assert lr["name"]=="LEGACY PATIENT" and lr["exam_price"]==777 and lr["total_amount"]==780
r=c.get("/api/settings",headers=H);ok(r);ls=r.get_json();assert ls["legacy_center"]=="Fayoum Scan REV7" and "legacyuser" in ls["legacy_rev7_users"]
r=c.post("/api/migration/rev7",headers=H,json=legacy);ok(r);assert r.get_json()["patients_inserted"]==0
print("REV.7 migration smoke tests passed")
