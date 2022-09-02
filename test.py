import logging
import sys

import pycloudlib
from pycloudlib.cloud import ImageType

logging.basicConfig(level=logging.DEBUG)

gce = pycloudlib.GCE(tag="test")
for a in ["x86_64", "arm64"]:
    for r in ["xenial", "bionic", "focal", "jammy", "kinetic"]:
        try:
            gce.daily_image(r, image_type=ImageType.GENERIC, arch=a)
        except Exception as e:  # xenial has no arm image
            print(e)
    for r in ["xenial", "bionic", "focal", "jammy"]:
        try:
            gce.daily_image(r, image_type=ImageType.PRO, arch=a)
        except Exception as e:  # no pro images have an arm image
            print(e)
    for r in ["bionic", "focal"]:
        try:
            gce.daily_image(r, image_type=ImageType.PRO_FIPS, arch=a)
        except Exception as e:  # no pro images have an arm image
            print(e)
