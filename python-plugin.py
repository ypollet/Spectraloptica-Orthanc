# Spectraloptica - 3D Viewer on calibrated images - Orthanc Plugin

# Copyright (C) 2024 Yann Pollet, Royal Belgian Institute of Natural Sciences

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

# along with this program. If not, see <http://www.gnu.org/licenses/>.

import json
import numpy as np

import orthanc

##############################################################################
#                                                                            #
# ----------------------------- Spectraloptica ------------------------------#
#                                                                            #
##############################################################################


def compute_landmark(output, uri, **request):
    if request["method"] == "GET":
        instanceId = request["groups"][0]
        x = float(request["get"]["x"])
        y = float(request["get"]["y"])
        orthanc.LogWarning(f"Compute position of ({x};{y}) at {instanceId}")

        tags = json.loads(
            orthanc.RestApiGet(f"/instances/{instanceId}/simplified-tags")
        )

        pixel_spacing = [float(x) for x in tags["PixelSpacing"].split("\\")]

        position = {"x": x * pixel_spacing[0], "y": y * pixel_spacing[1]}

        output.AnswerBuffer(json.dumps(position, indent=3), "application/json")
    else:
        output.SendMethodNotAllowed("GET")


orthanc.RegisterRestCallback("/spectraloptica/(.*)/position", compute_landmark)


def get_response_image(instance) -> bytearray:
    return orthanc.RestApiGet(f"/instances/{instance}/content/7fe0-0010/1")


def get_response_thumbnail(instance) -> bytearray:
    return orthanc.RestApiGet(f"/instances/{instance}/attachments/thumbnail/data")


# send single image
def image(output, uri, **request):
    if request["method"] == "GET":
        instanceId = request["groups"][0]
        orthanc.LogWarning(f"Request full image of {instanceId}")
        try:
            instanceId = request["groups"][0]
            image_binary = get_response_image(instanceId)
            output.AnswerBuffer(image_binary, "image/jpeg")
        except Exception as error:
            orthanc.LogError(error)
    else:
        output.SendMethodNotAllowed("GET")


orthanc.RegisterRestCallback("/spectraloptica/(.*)/full-image", image)


# send single image
def thumbnail(output, uri, **request):
    if request["method"] == "GET":
        instanceId = request["groups"][0]
        orthanc.LogWarning(f"Request thumbnail image of {instanceId}")
        try:
            instanceId = request["groups"][0]
            image_binary = get_response_thumbnail(instanceId)
            output.AnswerBuffer(image_binary, "image/jpeg")
        except Exception as error:
            orthanc.LogError(error)
    else:
        output.SendMethodNotAllowed("GET")


orthanc.RegisterRestCallback("/spectraloptica/(.*)/thumbnail", thumbnail)


# send images
def images(output, uri, **request):
    if request["method"] == "GET":
        seriesId = request["groups"][0]
        orthanc.LogWarning(f"Request Spectraloptica camera images of {seriesId}")
        try:
            orthanc_dict = json.loads(
                orthanc.RestApiGet(f"/series/{seriesId}/instances-tags?simplify")
            )

            to_jsonify = {}
            encoded_images = []
            individual_images = dict()
            height = 0
            width = 0
            thumbnail = False
            for instance, tags in orthanc_dict.items():
                attachments = json.loads(
                    orthanc.RestApiGet(f"/instances/{instance}/attachments")
                )
                thumbnail = "thumbnail" in attachments
                try:
                    width = tags["Columns"]
                    height = tags["Rows"]
                    image = {
                        "name": instance,
                        "label": tags["UserContentLabel"],
                        "filter": {
                            "type": (
                                "VIS"
                                if not "ImagePathFilterPassThroughWavelength" in tags
                                or not tags["ImagePathFilterPassThroughWavelength"]
                                else (
                                    "UV"
                                    if float(
                                        tags["ImagePathFilterPassThroughWavelength"]
                                    )
                                    < 400
                                    else "IR"
                                )
                            ),
                            "description": "",
                        },
                        "wavelength": {
                            "type": (
                                "VIS"
                                if not "IlluminationWaveLength" in tags
                                or not tags["IlluminationWaveLength"]
                                or (
                                    float(tags["IlluminationWaveLength"]) >= 400
                                    and float(tags["IlluminationWaveLength"]) <= 700
                                )
                                else (
                                    "UV"
                                    if float(tags["IlluminationWaveLength"]) < 400
                                    else "IR"
                                )
                            ),
                            "value": (
                                float(tags["IlluminationWaveLength"])
                                if "IlluminationWaveLength" in tags
                                else None
                            ),
                        },
                    }
                    if "WAVELENGTH" in tags["ImageType"]:
                        encoded_images.append(image)
                    else:
                        individual_images[tags["UserContentLabel"]] = image
                except Exception as error:
                    print(error)
                    continue

            to_jsonify = {
                "spectralImages": sorted(
                    encoded_images, key=lambda image: image["wavelength"]["value"]
                ),
                "individualImages": individual_images,
                "size": {"height": height, "width": width},
                "thumbnails": thumbnail,
            }
            output.AnswerBuffer(json.dumps(to_jsonify), "application/json")
        except ValueError as e:
            orthanc.LogError(e)
    else:
        output.SendMethodNotAllowed("GET")


orthanc.RegisterRestCallback("/spectraloptica/(.*)/images", images)
extension = """
    const SPECTRALOPTICA_PLUGIN_SOP_CLASS_UID = '1.2.840.10008.5.1.4.1.1.77.1.4'
    $('#series').live('pagebeforeshow', function() {
      var seriesId = $.mobile.pageData.uuid;
    
      GetResource('/series/' + seriesId, function(series) {
        GetResource('/instances/' + series['Instances'][0] + '/tags?simplify', function(instance) {

          if (instance['SOPClassUID'] == SPECTRALOPTICA_PLUGIN_SOP_CLASS_UID) {
            $('#spectraloptica-button').remove();

            var b = $('<a>')
                .attr('id', 'spectraloptica-button')
                .attr('data-role', 'button')
                .attr('href', '#')
                .attr('data-icon', 'search')
                .attr('data-theme', 'e')
                .text('Spectraloptica Viewer')
                .button();

            b.insertAfter($('#series-info'));
            b.click(function(e) {
              window.open('../spectraloptica/ui/index.html?series=' + seriesId);
            })
          }
        });
      });
    });
    """
orthanc.ExtendOrthancExplorer(extension)
