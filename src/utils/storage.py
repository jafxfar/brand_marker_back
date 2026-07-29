import logging
import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from src.core.config import get_settings
from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
settings = get_settings()


class StorageService:
    def __init__(self) -> None:
        self._s3 = None
        self._use_local = False
        self._local_dir = Path(settings.local_upload_dir)
        self._local_dir.mkdir(parents=True, exist_ok=True)

    def _get_s3(self):
        if self._s3 is not None:
            return self._s3
        try:
            import boto3
            from botocore.client import Config

            self._s3 = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,
                use_ssl=settings.s3_use_ssl,
                config=Config(signature_version="s3v4"),
            )
            self._s3.head_bucket(Bucket=settings.s3_bucket)
            return self._s3
        except Exception as exc:
            logger.warning("S3 unavailable, using local storage: %s", exc)
            self._use_local = True
            return None

    async def validate_upload(self, file: UploadFile) -> None:
        if not file.content_type or file.content_type not in settings.allowed_mime_types_list:
            raise ValidationError(f"File type not allowed: {file.content_type}")
        content = await file.read()
        await file.seek(0)
        if len(content) > settings.max_upload_bytes:
            raise ValidationError(f"File exceeds {settings.max_upload_size_mb}MB limit")

    async def upload(self, file: UploadFile, prefix: str = "uploads") -> tuple[str, str]:
        await self.validate_upload(file)
        ext = Path(file.filename or "file").suffix
        key = f"{prefix}/{uuid.uuid4().hex}{ext}"
        content = await file.read()
        content_type = file.content_type or "application/octet-stream"

        s3 = self._get_s3()
        if s3 and not self._use_local:
            s3.put_object(
                Bucket=settings.s3_bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
            url = f"{settings.s3_endpoint_url}/{settings.s3_bucket}/{key}"
            return key, url

        local_path = self._local_dir / key.replace("/", os.sep)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)
        return key, f"/uploads/{key}"


storage_service = StorageService()
