from tkinter import ttk
import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
import cv2


default_digit_segment_boxes = [
    (( 0.25, 0.00, 0.50, 0.20), 1),
    (( 0.00, 0.15, 0.40, 0.30), 0),
    (( 0.60, 0.15, 0.40, 0.30), 0),
    (( 0.25, 0.40, 0.50, 0.22), 1),
    (( 0.00, 0.56, 0.40, 0.30), 0),
    (( 0.60, 0.56, 0.40, 0.30), 0),
    (( 0.25, 0.80, 0.50, 0.20), 1)
]


class BoxVar:
    def __init__(self, value):
        ((x1, y1), (x2, y2), (x3, y3), (x4, y4)) = value

        self.p1 = (tk.IntVar(value=x1), tk.IntVar(value=y1))
        self.p2 = (tk.IntVar(value=x2), tk.IntVar(value=y2))
        self.p3 = (tk.IntVar(value=x3), tk.IntVar(value=y3))
        self.p4 = (tk.IntVar(value=x4), tk.IntVar(value=y4))

    def get(self):
        return (
            (get_int_value(self.p1[0], 0), get_int_value(self.p1[1], 0)),
            (get_int_value(self.p2[0], 0), get_int_value(self.p2[1], 0)),
            (get_int_value(self.p3[0], 0), get_int_value(self.p3[1], 0)),
            (get_int_value(self.p4[0], 0), get_int_value(self.p4[1], 0))
        )


def get_int_value(var, default=None):
    try:
        return var.get()
    except tk.TclError:
        return default


class BoxConfigApp:
    def __init__(self, preview_image_dims=(512, 512), digit_image_dims=(256, 128), digit_segment_boxes=None, digit_box_colors=None):
        self.app_state = None

        self.preview_image_dims = preview_image_dims
        self.digit_image_dims = digit_image_dims

        if digit_segment_boxes is None:
            self.digit_segment_boxes = default_digit_segment_boxes
        else:
            self.digit_segment_boxes = digit_segment_boxes

        if digit_box_colors is None:
            self.digit_box_colors = [
                (255, 0, 0),
                (0, 0, 255)
            ]
        else:
            self.digit_box_colors = digit_box_colors

        self.digit_box_vars = []
        self.digit_box_inputs = []

        self.input_image_photo_image = None
        self.input_image_label = None

        self.distorted_digit_photo_images = []
        self.distorted_digit_labels = []

        self.root_widget = None

    def create_widgets(self, tk_root: tk.Tk, digit_boxes):
        self.digit_box_vars.extend([BoxVar(ib) for ib in digit_boxes])

        self.root_widget = ttk.Frame(tk_root, padding=10)
        self.root_widget.grid()

        tk.Label(self.root_widget, text="Digit 1").grid(row=0, column=0, columnspan=5)
        tk.Label(self.root_widget, text="P1:").grid(row=1, column=0)
        tk.Label(self.root_widget, text="P2:").grid(row=2, column=0)
        tk.Label(self.root_widget, text="P3:").grid(row=3, column=0)
        tk.Label(self.root_widget, text="P4:").grid(row=4, column=0)

        tk.Label(self.root_widget, text="Digit 2").grid(row=0, column=5, columnspan=5)
        tk.Label(self.root_widget, text="P1:").grid(row=1, column=5)
        tk.Label(self.root_widget, text="P2:").grid(row=2, column=5)
        tk.Label(self.root_widget, text="P3:").grid(row=3, column=5)
        tk.Label(self.root_widget, text="P4:").grid(row=4, column=5)

        self.digit_box_inputs.extend([DigitInput(self.root_widget, dv) for dv in self.digit_box_vars])

        self.digit_box_inputs[0].grid(row=1, column=1)
        self.digit_box_inputs[1].grid(row=1, column=6)

        init_image = Image.fromarray(np.ones((1, 1)) * 255)
        self.input_image_photo_image = ImageTk.PhotoImage(image=init_image)
        self.input_image_label = tk.Label(self.root_widget, image=self.input_image_photo_image)
        self.input_image_label.grid(row=5, column=0, columnspan=10)

        self.distorted_digit_photo_images.append(ImageTk.PhotoImage(image=init_image))
        self.distorted_digit_photo_images.append(ImageTk.PhotoImage(image=init_image))

        for idx in range(2):
            distorted_digit_label = tk.Label(self.root_widget, image=self.distorted_digit_photo_images[idx])
            distorted_digit_label.grid(row=6, column=idx*5, columnspan=5)
            self.distorted_digit_labels.append(distorted_digit_label)

        # Add a button to quit the GUI
        tk.Button(self.root_widget, text="Quit", command=tk_root.destroy).grid(row=7, column=0, columnspan=10)

    def update_input_image(self, input_image):
        input_image = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)
        input_image_dims = input_image.shape[:2]

        for box_input in self.digit_box_inputs:
            box_input.set_limits(input_image_dims)

        s = scale_factor(input_image_dims, self.preview_image_dims)
        mat_input_to_preview = np.array([[s, 0], [0, s]], dtype=np.float32)

        preview_image = cv2.resize(input_image, (int(input_image_dims[1]*s), int(input_image_dims[0]*s)), interpolation=cv2.INTER_LINEAR)
        preview_image = cv2.cvtColor(preview_image, cv2.COLOR_GRAY2BGR)

        for digit_idx in range(2):
            ((x1, y1), (x2, y2), (x3, y3), (x4, y4)) = self.digit_box_vars[digit_idx].get()
            color = self.digit_box_colors[digit_idx]

            src_points_input = np.array([[x1, y1], [x2, y2], [x3, y3], [x4, y4]], dtype="float32")
            src_points_preview = np.dot(src_points_input, mat_input_to_preview)

            cv2.line(preview_image, (int(src_points_preview[0][0]), int(src_points_preview[0][1])), (int(src_points_preview[1][0]), int(src_points_preview[1][1])), color)
            cv2.line(preview_image, (int(src_points_preview[1][0]), int(src_points_preview[1][1])), (int(src_points_preview[2][0]), int(src_points_preview[2][1])), color)
            cv2.line(preview_image, (int(src_points_preview[2][0]), int(src_points_preview[2][1])), (int(src_points_preview[3][0]), int(src_points_preview[3][1])), color)
            cv2.line(preview_image, (int(src_points_preview[3][0]), int(src_points_preview[3][1])), (int(src_points_preview[0][0]), int(src_points_preview[0][1])), color)

            self.input_image_photo_image = ImageTk.PhotoImage(image=Image.fromarray(preview_image))
            self.input_image_label.config(image=self.input_image_photo_image)

            dst_points = np.array([
                [0, 0],
                [self.digit_image_dims[1], 0],
                [self.digit_image_dims[1], self.digit_image_dims[0]],
                [0, self.digit_image_dims[0]]
            ], dtype="float32")

            mat = cv2.getPerspectiveTransform(src_points_input, dst_points)
            digit_image = cv2.warpPerspective(input_image, mat, (self.digit_image_dims[1], self.digit_image_dims[0]))
            digit_image_rgb = cv2.cvtColor(digit_image, cv2.COLOR_GRAY2BGR)

            for ((x_percent, y_percent, width_percent, height_percent), _) in self.digit_segment_boxes:
                (img_height, img_width) = digit_image_rgb.shape[:2]

                sb_x = int(img_width * x_percent)
                sb_y = int(img_height * y_percent)
                sb_width = int(img_width * width_percent)
                sb_height = int(img_height * height_percent)

                cv2.rectangle(digit_image_rgb, (sb_x, sb_y), (sb_x+sb_width, sb_y+sb_height), color)

            distorted_pil_image = Image.fromarray(digit_image_rgb)
            self.distorted_digit_photo_images[digit_idx] = ImageTk.PhotoImage(image=distorted_pil_image)
            self.distorted_digit_labels[digit_idx].config(image=self.distorted_digit_photo_images[digit_idx])


