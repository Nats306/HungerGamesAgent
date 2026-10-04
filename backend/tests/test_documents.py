import io

import docx

from tests.conftest import ADMIN, ALICE, BOB

MD = b"""---
title: 74th Hunger Games
source_url: https://example.org/74th
---
# Summary
The 74th Hunger Games were won by Katniss Everdeen and Peeta Mellark from District 12.
They threatened to eat poisonous nightlock berries, so the Gamemakers declared two victors.
"""


def upload(client, name="74th.md", data=MD):
    return client.post("/api/documents", files={"file": (name, data)})


def test_upload_markdown_is_processed(as_user):
    client = as_user(ALICE)
    response = upload(client)
    assert response.status_code == 202
    doc_id = response.json()["id"]

    # TestClient runs background tasks before returning, so it is already processed.
    doc = client.get(f"/api/documents/{doc_id}").json()
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1
    assert doc["title"] == "74th Hunger Games"
    assert doc["source_url"] == "https://example.org/74th"
    assert doc["can_delete"] is True


def test_upload_docx_and_csv(as_user):
    client = as_user(ALICE)
    buffer = io.BytesIO()
    d = docx.Document()
    d.add_paragraph("Rue was a tribute from District 11 in the 74th Hunger Games.")
    d.save(buffer)
    assert client.get(f"/api/documents/{upload(client, 'rue.docx', buffer.getvalue()).json()['id']}").json()["status"] == "ready"

    csv_data = b"name,district\nKatniss Everdeen,12\nRue,11\n"
    assert client.get(f"/api/documents/{upload(client, 'tributes.csv', csv_data).json()['id']}").json()["status"] == "ready"


def test_unsupported_and_empty_files(as_user):
    client = as_user(ALICE)
    assert upload(client, "virus.exe", b"MZ").status_code == 400
    assert upload(client, "empty.txt", b"").status_code == 400


def test_unreadable_file_is_marked_failed(as_user):
    client = as_user(ALICE)
    doc_id = upload(client, "broken.pdf", b"this is not a pdf").json()["id"]
    doc = client.get(f"/api/documents/{doc_id}").json()
    assert doc["status"] == "failed"
    assert doc["error"]


def test_only_owner_or_admin_can_delete(as_user):
    doc_id = upload(as_user(ALICE)).json()["id"]

    bob = as_user(BOB)
    assert bob.get("/api/documents").json()[0]["can_delete"] is False
    assert bob.delete(f"/api/documents/{doc_id}").status_code == 403

    admin = as_user(ADMIN)
    assert admin.delete(f"/api/documents/{doc_id}").status_code == 204
    assert admin.get("/api/documents").json() == []
