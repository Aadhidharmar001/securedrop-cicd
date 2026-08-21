from datetime import datetime, timedelta, timezone


def test_expired_share_link(client, db_session):
    file_content = b"Expired file"

    # Upload the file
    upload_response = client.post(
        "/files",
        files={
            "file": (
                "expired.txt",
                file_content,
                "text/plain",
            )
        },
        params={
            "expires_in_hours": 1,
            "max_downloads": 3,
        },
    )

    assert upload_response.status_code == 200

    data = upload_response.json()
    token = data["share_token"]

    # Manually expire the file in the test database
    from app.models import File

    db_file = (
        db_session.query(File)
        .filter(File.token == token)
        .first()
    )

    assert db_file is not None

    db_file.expires_at = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    )

    db_session.commit()

    # Try to download the expired file
    response = client.get(
        f"/share/{token}"
    )

    assert response.status_code == 410
    assert response.json()["detail"] == "Share link has expired."
    