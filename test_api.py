# -*- coding: utf-8 -*-
"""End-to-end API test against a running server on :8080."""
import httpx

BASE = "http://127.0.0.1:8080"
c = httpx.Client(base_url=BASE, timeout=10)

# setup flow
s = c.get("/api/state").json()
assert s["needs_setup"] is True and s["user"] is None
r = c.post("/api/setup", json={"username": "aka", "password": "1234", "name": "Brother"})
assert r.status_code == 200, r.text
assert "session" in c.cookies
s = c.get("/api/state").json()
assert s["user"]["role"] == "admin"

# unauth client rejected
anon = httpx.Client(base_url=BASE, timeout=10)
assert anon.get("/api/houses").status_code == 401
assert anon.post("/api/setup", json={"username": "x", "password": "yyyy"}).status_code == 400

# login wrong / right
assert anon.post("/api/login", json={"username": "aka", "password": "bad"}).status_code == 401
assert anon.post("/api/login", json={"username": "AKA", "password": "1234"}).status_code == 200

# create houses
h1 = c.post("/api/houses", json={
    "address": "Чиланзар, 5-кв, дом 12", "district": "Чиланзар", "deal_type": "rent",
    "purchase_price": 52000, "purchase_currency": "USD",
    "owner_name": "Азиз ака", "owner_phone": "+998901112233"}).json()
h2 = c.post("/api/houses", json={
    "address": "Юнусабад, 9-кв", "district": "Юнусабад", "deal_type": "sale",
    "purchase_price": 70000, "purchase_currency": "USD", "notes": "срочно"}).json()
assert h1["status"] == "available"

# filters
assert len(c.get("/api/houses?flt=all").json()) == 2
assert len(c.get("/api/houses?flt=sale").json()) == 1
assert len(c.get("/api/houses?flt=rent_free").json()) == 1

# edit house
r = c.patch(f"/api/houses/{h1['id']}", json={"address": "Чиланзар, 5-кв, дом 12А",
    "deal_type": "rent", "purchase_price": 52000, "purchase_currency": "USD"}).json()
assert r["address"].endswith("12А")

# partner
r = c.post(f"/api/houses/{h2['id']}/partners",
           json={"name": "Бекзод", "share": 50, "invested": 35000, "invested_currency": "USD"}).json()
assert r["partners"][0]["share"] == 50

# tenant move-in
r = c.post(f"/api/houses/{h1['id']}/tenants", json={
    "name": "Алишер", "phone": "+998901234567", "passport": "AB1234567",
    "rent_amount": 4000000, "rent_currency": "UZS", "due_day": 5, "move_in": "2026-06-01"})
assert r.status_code == 200, r.text
h1full = r.json()
tid = h1full["tenant"]["id"]
assert h1full["status"] == "rented"
assert h1full["tenant"]["paid_this_month"] is False

# double move-in rejected
assert c.post(f"/api/houses/{h1['id']}/tenants",
              json={"name": "X", "rent_amount": 1, "due_day": 1}).status_code == 400
# bad due day
assert c.post(f"/api/houses/{h2['id']}/tenants",
              json={"name": "X", "rent_amount": 1, "due_day": 31}).status_code == 400

# tenants list + debtors (due day 5, today is the 17th)
tl = c.get("/api/tenants").json()
assert len(tl) == 1 and tl[0]["paid_this_month"] is False
rep = c.get("/api/reports").json()
assert len(rep["debtors"]) == 1 and rep["debtors"][0]["overdue_days"] >= 0

# payment for current month
from datetime import date
today = date.today()
r = c.post("/api/payments", json={"tenant_id": tid, "amount": 4000000, "currency": "UZS",
                                  "period_year": today.year, "period_month": today.month})
assert r.status_code == 200
rep = c.get("/api/reports").json()
assert len(rep["debtors"]) == 0
assert rep["month"]["income"][0]["total"] == 4000000

# expenses
r = c.post("/api/expenses", json={"house_id": h1["id"], "category": "electricity",
                                  "amount": 150000, "currency": "UZS", "note": "свет"})
assert r.status_code == 200
assert c.post("/api/expenses", json={"house_id": h1["id"], "category": "bad",
                                     "amount": 1, "currency": "UZS"}).status_code == 400
hf = c.get(f"/api/houses/{h1['id']}").json()
assert hf["expenses_total"][0]["total"] == 150000
assert hf["rent_income"][0]["total"] == 4000000

# sold + profit
r = c.post(f"/api/houses/{h2['id']}/sold",
           json={"price": 85000, "currency": "USD", "buyer": "Карим"}).json()
assert r["status"] == "sold" and r["profit"] == 15000  # 85000-70000, no USD expenses

# move out
r = c.post(f"/api/tenants/{tid}/moveout").json()
assert r["status"] == "available" and r["tenant"] is None
assert r["history"][0]["total_paid"] == 4000000

# users admin
r = c.post("/api/users", json={"username": "partner1", "password": "5555", "name": "Шерик"})
assert r.status_code == 200
assert c.post("/api/users", json={"username": "partner1", "password": "5555"}).status_code == 400
users = c.get("/api/users").json()
assert len(users) == 2

# non-admin cannot manage users
p = httpx.Client(base_url=BASE, timeout=10)
p.post("/api/login", json={"username": "partner1", "password": "5555"})
assert p.get("/api/users").status_code == 403
assert p.get("/api/houses").status_code == 200

# profile
assert c.post("/api/profile", json={"lang": "uz", "tg_chat_id": "123456"}).status_code == 200
assert c.get("/api/state").json()["user"]["lang"] == "uz"

# logout
c.post("/api/logout")
assert c.get("/api/houses").status_code == 401

# index page served
assert "UyWeb" in anon.get("/").text

print("ALL API TESTS PASSED ✅")
