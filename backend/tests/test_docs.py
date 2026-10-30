from __future__ import annotations

from conftest import PDF_BYTES, png_bytes, sent_emails, signup_and_login
from sqlalchemy import select

from app.core.db import SessionLocal
import uuid

from app.models.admin_action import AdminAction
from app.models.business_document import BusinessDocument


async def test_doc_upload_rejects_disguised_html(client):
    await signup_and_login(client, "doc1@kaverifoods.in")
    html = b"<html><script>alert(1)</script></html>"
    r = await client.post(
        "/me/verification-docs",
        data={"cert_type": "GST Certificate"},
        files={"file": ("gst.png", html, "image/png")},
    )
    assert r.status_code == 415
    r = await client.post(
        "/me/verification-docs",
        data={"cert_type": "GST Certificate"},
        files={"file": ("gst.pdf", b"", "application/pdf")},
    )
    assert r.status_code == 400


async def test_doc_access_control(client, make_client, admin_client):
    owner = await signup_and_login(client, "doc2@kaverifoods.in")
    r = await client.post(
        "/me/verification-docs",
        data={"cert_type": "GST Certificate"},
        # Lying filename/content-type: we store by sniffed type.
        files={"file": ("../../evil.html", PDF_BYTES, "text/html")},
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["mimeType"] == "application/pdf"
    assert doc["url"] == f"/me/verification-docs/{doc['id']}/file"
    assert doc["filename"] == "evil.html"

    r = await client.get(doc["url"])
    assert r.status_code == 200
    assert r.content == PDF_BYTES
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-disposition"].startswith("inline")

    # Other user → 404; anonymous → 401; legacy public path → gone.
    stranger = make_client()
    await signup_and_login(stranger, "doc3@othermill.in")
    assert (await stranger.get(doc["url"])).status_code == 404
    assert (await stranger.delete(f"/me/verification-docs/{doc['id']}")).status_code == 404
    assert (await make_client().get(doc["url"])).status_code == 401
    assert (await make_client().get(f"/admin/docs/{doc['id']}/file")).status_code == 401
    assert (await stranger.get(f"/uploads/verification/{owner['businessId']}/x.pdf")).status_code == 404

    # Admin sees admin URLs and can download.
    pending = (await admin_client.get("/admin/docs/pending")).json()
    assert pending[0]["doc"]["url"] == f"/admin/docs/{doc['id']}/file"
    r = await admin_client.get(pending[0]["doc"]["url"])
    assert r.status_code == 200 and r.content == PDF_BYTES

    # Admin reject → audit + email.
    r = await admin_client.post(f"/admin/docs/{doc['id']}/reject", json={"reason": "Blurry scan"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert any("not accepted" in m.subject for m in sent_emails("doc2@kaverifoods.in"))
    r = await admin_client.post(f"/admin/docs/{doc['id']}/approve")
    assert r.json()["status"] == "approved"
    async with SessionLocal() as db:
        rows = list(await db.scalars(select(AdminAction).order_by(AdminAction.created_at)))
        stored = await db.get(BusinessDocument, uuid.UUID(doc["id"]))
    # The admin's file view is audited first (no file contents in the log).
    assert [a.action for a in rows] == ["kyb.file_viewed", "doc.reject", "doc.approve"]
    assert rows[0].target_type == "business_document" and rows[0].details["business_id"] == owner["businessId"]
    assert {a.target_type for a in rows[1:]} == {"document"}
    assert rows[1].details["businessId"] == owner["businessId"]
    # Stored per business, reviewer recorded.
    assert str(stored.business_id) == owner["businessId"] and str(stored.uploaded_by_user_id) == owner["userId"]
    assert stored.storage_key.startswith(f"verification/{stored.business_id}/")
    assert stored.reviewed_by == "admin@cor1x.test" and stored.doc_type == "GST Certificate"

    listed = (await client.get("/me/verification-docs")).json()
    assert listed[0]["status"] == "approved"

    # Owner deletes → file gone.
    assert (await client.delete(f"/me/verification-docs/{doc['id']}")).status_code == 204
    assert (await client.get(doc["url"])).status_code == 404


async def test_image_docs_accepted(client):
    await signup_and_login(client, "doc4@kaverifoods.in")
    r = await client.post(
        "/me/verification-docs",
        data={"cert_type": "FSSAI"},
        files={"file": ("scan", png_bytes(), "application/octet-stream")},
    )
    assert r.status_code == 201
    assert r.json()["mimeType"] == "image/png"
