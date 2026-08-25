"""Cloud storage abstraction layer for model registry.

This module provides an abstract interface for cloud storage operations with
concrete implementations for major cloud providers (AWS S3, Azure Blob Storage,
Google Cloud Storage).
"""

import asyncio
import tarfile
import tempfile
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CloudStorageBackend(ABC):
    """Abstract base class for cloud storage providers.

    Provides a unified interface for cloud storage operations across different
    providers. Concrete implementations handle provider-specific details.
    """

    @abstractmethod
    async def upload_model(self, model_path: Path, model_id: str) -> str:
        """Upload model to cloud storage.

        Parameters
        ----------
        model_path : Path
            Local path to model directory
        model_id : str
            Unique identifier for the model

        Returns
        -------
        str
            Cloud storage URL for the uploaded model
        """
        pass

    @abstractmethod
    async def download_model(self, storage_url: str, local_path: Path) -> None:
        """Download model from cloud storage.

        Parameters
        ----------
        storage_url : str
            Cloud storage URL of the model
        local_path : Path
            Local path where model should be downloaded
        """
        pass

    @abstractmethod
    async def delete_model(self, storage_url: str) -> None:
        """Delete model from cloud storage.

        Parameters
        ----------
        storage_url : str
            Cloud storage URL of the model to delete
        """
        pass

    @abstractmethod
    async def generate_signed_url(self, storage_url: str, expires_in: int = 3600) -> str:
        """Generate time-limited access URL.

        Parameters
        ----------
        storage_url : str
            Cloud storage URL of the model
        expires_in : int, default=3600
            URL expiration time in seconds

        Returns
        -------
        str
            Signed URL for time-limited access
        """
        pass


