from storages.backends.s3boto3 import S3Boto3Storage  # noqa E402

MediaRootS3BotoStorage = lambda: S3Boto3Storage(location='media')  # noqa

