"""
PRD-03 Phase 4b: profile photo processing (Pillow, decision 19) and the
presign / complete / delete endpoints. Real generated images; R2 is an
in-memory fake.
"""
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import server
from profile_photo import MAX_PIXELS, PhotoRejected, process_photo
from test_vault import FakeCollection, UID

GPS_TAG = 0x8825
MAKE_TAG = 0x010F


def jpeg_with_gps(w=1200, h=1600):
    img = Image.new("RGB", (w, h), (200, 30, 30))
    img.paste((30, 30, 200), (0, h // 2, w, h))
    exif = Image.Exif()
    exif[MAKE_TAG] = "SecretCam"
    exif[GPS_TAG] = {1: "N", 2: (40.0, 44.0, 54.0), 3: "W", 4: (73.0, 59.0, 9.0)}
    buf = BytesIO()
    img.save(buf, "JPEG", exif=exif, comment=b"secret comment")
    return buf.getvalue()


def png_transparent():
    img = Image.new("RGBA", (500, 300), (0, 0, 0, 0))
    img.paste((0, 255, 0, 255), (100, 50, 400, 250))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def open_webp(data):
    img = Image.open(BytesIO(data))
    assert img.format == "WEBP"
    return img


# ---------------------------------------------------------------------------
# process_photo (pure)
# ---------------------------------------------------------------------------

def test_metadata_fully_stripped():
    out = process_photo(jpeg_with_gps())
    for size in (800, 200):
        img = open_webp(out[size])
        assert not img.getexif(), "EXIF must be gone"
        assert "exif" not in img.info and "xmp" not in img.info and "icc_profile" not in img.info
        assert b"SecretCam" not in out[size] and b"secret comment" not in out[size]


def test_squares_at_both_sizes_and_centered():
    out = process_photo(jpeg_with_gps(1200, 1600))   # portrait: red top half, blue bottom half
    big = open_webp(out[800]).convert("RGB")
    assert big.size == (800, 800) and open_webp(out[200]).size == (200, 200)
    top, bottom = big.getpixel((400, 50)), big.getpixel((400, 750))
    assert top[0] > 150 and bottom[2] > 150          # centre crop keeps both halves


def test_transparent_png_flattened_on_black():
    img = open_webp(process_photo(png_transparent())[800]).convert("RGB")
    assert img.getpixel((400, 20))[1] < 20           # former transparent strip (top) is dark
    assert img.getpixel((400, 400))[1] > 200         # green content kept


def test_rotation_tag_applied():
    img = Image.new("RGB", (400, 200), (255, 0, 0))
    img.paste((0, 0, 255), (200, 0, 400, 200))       # left red, right blue
    exif = Image.Exif()
    exif[0x0112] = 6                                 # rotate 90 CW on display
    buf = BytesIO()
    img.save(buf, "JPEG", exif=exif)
    out = open_webp(process_photo(buf.getvalue())[800]).convert("RGB")
    assert out.getpixel((400, 50))[0] > 150          # after rotation red is on top
    assert out.getpixel((400, 750))[2] > 150


@pytest.mark.parametrize("data", [
    b"", b"this is a text file pretending to be a jpg", b"\xff\xd8\xff" + b"\x00" * 50,
])
def test_garbage_rejected(data):
    with pytest.raises(PhotoRejected):
        process_photo(data)


def test_gif_rejected():
    buf = BytesIO()
    Image.new("RGB", (50, 50)).save(buf, "GIF")
    with pytest.raises(PhotoRejected):
        process_photo(buf.getvalue())


def test_oversized_pixel_count_rejected_without_decoding():
    # 8000 x 6000 = 48 MP > limit; a flat PNG of that size is small on disk.
    buf = BytesIO()
    Image.new("L", (8000, 6000)).save(buf, "PNG", optimize=True)
    assert 8000 * 6000 > MAX_PIXELS
    with pytest.raises(PhotoRejected):
        process_photo(buf.getvalue())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class ProfileCollection(FakeCollection):
    async def update_one(self, flt, update):
        result = await super().update_one(flt, update)
        for d in self.docs:
            if self._match(d, flt):
                for k in update.get("$unset", {}):
                    d.pop(k, None)
        return result


class FakeR2:
    def __init__(self):
        self.objects = {}
        self.deleted = []

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://r2.test/{op}/{Params['Key']}?ttl={ExpiresIn}"

    def head_object(self, Bucket, Key):
        return {"ContentLength": len(self.objects[Key])}

    def get_object(self, Bucket, Key):
        return {"Body": BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)
        self.objects.pop(Key, None)


@pytest.fixture
def env(monkeypatch):
    db = MagicMock()
    db.sync_profiles = ProfileCollection([{"user_id": UID, "slug": "tyler-example",
                                           "display_name": "Tyler Example", "photo_key": None}])
    monkeypatch.setattr(server, "db", db)
    r2 = FakeR2()
    monkeypatch.setattr(server, "r2_client", r2)
    monkeypatch.setattr(server.limiter, "enabled", False)
    server.app.dependency_overrides[server.require_artist] = lambda: {"sub": UID, "metadata": {"role": "artist"}}
    yield TestClient(server.app), db, r2
    server.app.dependency_overrides.clear()


def upload(client, r2, data, content_type="image/jpeg"):
    resp = client.post("/api/sync/profile/photo/presign",
                       json={"content_type": content_type, "file_size": len(data)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    key = body["presigned_url"].split("/put_object/")[1].split("?")[0]
    r2.objects[key] = data                           # the browser's PUT
    return body["upload_id"], key


def test_full_upload_flow(env):
    client, db, r2 = env
    upload_id, incoming = upload(client, r2, jpeg_with_gps())
    assert incoming.startswith("profiles/tyler-example/incoming/")
    resp = client.post("/api/sync/profile/photo/complete", json={"upload_id": upload_id})
    assert resp.status_code == 200, resp.text
    p = db.sync_profiles.docs[0]
    assert p["photo_key"].startswith("profiles/tyler-example/photo/")
    assert "photo_pending" not in p
    assert incoming not in r2.objects and incoming in r2.deleted      # original gone
    stored = [k for k in r2.objects if k.startswith(p["photo_key"])]
    assert sorted(stored) == sorted([f"{p['photo_key']}-800.webp", f"{p['photo_key']}-200.webp"])
    assert b"SecretCam" not in r2.objects[stored[0]]
    assert resp.json()["photo_url"] and resp.json()["photo_thumb_url"]


def test_bad_file_rejected_and_original_still_deleted(env):
    client, db, r2 = env
    upload_id, incoming = upload(client, r2, b"not an image at all")
    resp = client.post("/api/sync/profile/photo/complete", json={"upload_id": upload_id})
    assert resp.status_code == 422
    assert "couldn't be read" in resp.json()["detail"]
    assert incoming not in r2.objects
    assert db.sync_profiles.docs[0]["photo_key"] is None
    assert "photo_pending" not in db.sync_profiles.docs[0]


def test_size_mismatch_rejected(env):
    client, db, r2 = env
    upload_id, incoming = upload(client, r2, jpeg_with_gps())
    r2.objects[incoming] = r2.objects[incoming] + b"extra"
    assert client.post("/api/sync/profile/photo/complete",
                       json={"upload_id": upload_id}).status_code == 422
    assert incoming not in r2.objects


def test_replacing_photo_deletes_previous_files(env):
    client, db, r2 = env
    uid1, _ = upload(client, r2, jpeg_with_gps())
    client.post("/api/sync/profile/photo/complete", json={"upload_id": uid1})
    first = db.sync_profiles.docs[0]["photo_key"]
    uid2, _ = upload(client, r2, png_transparent(), "image/png")
    client.post("/api/sync/profile/photo/complete", json={"upload_id": uid2})
    second = db.sync_profiles.docs[0]["photo_key"]
    assert second != first
    assert not [k for k in r2.objects if k.startswith(first)]
    assert len([k for k in r2.objects if k.startswith(second)]) == 2


def test_delete_photo(env):
    client, db, r2 = env
    uid1, _ = upload(client, r2, jpeg_with_gps())
    client.post("/api/sync/profile/photo/complete", json={"upload_id": uid1})
    key = db.sync_profiles.docs[0]["photo_key"]
    resp = client.delete("/api/sync/profile/photo")
    assert resp.status_code == 200 and resp.json()["photo_url"] is None
    assert not [k for k in r2.objects if k.startswith(key)]


def test_wrong_upload_id_404(env):
    client, db, r2 = env
    upload(client, r2, jpeg_with_gps())
    assert client.post("/api/sync/profile/photo/complete",
                       json={"upload_id": "someone-elses"}).status_code == 404


def test_presign_needs_profile(env):
    client, db, r2 = env
    db.sync_profiles.docs.clear()
    resp = client.post("/api/sync/profile/photo/presign", json={"content_type": "image/jpeg", "file_size": 100})
    assert resp.status_code == 409 and "Save your profile first" in resp.json()["detail"]


@pytest.mark.parametrize("body", [
    {"content_type": "image/gif", "file_size": 100},
    {"content_type": "image/jpeg", "file_size": 10 * 1024 * 1024 + 1},
    {"content_type": "image/jpeg", "file_size": 0},
])
def test_presign_validation(env, body):
    client, db, r2 = env
    assert client.post("/api/sync/profile/photo/presign", json=body).status_code == 422
