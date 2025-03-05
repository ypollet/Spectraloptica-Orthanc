# Spectraloptica - Orthanc Plugin

# Copyright (C) 2025 Yann Pollet, Royal Belgian Institute of Natural Sciences

#

# This program is free software: you can redistribute it and/or

# modify it under the terms of the GNU Affero General Public License

# as published by the Free Software Foundation, either version 3 of

# the License, or (at your option) any later version.

#

# This program is distributed in the hope that it will be useful, but

# WITHOUT ANY WARRANTY; without even the implied warranty of

# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU

# Affero General Public License for more details.

#

# You should have received a copy of the GNU Affero General Public License

# along with this program. If not, see <https://www.gnu.org/licenses/>.

from enum import Enum
from io import BytesIO
import PIL
import datetime
import pydicom
from pydicom.valuerep import VR
import glob
import json
import requests
import os


class Filter(Enum):
    VIS = None
    UV = 365
    IR = 800


orthanc_server = (
    "http://localhost:8042"  # "https://naturalheritage.africamuseum.be/Orthanc"
)

path_to_project = "data/sample-cropped"
SOURCE = f"{path_to_project}/*.jpg"
calib_file = f"{path_to_project}/spectral.json"
images = sorted(glob.glob(SOURCE))
i = 0


with open(calib_file, "rb") as f:
    spectral_dict = json.load(f)

study_uid = pydicom.uid.generate_uid()
series_uid = pydicom.uid.generate_uid()

if "thumbnails" in spectral_dict and spectral_dict["thumbnails"]:
    thumbnails_width = spectral_dict["thumbnails_width"]
    thumbnails_height = spectral_dict["thumbnails_height"]

now = datetime.datetime.now()

for image in spectral_dict["spectral"]:
    image_name = image["name"]
    image_path = f"{path_to_project}/{image_name}"
    camera = os.path.basename(image_path)
    print(camera)
    ds = pydicom.dataset.Dataset()
    ds.PatientName = "Tombe^Egyptienne^MS"
    ds.PatientID = "MS36587845"
    ds.PatientBirthDate = "20200914"
    ds.PatientSex = "O"

    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")

    ds.ImageType = ["ORIGINAL", "PRIMARY", "", "WAVELENGTH"]
    ds.UserContentLabel = camera
    ds.Laterality = "L"
    ds.LossyImageCompression = "01"
    ds.Modality = "XC"  # External-camera photography
    ds.SOPClassUID = pydicom.uid.VLPhotographicImageStorage
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = series_uid
    ds.StudyInstanceUID = study_uid
    ds.PixelSpacing = spectral_dict["PixelRatio"]
    ds.ImagePathFilterPassThroughWavelength = Filter[image["filter"]["type"]].value
    try:
        ds.IlluminationWaveLength = image["wavelength"]["value"]
    except Exception:
        pass
    ds.AccessionNumber = None
    ds.ReferringPhysicianName = None
    ds.SeriesNumber = None
    ds.StudyID = None
    ds.StudyDescription = "MS Tombe Egyptienne"
    ds.SeriesDescription = "Acquisition de la parois"
    ds.Manufacturer = None
    ds.AcquisitionContextSequence = None
    ds.InstanceNumber = i + 1

    # Basic encapsulation of color JPEG
    # httpss://pydicom.github.io/pydicom/stable/tutorials/pixel_data/compressing.html

    with open(image_path, "rb") as f:
        frames = [f.read()]
        ds.PixelData = pydicom.encaps.encapsulate(frames)

    with PIL.Image.open(image_path) as im:
        ds.Rows = im.size[1]
        ds.Columns = im.size[0]
        thumbnail_buffer = None
        if "thumbnails" in spectral_dict and spectral_dict["thumbnails"]:
            im.thumbnail((thumbnails_width, thumbnails_height))
            thumbnail_buffer = BytesIO()
            im.save(thumbnail_buffer, format="JPEG")

    ds.PlanarConfiguration = 0
    ds.SamplesPerPixel = 3
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PhotometricInterpretation = "RGB"

    ds["PixelData"].VR = "OB"  # always for encapsulated pixel data
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    meta = pydicom.dataset.FileMetaDataset()
    meta.TransferSyntaxUID = pydicom.uid.JPEGBaseline8Bit
    ds.file_meta = meta

    out: BytesIO = BytesIO()
    ds.save_as(out, write_like_original=False)

    response = requests.post(f"{orthanc_server}/instances", out.getvalue())

    response.raise_for_status()

    uuid = response.json()["ID"]
    series_uuid = response.json()["ParentSeries"]

    if thumbnail_buffer:
        r = requests.put(
            f"{orthanc_server}/instances/{uuid}/attachments/thumbnail",
            data=thumbnail_buffer.getvalue(),
        )
    i += 1

