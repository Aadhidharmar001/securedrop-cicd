from pathlib import Path


def test_delete_file(client, db_session):
    file_content = b"File to be revoked"

    # Upload file
    upload_response = client.post(
        "/files",
        files={
            "file": (
                "delete-test.txt",
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

    file_id = data["id"]
    token = data["share_token"]

    # Get database record
    from app.models import File

    db_file = (
        db_session.query(File)
        .filter(File.id == file_id)
        .first()
    )

    assert db_file is not None

    physical_path = Path(db_file.file_path)

    # Make sure physical file exists
    assert physical_path.exists()

    # Delete / revoke
    delete_response = client.delete(
        f"/files/{file_id}"
    )

    assert delete_response.status_code == 200

    assert delete_response.json() == {
        "message": "File revoked successfully.",
        "file_id": file_id,
    }

    # Physical file should be gone
    assert not physical_path.exists()

    # Share link should no longer work
    download_response = client.get(
        f"/share/{token}"
    )

    assert download_response.status_code == 404
    