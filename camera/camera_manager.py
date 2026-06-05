# ==============================
# FILE: camera/camera_manager.py
# ==============================

from camera import camera_state

from camera.webcam_capture import (
    open_camera,
    close_camera
)


class CameraManager:

    def start_camera(self):

        if camera_state.camera_running:

            print(
                "[CAMERA] Already Running"
            )

            return True

        cam = open_camera()

        if cam is None:

            print(
                "[CAMERA] Failed To Open"
            )

            return False

        camera_state.camera = cam

        camera_state.camera_running = True

        camera_state.camera_enabled = True

        print(
            "[CAMERA] Started"
        )

        return True

    def stop_camera(self):

        close_camera(
            camera_state.camera
        )

        camera_state.camera = None

        camera_state.latest_frame = None

        camera_state.camera_running = False

        camera_state.camera_enabled = False

        print(
            "[CAMERA] Stopped"
        )

    def restart_camera(self):

        self.stop_camera()

        return self.start_camera()

    def is_running(self):

        return (
            camera_state.camera_running
        )