for image_label in spectral_dict["individualImages"]:
    print(image_label)
    image = spectral_dict["individualImages"][image_label]
    image_name = image["name"]
    image_path = f"{path_to_project}/{image_name}"
    ds = pydicom.dataset.Dataset()
    ds.PatientName = "Tombe^Egyptienne^MS"
    ds.PatientID = "MS36587845"
    ds.PatientBirthDate = "20200914"
    ds.PatientSex = "O"

    ds.StudyDate = now.strftime("%Y%m%d")
    ds.StudyTime = now.strftime("%H%M%S")

    ds.ImageType = ["ORIGINAL", "PRIMARY"]
    ds.UserContentLabel = image_label
    ds.Laterality = "L"
    ds.LossyImageCompression = "01"
    ds.Modality = "XC"  # External-camera photography
    ds.SOPClassUID = pydicom.uid.VLPhotographicImageStorage
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = series_uid
    ds.StudyInstanceUID = study_uid
    ds.PixelSpacing = spectral_dict["PixelRatio"]
    ds.ImagePathFilterPassThroughWavelength = Filter[image["filter"]["type"]].value
    try:
        ds.IlluminationWaveLength = image["wavelength"]["value"]
    except Exception:
        pass
    ds.AccessionNumber = None
    ds.ReferringPhysicianName = None
    ds.SeriesNumber = None
    ds.StudyID = None
    ds.StudyDescription = "MS Tombe Egyptienne"
    ds.SeriesDescription = "Acquisition de la parois"
    ds.Manufacturer = None
    ds.AcquisitionContextSequence = None
    ds.InstanceNumber = i + 1

    # Basic encapsulation of color JPEG
    # httpss://pydicom.github.io/pydicom/stable/tutorials/pixel_data/compressing.html

    with open(image_path, "rb") as f:
        frames = [f.read()]
        ds.PixelData = pydicom.encaps.encapsulate(frames)

    with PIL.Image.open(image_path) as im:
        ds.Rows = im.size[1]
        ds.Columns = im.size[0]
        thumbnail_buffer = None
        if "thumbnails" in spectral_dict and spectral_dict["thumbnails"]:
            im.thumbnail((thumbnails_width, thumbnails_height))
            thumbnail_buffer = BytesIO()
            im.save(thumbnail_buffer, format="JPEG")

    ds.PlanarConfiguration = 0
    ds.SamplesPerPixel = 3
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PhotometricInterpretation = "RGB"

    ds["PixelData"].VR = "OB"  # always for encapsulated pixel data
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    meta = pydicom.dataset.FileMetaDataset()
    meta.TransferSyntaxUID = pydicom.uid.JPEGBaseline8Bit
    ds.file_meta = meta

    out: BytesIO = BytesIO()
    ds.save_as(out, write_like_original=False)

    response = requests.post(f"{orthanc_server}/instances", out.getvalue())

    response.raise_for_status()

    uuid = response.json()["ID"]
    series_uuid = response.json()["ParentSeries"]

    if thumbnail_buffer:
        r = requests.put(
            f"{orthanc_server}/instances/{uuid}/attachments/thumbnail",
            data=thumbnail_buffer.getvalue(),
        )
    i += 1