class S3StorageBackend(CloudStorageBackend):
    """AWS S3 storage backend implementation."""

    def __init__(self, bucket_name: str, access_key: str, secret_key: str, region: str):
        """Initialize S3 storage backend.

        Parameters
        ----------
        bucket_name : str
            S3 bucket name
        access_key : str
            AWS access key
        secret_key : str
            AWS secret key
        region : str
            AWS region
        """
        self.bucket_name = bucket_name
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self._s3_client = None

    async def _get_s3_client(self):
        """Get or create S3 client instance."""
        if self._s3_client is None:
            # Import boto3 only when needed
            import boto3
            self._s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
        return self._s3_client

    def _parse_s3_url(self, storage_url: str) -> tuple[str, str]:
        """Parse S3 URL into bucket and key components.

        Parameters
        ----------
        storage_url : str
            S3 URL in format s3://bucket/key

        Returns
        -------
        tuple[str, str]
            Bucket name and key

        Raises
        ------
        ValueError
            If URL is not a valid S3 URL
        """
        if not storage_url.startswith('s3://'):
            raise ValueError(f"Invalid S3 URL: {storage_url}")

        # Remove s3:// prefix
        url_parts = storage_url[5:].split('/', 1)

        if len(url_parts) != 2 or not url_parts[0] or not url_parts[1]:
            raise ValueError(f"Invalid S3 URL: {storage_url}")

        return url_parts[0], url_parts[1]

    def _create_model_bundle(self, model_path: Path) -> Path:
        """Create compressed tar.gz bundle from model directory.

        Parameters
        ----------
        model_path : Path
            Path to model directory

        Returns
        -------
        Path
            Path to created tar.gz bundle
        """
        # Create temporary file for bundle
        bundle_fd, bundle_path = tempfile.mkstemp(suffix='.tar.gz')
        bundle_path = Path(bundle_path)

        try:
            with tarfile.open(bundle_path, 'w:gz') as tar:
                tar.add(model_path, arcname=model_path.name)

            return bundle_path
        finally:
            # Close file descriptor
            import os
            os.close(bundle_fd)

    async def upload_model(self, model_path: Path, model_id: str) -> str:
        """Upload model to S3 storage.

        Parameters
        ----------
        model_path : Path
            Local path to model directory
        model_id : str
            Unique identifier for the model

        Returns
        -------
        str
            S3 URL for the uploaded model
        """
        try:
            # Create compressed bundle
            bundle_path = self._create_model_bundle(model_path)

            # Generate S3 key
            s3_key = f"models/{model_id}/model_bundle.tar.gz"

            # Get S3 client
            s3_client = await self._get_s3_client()

            # Upload to S3
            await asyncio.get_event_loop().run_in_executor(
                None,
                s3_client.upload_file,
                str(bundle_path),
                self.bucket_name,
                s3_key
            )

            # Clean up temporary bundle
            bundle_path.unlink()

            # Return S3 URL
            storage_url = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"Model {model_id} uploaded to {storage_url}")

            return storage_url

        except Exception as e:
            logger.error(f"Failed to upload model {model_id} to S3: {str(e)}")
            raise

    async def download_model(self, storage_url: str, local_path: Path) -> None:
        """Download model from S3 storage.

        Parameters
        ----------
        storage_url : str
            S3 URL of the model
        local_path : Path
            Local path where model should be downloaded
        """
        try:
            # Parse S3 URL
            bucket, key = self._parse_s3_url(storage_url)

            # Create temporary file for download
            bundle_fd, bundle_path = tempfile.mkstemp(suffix='.tar.gz')
            bundle_path = Path(bundle_path)

            try:
                # Get S3 client
                s3_client = await self._get_s3_client()

                # Download from S3
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    s3_client.download_file,
                    bucket,
                    key,
                    str(bundle_path)
                )

                # Extract bundle to local path
                local_path.parent.mkdir(parents=True, exist_ok=True)

                with tarfile.open(bundle_path, 'r:gz') as tar:
                    tar.extractall(path=local_path.parent)

                logger.info(f"Model downloaded from {storage_url} to {local_path}")

            finally:
                # Clean up temporary bundle
                import os
                os.close(bundle_fd)
                if bundle_path.exists():
                    bundle_path.unlink()

        except Exception as e:
            logger.error(f"Failed to download model from {storage_url}: {str(e)}")
            raise

    async def delete_model(self, storage_url: str) -> None:
        """Delete model from S3 storage.

        Parameters
        ----------
        storage_url : str
            S3 URL of the model to delete
        """
        try:
            # Parse S3 URL
            bucket, key = self._parse_s3_url(storage_url)

            # Get S3 client
            s3_client = await self._get_s3_client()

            # Delete from S3
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: s3_client.delete_object(Bucket=bucket, Key=key)
            )

            logger.info(f"Model deleted from {storage_url}")

        except Exception as e:
            logger.error(f"Failed to delete model from {storage_url}: {str(e)}")
            raise

    async def generate_signed_url(self, storage_url: str, expires_in: int = 3600) -> str:
        """Generate signed URL for time-limited access.

        Parameters
        ----------
        storage_url : str
            S3 URL of the model
        expires_in : int, default=3600
            URL expiration time in seconds

        Returns
        -------
        str
            Signed URL for time-limited access
        """
        try:
            # Parse S3 URL
            bucket, key = self._parse_s3_url(storage_url)

            # Get S3 client
            s3_client = await self._get_s3_client()

            # Generate signed URL
            signed_url = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: s3_client.generate_presigned_url(
                    ClientMethod='get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=expires_in
                )
            )

            logger.debug(f"Generated signed URL for {storage_url} (expires in {expires_in}s)")

            return signed_url

        except ClientError as e:
            logger.error(f"S3 client error generating signed URL for {storage_url}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {storage_url}: {str(e)}")
            raise


