from storages.backends.s3boto3 import S3Boto3Storage


class CustomMediaS3Storage(S3Boto3Storage):
    file_overwrite = False

    def _save(self, name, content):
        public_directories = [
            "cv_applications/",
            "cv_applications\\",
            "test_uploads/",
            "test_uploads\\",
            "company_logos/",
            "company_logos\\",
        ]
        if any(directory in name for directory in public_directories):
            self.default_acl = "public-read"
        else:
            self.default_acl = "private"

        return super()._save(name, content)