def scale_factor(dim1, dim2):
    return float(np.min(np.array(dim2) / np.array(dim1)))


class DigitInput:
    def __init__(self, parent, digit_var):
        self.p1_input = (
            tk.Spinbox(parent, textvariable=digit_var.p1[0], from_=0, to=10000, increment=1, width=8),
            tk.Spinbox(parent, textvariable=digit_var.p1[1], from_=0, to=10000, increment=1, width=8)
        )

        self.p2_input = (
            tk.Spinbox(parent, textvariable=digit_var.p2[0], from_=0, to=10000, increment=1, width=8),
            tk.Spinbox(parent, textvariable=digit_var.p2[1], from_=0, to=10000, increment=1, width=8)
        )

        self.p3_input = (
            tk.Spinbox(parent, textvariable=digit_var.p3[0], from_=0, to=10000, increment=1, width=8),
            tk.Spinbox(parent, textvariable=digit_var.p3[1], from_=0, to=10000, increment=1, width=8)
        )

        self.p4_input = (
            tk.Spinbox(parent, textvariable=digit_var.p4[0], from_=0, to=10000, increment=1, width=8),
            tk.Spinbox(parent, textvariable=digit_var.p4[1], from_=0, to=10000, increment=1, width=8)
        )

        self.p1_label = (
            tk.Label(parent, text="X"),
            tk.Label(parent, text="Y")
        )

        self.p2_label = (
            tk.Label(parent, text="X"),
            tk.Label(parent, text="Y")
        )

        self.p3_label = (
            tk.Label(parent, text="X"),
            tk.Label(parent, text="Y")
        )

        self.p4_label = (
            tk.Label(parent, text="X"),
            tk.Label(parent, text="Y")
        )

    def set_limits(self, dim):
        self.p1_input[0].config(from_=0, to=dim[1])
        self.p1_input[1].config(from_=0, to=dim[0])

        self.p2_input[0].config(from_=0, to=dim[1])
        self.p2_input[1].config(from_=0, to=dim[0])

        self.p3_input[0].config(from_=0, to=dim[1])
        self.p3_input[1].config(from_=0, to=dim[0])

        self.p4_input[0].config(from_=0, to=dim[1])
        self.p4_input[1].config(from_=0, to=dim[0])

    def grid(self, row, column):
        self.p1_label[0].grid(row=row+0, column=column+0)
        self.p1_input[0].grid(row=row+0, column=column+1)

        self.p1_label[1].grid(row=row+0, column=column+2)
        self.p1_input[1].grid(row=row+0, column=column+3)

        self.p2_label[0].grid(row=row+1, column=column+0)
        self.p2_input[0].grid(row=row+1, column=column+1)

        self.p2_label[1].grid(row=row+1, column=column+2)
        self.p2_input[1].grid(row=row+1, column=column+3)

        self.p3_label[0].grid(row=row+2, column=column+0)
        self.p3_input[0].grid(row=row+2, column=column+1)

        self.p3_label[1].grid(row=row+2, column=column+2)
        self.p3_input[1].grid(row=row+2, column=column+3)

        self.p4_label[0].grid(row=row+3, column=column+0)
        self.p4_input[0].grid(row=row+3, column=column+1)

        self.p4_label[1].grid(row=row+3, column=column+2)
        self.p4_input[1].grid(row=row+3, column=column+3)


