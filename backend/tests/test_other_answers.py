"""Oct 26: "Other" answers need the typed name (distributor, genre), and IPI takes 9 to 11 digits."""
import pytest
from pydantic import ValidationError

import server
from sync_vault import metadata_patch_fields
from test_presign_consent import (  # noqa: F401  (pytest fixtures)
    base, client, fake_db, inserted_doc, intake, post,
)


def sync_body(**intake_overrides):
    return base(consent_ai_training=False, consent_sync=True, sync_intake=intake(**intake_overrides))


# Distributor ---------------------------------------------------------------

def test_distributor_other_needs_a_name(client, fake_db):
    resp = post(client, sync_body(distributor="Other"))
    assert resp.status_code == 422 and "Enter which distributor you use." in resp.text
    fake_db.track_submissions.insert_one.assert_not_awaited()


def test_distributor_other_is_stored(client, fake_db):
    resp = post(client, sync_body(distributor="Other", distributor_other="  Ditto Music "))
    assert resp.status_code == 200, resp.text
    doc = inserted_doc(fake_db)
    assert doc["intake"]["distributor"] == "Other"
    assert doc["intake"]["distributor_other"] == "Ditto Music"


def test_distributor_other_dropped_for_a_listed_distributor(client, fake_db):
    resp = post(client, sync_body(distributor="DistroKid", distributor_other="Ditto Music"))
    assert resp.status_code == 200, resp.text
    assert inserted_doc(fake_db)["intake"]["distributor_other"] is None


# Genre ---------------------------------------------------------------------

def test_genre_other_needs_a_name(client, fake_db):
    resp = post(client, base(genre="Other"))
    assert resp.status_code == 422 and "Enter which genre." in resp.text
    fake_db.track_submissions.insert_one.assert_not_awaited()


def test_genre_other_is_stored(client, fake_db):
    resp = post(client, base(genre="Other", genre_other=" Drill "))
    assert resp.status_code == 200, resp.text
    doc = inserted_doc(fake_db)
    assert doc["genre"] == "Other" and doc["genre_other"] == "Drill"


def test_genre_other_dropped_for_a_listed_genre(client, fake_db):
    resp = post(client, base(genre="Pop", genre_other="Drill"))
    assert resp.status_code == 200, resp.text
    assert inserted_doc(fake_db)["genre_other"] is None


def test_application_genre_other_needs_a_name():
    fields = dict(name="A", email="a@example.com", spotify_url="https://open.spotify.com/x",
                  genre="Other", bio="b")
    with pytest.raises(ValidationError, match="Enter which genre."):
        server.ArtistCreate(**fields)
    assert server.ArtistCreate(**fields, genre_other="Drill").genre_other == "Drill"


def test_vault_genre_other():
    with pytest.raises(ValidationError, match="Enter which genre."):
        server.VaultMetadataPatch(genre="Other")
    p = server.VaultMetadataPatch(genre="Other", genre_other="Drill")
    assert metadata_patch_fields(None, None, None, p.genre, p.genre_other) == {
        "genre": "Other", "genre_other": "Drill"}
    assert metadata_patch_fields(None, None, None, "Pop", "Drill") == {"genre": "Pop", "genre_other": None}


# IPI -----------------------------------------------------------------------

@pytest.mark.parametrize("ipi, stored", [
    ("123456789", "123456789"), ("1234567890", "1234567890"),
    ("00123456789", "00123456789"), ("00123.456.789", "00123456789"),
])
def test_sync_ipi_every_pro_format(client, fake_db, ipi, stored):
    resp = post(client, sync_body(ipi=ipi))
    assert resp.status_code == 200, resp.text
    assert inserted_doc(fake_db)["intake"]["ipi"] == stored


@pytest.mark.parametrize("ipi", ["12345678", "123456789012", "12345abc90"])
def test_sync_ipi_bad_lengths(client, fake_db, ipi):
    resp = post(client, sync_body(ipi=ipi))
    assert resp.status_code == 422 and "IPI must be 9 to 11 digits." in resp.text
