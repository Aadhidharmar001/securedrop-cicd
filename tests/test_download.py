def test_download_file(client, db_session):
    file_content = b"SecureDrop test content"

    # Upload a file
    upload_response = client.post(
        "/files",
        files={
            "file": (
                "download-test.txt",
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

    upload_data = upload_response.json()
    token = upload_data["share_token"]

    # Download the file
    download_response = client.get(
        f"/share/{token}"
    )

    assert download_response.status_code == 200
    assert download_response.content == file_content

    # Verify download counter
    from app.models import File

    db_file = (
        db_session.query(File)
        .filter(File.token == token)
        .first()
    )

    assert db_file is not None
    assert db_file.download_count == 1