def segments_to_number(segments):
    if segments ==   [True,  True,  True,  False, True,  True, True ]:
        return 0
    elif segments == [False, False, True,  False, False, True, False]:
        return 1
    elif segments == [True,  False, True,  True,  True,  False, True]:
        return 2
    elif segments == [True,  False, True,  True,  False, True, True ]:
        return 3
    elif segments == [False, True,  True,  True,  False, True, False]:
        return 4
    elif segments == [True,  True,  False, True, False, True, True ]:
        return 5
    elif segments == [True,  True,  False, True,  True,  True, True ]:
        return 6
    elif segments == [True,  False, True,  False, False, True, False]:
        return 7
    elif segments == [True,  True,  True,  True,  True,  True, True ]:
        return 8
    elif segments == [True,  True,  True,  True,  False, True, True ]:
        return 9
    elif segments == [False,  False,  False,  False,  False, False, False]:
        return "blank"
    else:
        return None


def find_active_segments(digit_img, boxes):
    return [bool(mean_gradient_std(project_img_pct(digit_img, proj), axis) > 7.0) for (proj, axis) in boxes]


def mean_gradient_std(img, mean_axis):
    m = np.mean(img, axis=mean_axis)
    return np.std(np.abs(np.diff(m)))


def project_img_pct(img, proj):
    (img_h, img_w) = img.shape[:2]
    proj_x, proj_y, proj_w, proj_h = proj

    x = int(img_w * proj_x)
    y = int(img_h * proj_y)
    w = int(img_w * proj_w)
    h = int(img_h * proj_h)

    return img[y:y+h, x:x+w]


def capture_digits(frame, digit_boxes, digit_image_dims, digit_segment_boxes, show_debug_windows=False):
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    digits = []
    idx = 0
    for ((x1, y1), (x2, y2), (x3, y3), (x4, y4)) in digit_boxes:
        src_points = np.array([
            [x1, y1],
            [x2, y2],
            [x3, y3],
            [x4, y4]
        ], dtype="float32")

        dst_points = np.array([
            [0, 0],
            [digit_image_dims[1], 0],
            [digit_image_dims[1], digit_image_dims[0]],
            [0, digit_image_dims[0]]
        ], dtype="float32")

        mat = cv2.getPerspectiveTransform(src_points, dst_points)
        digit_image = cv2.warpPerspective(frame, mat, (digit_image_dims[1], digit_image_dims[0]))
        active_segments = find_active_segments(digit_image, digit_segment_boxes)
        digits.append(segments_to_number(active_segments))

        if show_debug_windows:
            cv2.imshow(f"digit {idx}", digit_image)

        idx += 1

    if show_debug_windows:
        cv2.waitKey(1)

    return digits_to_num(digits)


def digits_to_num(digits):
    digits = [d for d in digits if d != "blank"]

    if len(digits) == 0:
        return None

    if any(d is None for d in digits):
        return None

    num = 0
    for i in range(len(digits)):
        exp = len(digits) - i - 1
        digit = digits[i]
        num += int(digit * pow(10, exp))

    return num