class AzureBlobStorageBackend(CloudStorageBackend):
    """Azure Blob Storage backend implementation."""

    def __init__(self, container_name: str, connection_string: str):
        """Initialize Azure Blob Storage backend.

        Parameters
        ----------
        container_name : str
            Azure container name
        connection_string : str
            Azure storage connection string
        """
        self.container_name = container_name
        self.connection_string = connection_string
        self._blob_service_client = None

    async def _get_blob_client(self, blob_name: str):
        """Get or create blob client instance."""
        if self._blob_service_client is None:
            # Import azure-storage-blob only when needed
            from azure.storage.blob import BlobServiceClient
            self._blob_service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )

        return self._blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )

    def _parse_azure_url(self, storage_url: str) -> tuple[str, str]:
        """Parse Azure URL into container and blob name components.

        Parameters
        ----------
        storage_url : str
            Azure URL in format azure://container/blob_name

        Returns
        -------
        tuple[str, str]
            Container name and blob name

        Raises
        ------
        ValueError
            If URL is not a valid Azure URL
        """
        if not storage_url.startswith('azure://'):
            raise ValueError(f"Invalid Azure URL: {storage_url}")

        # Remove azure:// prefix
        url_parts = storage_url[8:].split('/', 1)

        if len(url_parts) != 2 or not url_parts[0] or not url_parts[1]:
            raise ValueError(f"Invalid Azure URL: {storage_url}")

        return url_parts[0], url_parts[1]

    def _create_model_bundle(self, model_path: Path) -> Path:
        """Create compressed tar.gz bundle from model directory.

        Parameters
        ----------
        model_path : Path
            Path to model directory

        Returns
        -------
        Path
            Path to created tar.gz bundle
        """
        # Create temporary file for bundle
        bundle_fd, bundle_path = tempfile.mkstemp(suffix='.tar.gz')
        bundle_path = Path(bundle_path)

        try:
            with tarfile.open(bundle_path, 'w:gz') as tar:
                tar.add(model_path, arcname=model_path.name)

            return bundle_path
        finally:
            # Close file descriptor
            import os
            os.close(bundle_fd)

    async def upload_model(self, model_path: Path, model_id: str) -> str:
        """Upload model to Azure Blob Storage.

        Parameters
        ----------
        model_path : Path
            Local path to model directory
        model_id : str
            Unique identifier for the model

        Returns
        -------
        str
            Azure URL for the uploaded model
        """
        try:
            # Create compressed bundle
            bundle_path = self._create_model_bundle(model_path)

            # Generate blob name
            blob_name = f"models/{model_id}/model_bundle.tar.gz"

            # Get blob client
            blob_client = await self._get_blob_client(blob_name)

            # Upload to Azure Blob Storage
            with open(bundle_path, 'rb') as data:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: blob_client.upload_blob(data, overwrite=True)
                )

            # Clean up temporary bundle
            bundle_path.unlink()

            # Return Azure URL
            storage_url = f"azure://{self.container_name}/{blob_name}"
            logger.info(f"Model {model_id} uploaded to {storage_url}")

            return storage_url

        except Exception as e:
            logger.error(f"Failed to upload model {model_id} to Azure: {str(e)}")
            raise

    async def download_model(self, storage_url: str, local_path: Path) -> None:
        """Download model from Azure Blob Storage.

        Parameters
        ----------
        storage_url : str
            Azure URL of the model
        local_path : Path
            Local path where model should be downloaded
        """
        try:
            # Parse Azure URL
            container, blob_name = self._parse_azure_url(storage_url)

            # Create temporary file for download
            bundle_fd, bundle_path = tempfile.mkstemp(suffix='.tar.gz')
            bundle_path = Path(bundle_path)

            try:
                # Get blob client
                blob_client = await self._get_blob_client(blob_name)

                # Download from Azure
                download_stream = await asyncio.get_event_loop().run_in_executor(
                    None,
                    blob_client.download_blob
                )

                with open(bundle_path, 'wb') as download_file:
                    download_file.write(download_stream.readall())

                # Extract bundle to local path
                local_path.parent.mkdir(parents=True, exist_ok=True)

                with tarfile.open(bundle_path, 'r:gz') as tar:
                    tar.extractall(path=local_path.parent)

                logger.info(f"Model downloaded from {storage_url} to {local_path}")

            finally:
                # Clean up temporary bundle
                import os
                os.close(bundle_fd)
                if bundle_path.exists():
                    bundle_path.unlink()

        except Exception as e:
            logger.error(f"Failed to download model from {storage_url}: {str(e)}")
            raise

    async def delete_model(self, storage_url: str) -> None:
        """Delete model from Azure Blob Storage.

        Parameters
        ----------
        storage_url : str
            Azure URL of the model to delete
        """
        try:
            # Parse Azure URL
            container, blob_name = self._parse_azure_url(storage_url)

            # Get blob client
            blob_client = await self._get_blob_client(blob_name)

            # Delete from Azure
            await asyncio.get_event_loop().run_in_executor(
                None,
                blob_client.delete_blob
            )

            logger.info(f"Model deleted from {storage_url}")

        except Exception as e:
            logger.error(f"Failed to delete model from {storage_url}: {str(e)}")
            raise

    async def generate_signed_url(self, storage_url: str, expires_in: int = 3600) -> str:
        """Generate signed URL for time-limited access.

        Parameters
        ----------
        storage_url : str
            Azure URL of the model
        expires_in : int, default=3600
            URL expiration time in seconds

        Returns
        -------
        str
            Signed URL for time-limited access
        """
        try:
            # Parse Azure URL
            container, blob_name = self._parse_azure_url(storage_url)

            # Generate signed URL
            from datetime import datetime, timedelta
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions

            # Extract account info from connection string
            account_name = None
            account_key = None
            for part in self.connection_string.split(';'):
                if part.startswith('AccountName='):
                    account_name = part.split('=')[1]
                elif part.startswith('AccountKey='):
                    account_key = part.split('=')[1]

            if not account_name or not account_key:
                raise ValueError("Could not extract account credentials from connection string")

            # Generate SAS token
            sas_token = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: generate_blob_sas(
                    account_name=account_name,
                    account_key=account_key,
                    container_name=container,
                    blob_name=blob_name,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(seconds=expires_in)
                )
            )

            # Construct signed URL
            signed_url = f"https://{account_name}.blob.core.windows.net/{container}/{blob_name}?{sas_token}"

            logger.debug(f"Generated signed URL for {storage_url} (expires in {expires_in}s)")

            return signed_url

        except Exception as e:
            logger.error(f"Failed to generate signed URL for {storage_url}: {str(e)}")
            raise


