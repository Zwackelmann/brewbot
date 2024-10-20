import cv2


class Cam:
    def __init__(self, idx=0):
        self.idx = idx
        self.cap = cv2.VideoCapture(idx)
        self.image = None
        self.update()

    def update(self):
        ret, frame = self.cap.read()

        if not ret:
            self.image = None

        self.image = frame

    def release(self):
        self.cap.release()
