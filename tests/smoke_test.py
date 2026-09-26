import os,sys,tempfile
os.environ["FAYOUM_SCAN_DATA_DIR"]=tempfile.mkdtemp(prefix="fayoum_test_")
sys.path.insert(0,os.path.abspath("."))
from server.app import app,init
init()
c=app.test_client()
def ok(r,code=None):
 if code is None: assert 200 <= r.status_code < 300,(r.status_code,r.get_data(as_text=True))
 else: assert r.status_code==code,(r.status_code,r.get_data(as_text=True))
r=c.get("/api/health");ok(r)
r=c.post("/api/login",json={"username":"admin","password":"admin123"});ok(r)
j=r.get_json();assert j.get("token")
H={"Authorization":"Bearer "+j["token"]}
r=c.get("/api/permissions",headers=H);ok(r);assert "*" in r.get_json()["permissions"]
r=c.post("/api/payment-types",headers=H,json={"name":"TEST CONTRACT","category":"Contract"});ok(r)
r=c.post("/api/exams",headers=H,json={"unit":"CT","name":"TEST CT","base_price":1000});ok(r)
r=c.post("/api/patients",headers=H,json={"name":"TEST PATIENT","phone":"01000000000","payment_type":"Cash","unit":"CT","exam":"TEST CT","exam_price":1000,"coverage_percentage":10,"coverage_amount":100,"additional_fees":50,"discount":25,"paid_amount":500,"remaining_amount":425,"total_amount":925,"price_snapshot":"{\"price\":1000,\"coverage_percentage\":10,\"total_amount\":925}","case_date":"2026-09-26"});ok(r)
pid=r.get_json().get("id");assert pid
r=c.get("/api/patients?date=2026-09-26",headers=H);ok(r)
rows=r.get_json();assert any(x["id"]==pid for x in rows)
row=next(x for x in rows if x["id"]==pid)
assert row["coverage_amount"]==100 and row["additional_fees"]==50 and row["total_amount"]==925 and row["remaining_amount"]==425
r=c.put(f"/api/patients/{pid}",headers=H,json={"name":"TEST PATIENT UPDATED","row_version":row["row_version"]});ok(r)
r=c.get("/api/dashboard?date=2026-09-26",headers=H);ok(r);assert r.get_json()["cases"]>=1
r=c.get("/api/export/patients.xlsx?date=2026-09-26",headers=H);ok(r);assert "spreadsheetml" in r.content_type
r=c.post("/api/appointments",headers=H,json={"patient_name":"BOOKING TEST","phone":"01111111111","unit":"MRI","appointment_date":"2026-09-27","status":"Booked"});ok(r)
r=c.get("/api/appointments?date=2026-09-27",headers=H);ok(r);assert len(r.get_json())>=1
print("FAYOUM SCAN RIS smoke tests passed")
