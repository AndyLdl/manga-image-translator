import os
from PIL import Image
from abc import abstractmethod
from .rendering.gimp_render import gimp_render

from .utils import Context
from google.cloud import storage
from google.oauth2 import service_account
import io

# Google Cloud Storage setup
# credentials = service_account.Credentials.from_service_account_file(
#     '/Users/andy/ToolsProjectConfig/manga-translate-426423-37a3e09cad48.json')
# storage_client = storage.Client(credentials=credentials, project='manga-translate-426423')
storage_client = storage.Client()
bucket_name = 'manga-translate-result'
bucket = storage_client.get_bucket(bucket_name)

class FormatNotSupportedException(Exception):
    def __init__(self, fmt: str):
        super().__init__(f'Format {fmt} is not supported.')

OUTPUT_FORMATS = {}
def register_format(format_cls):
    for fmt in format_cls.SUPPORTED_FORMATS:
        if fmt in OUTPUT_FORMATS:
            raise Exception(f'Tried to register multiple ExportFormats for "{fmt}"')
        OUTPUT_FORMATS[fmt] = format_cls()
    return format_cls

class ExportFormat():
    SUPPORTED_FORMATS = []

    # Subclasses will be auto registered
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        register_format(cls)

    def save(self, result: Image.Image, dest: str, ctx: Context):
        self._save(result, dest, ctx)

    @abstractmethod
    def _save(self, result: Image.Image, dest: str, ctx: Context):
        pass

def save_result(result: Image.Image, dest: str, ctx: Context):
    # Determine the image format from the file extension or default to PNG
    _, ext = os.path.splitext(dest)
    image_format = ext[1:].upper() if ext[1:] else 'PNG'
    mime_type = f'image/{image_format.lower()}'

    # Save the image locally
    result.save(dest, format=image_format)
    print(f"Image saved locally at {dest}")

    # Save the image to a byte buffer for uploading to GCS
    img_byte_arr = io.BytesIO()
    result.save(img_byte_arr, format=image_format)
    img_byte_arr = img_byte_arr.getvalue()

    # Construct the GCS object name from the local path
    # Find the index of '/result/' and extract the path from that point onwards
    result_index = dest.find('/result/') + 1  # +1 to include the leading '/'
    if result_index > 0:
        gcs_object_name = dest[result_index:]
    else:
        gcs_object_name = os.path.basename(dest)  # Fallback to basename if '/result/' not found

    # Upload to Google Cloud Storage
    blob = bucket.blob(gcs_object_name)
    blob.upload_from_string(img_byte_arr, content_type=mime_type)
    print(f"Image uploaded to Google Cloud Storage at gs://{bucket_name}/{gcs_object_name}")


# -- Format Implementations

class ImageFormat(ExportFormat):
    SUPPORTED_FORMATS = ['png', 'webp']

    def _save(self, result: Image.Image, dest: str, ctx: Context):
        result.save(dest)

class JPGFormat(ExportFormat):
    SUPPORTED_FORMATS = ['jpg', 'jpeg']

    def _save(self, result: Image.Image, dest: str, ctx: Context):
        result = result.convert('RGB')
        # Certain versions of PIL only support JPEG but not JPG
        result.save(dest, quality=ctx.save_quality, format='JPEG')

class GIMPFormat(ExportFormat):
    SUPPORTED_FORMATS = ['xcf', 'psd', 'pdf']

    def _save(self, result: Image.Image, dest: str, ctx: Context):
        gimp_render(dest, ctx)

# class KraFormat(ExportFormat):
#     SUPPORTED_FORMATS = ['kra']

#     def _save(self, result: Image.Image, dest: str, ctx: Context):
#         ...

# class SvgFormat(TranslationExportFormat):
#     SUPPORTED_FORMATS = ['svg']