class GCSStorageBackend(CloudStorageBackend):
    """Google Cloud Storage backend implementation."""

    def __init__(self, bucket_name: str, project_id: str, credentials_path: str):
        """Initialize Google Cloud Storage backend.

        Parameters
        ----------
        bucket_name : str
            GCS bucket name
        project_id : str
            Google Cloud project ID
        credentials_path : str
            Path to service account credentials JSON file
        """
        self.bucket_name = bucket_name
        self.project_id = project_id
        self.credentials_path = credentials_path
        self._storage_client = None

    async def _get_storage_client(self):
        """Get or create storage client instance."""
        if self._storage_client is None:
            # Import google-cloud-storage only when needed
            from google.cloud import storage
            self._storage_client = storage.Client.from_service_account_json(
                self.credentials_path,
                project=self.project_id
            )
        return self._storage_client

    def _parse_gcs_url(self, storage_url: str) -> tuple[str, str]:
        """Parse GCS URL into bucket and object name components.

        Parameters
        ----------
        storage_url : str
            GCS URL in format gs://bucket/object_name

        Returns
        -------
        tuple[str, str]
            Bucket name and object name

        Raises
        ------
        ValueError
            If URL is not a valid GCS URL
        """
        if not storage_url.startswith('gs://'):
            raise ValueError(f"Invalid GCS URL: {storage_url}")

        # Remove gs:// prefix
        url_parts = storage_url[5:].split('/', 1)

        if len(url_parts) != 2 or not url_parts[0] or not url_parts[1]:
            raise ValueError(f"Invalid GCS URL: {storage_url}")

        return url_parts[0], url_parts[1]

    def _create_model_bundle(self, model_path: Path) -> Path:
        """Create compressed tar.gz bundle from model directory.

        Parameters
        ----------
        model_path : Path
            Path to model directory

        Returns
        -------
        Path
            Path to created tar.gz bundle
        """
        # Create temporary file for bundle
        bundle_fd, bundle_path = tempfile.mkstemp(suffix='.tar.gz')
        bundle_path = Path(bundle_path)

        try:
            with tarfile.open(bundle_path, 'w:gz') as tar:
                tar.add(model_path, arcname=model_path.name)

            return bundle_path
        finally:
            # Close file descriptor
            import os
            os.close(bundle_fd)

    async def upload_model(self, model_path: Path, model_id: str) -> str:
        """Upload model to Google Cloud Storage.

        Parameters
        ----------
        model_path : Path
            Local path to model directory
        model_id : str
            Unique identifier for the model

        Returns
        -------
        str
            GCS URL for the uploaded model
        """
        try:
            # Create compressed bundle
            bundle_path = self._create_model_bundle(model_path)

            # Generate object name
            object_name = f"models/{model_id}/model_bundle.tar.gz"

            # Get storage client
            storage_client = await self._get_storage_client()

            # Get bucket and blob
            bucket = storage_client.bucket(self.bucket_name)
            blob = bucket.blob(object_name)

            # Upload to GCS
            await asyncio.get_event_loop().run_in_executor(
                None,
                blob.upload_from_filename,
                str(bundle_path)
            )

            # Clean up temporary bundle
            bundle_path.unlink()

            # Return GCS URL
            storage_url = f"gs://{self.bucket_name}/{object_name}"
            logger.info(f"Model {model_id} uploaded to {storage_url}")

            return storage_url

        except Exception as e:
            logger.error(f"Failed to upload model {model_id} to GCS: {str(e)}")
            raise

    async def download_model(self, storage_url: str, local_path: Path) -> None:
        """Download model from Google Cloud Storage.

        Parameters
        ----------
        storage_url : str
            GCS URL of the model
        local_path : Path
            Local path where model should be downloaded
        """
        try:
            # Parse GCS URL
            bucket_name, object_name = self._parse_gcs_url(storage_url)

            # Create temporary file for download
            bundle_fd, bundle_path = tempfile.mkstemp(suffix='.tar.gz')
            bundle_path = Path(bundle_path)

            try:
                # Get storage client
                storage_client = await self._get_storage_client()

                # Get bucket and blob
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(object_name)

                # Download from GCS
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    blob.download_to_filename,
                    str(bundle_path)
                )

                # Extract bundle to local path
                local_path.parent.mkdir(parents=True, exist_ok=True)

                with tarfile.open(bundle_path, 'r:gz') as tar:
                    tar.extractall(path=local_path.parent)

                logger.info(f"Model downloaded from {storage_url} to {local_path}")

            finally:
                # Clean up temporary bundle
                import os
                os.close(bundle_fd)
                if bundle_path.exists():
                    bundle_path.unlink()

        except Exception as e:
            logger.error(f"Failed to download model from {storage_url}: {str(e)}")
            raise

    async def delete_model(self, storage_url: str) -> None:
        """Delete model from Google Cloud Storage.

        Parameters
        ----------
        storage_url : str
            GCS URL of the model to delete
        """
        try:
            # Parse GCS URL
            bucket_name, object_name = self._parse_gcs_url(storage_url)

            # Get storage client
            storage_client = await self._get_storage_client()

            # Get bucket and blob
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(object_name)

            # Delete from GCS
            await asyncio.get_event_loop().run_in_executor(
                None,
                blob.delete
            )

            logger.info(f"Model deleted from {storage_url}")

        except Exception as e:
            logger.error(f"Failed to delete model from {storage_url}: {str(e)}")
            raise

    async def generate_signed_url(self, storage_url: str, expires_in: int = 3600) -> str:
        """Generate signed URL for time-limited access.

        Parameters
        ----------
        storage_url : str
            GCS URL of the model
        expires_in : int, default=3600
            URL expiration time in seconds

        Returns
        -------
        str
            Signed URL for time-limited access
        """
        try:
            # Parse GCS URL
            bucket_name, object_name = self._parse_gcs_url(storage_url)

            # Get storage client
            storage_client = await self._get_storage_client()

            # Get bucket and blob
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(object_name)

            # Generate signed URL
            from datetime import datetime, timedelta

            signed_url = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.utcnow() + timedelta(seconds=expires_in),
                    method='GET'
                )
            )

            logger.debug(f"Generated signed URL for {storage_url} (expires in {expires_in}s)")

            return signed_url

        except Exception as e:
            logger.error(f"Failed to generate signed URL for {storage_url}: {str(e)}")
            raise


def create_storage_backend(config: Dict[str, Any]) -> CloudStorageBackend:
    """Factory function to create storage backend from configuration.

    Parameters
    ----------
    config : Dict[str, Any]
        Storage backend configuration

    Returns
    -------
    CloudStorageBackend
        Configured storage backend instance

    Raises
    ------
    ValueError
        If provider is not supported
    """
    provider = config.get('provider', '').lower()

    if provider == 's3':
        return S3StorageBackend(
            bucket_name=config['bucket_name'],
            access_key=config['access_key'],
            secret_key=config['secret_key'],
            region=config['region']
        )
    elif provider == 'azure':
        return AzureBlobStorageBackend(
            container_name=config['container_name'],
            connection_string=config['connection_string']
        )
    elif provider == 'gcs':
        return GCSStorageBackend(
            bucket_name=config['bucket_name'],
            project_id=config['project_id'],
            credentials_path=config['credentials_path']
        )
    else:
        raise ValueError(f"Unsupported storage provider: {provider}")
