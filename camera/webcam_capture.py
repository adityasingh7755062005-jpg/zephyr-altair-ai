# ==============================
# FILE: camera/webcam_capture.py
# ==============================

import cv2

FRAME_WIDTH = 320
FRAME_HEIGHT = 240


def open_camera():

    cam = cv2.VideoCapture(
        0,
        cv2.CAP_DSHOW
    )

    if not cam.isOpened():

        cam = cv2.VideoCapture(0)

    if not cam.isOpened():

        return None

    cam.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        FRAME_WIDTH
    )

    cam.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        FRAME_HEIGHT
    )

    cam.set(
        cv2.CAP_PROP_BUFFERSIZE,
        1
    )

    return cam


def close_camera(cam):

    try:

        if cam is not None:

            cam.release()

    except:
        pass

    try:

        cv2.destroyAllWindows()

    except:
        pass