# widgets
import napari
from magicgui.widgets import Container, create_widget, Dialog, Label
import numpy as np
import time

class AddWatershedRegion(Container):
    def __init__(self, viewer: "napari.viewer.Viewer"):
        super().__init__()
        self._viewer = viewer

        self.has_done_update=False
        self.previous_state = None

        self.source_layer = create_widget(label="Source image", annotation="napari.layers.Labels")
        self.source_label = create_widget(label="Source label", annotation=int)
        self.target_layer = create_widget(label="Target image", annotation="napari.layers.Labels")
        self.target_label = create_widget(label="Target label", annotation=int)
        self.run_button = create_widget(label="Run", widget_type="PushButton")
        self.undo_button = create_widget(label="Undo", widget_type="PushButton")

        self.extend([
            self.source_layer,
            self.source_label,
            self.target_layer,
            self.target_label,
            self.run_button,
            self.undo_button
        ])

        self.pop_up_text = Label(value="")
        self.dialog_box = Dialog(widgets=[self.pop_up_text], layout="vertical")

        self.run_button.clicked.connect(self.update_image)
        self.undo_button.clicked.connect(self.undo)

    def update_image(self):
        source = self.source_layer.value
        target = self.target_layer.value
        if source is None or target is None:
            return

        source_label = self.source_label.value
        target_label = self.target_label.value

        if source_label != 0:
            self.previous_state = target.data.copy()
            target.data[source.data == source_label] = target_label
            target.refresh()
            self.has_done_update = True
            self.update_timestamp = time.time()

    def undo(self):
        if self.has_done_update:
            # this part is for the pop-up box message
            time_elapsed = time.time() - self.update_timestamp
            if time_elapsed < 10:
                res = True
            else:
                if time_elapsed > 60:
                    self.pop_up_text.value = f"Are you sure you want to undo an action from {round(time_elapsed / 60)} min ago?"
                else:
                    self.pop_up_text.value = f"Are you sure you want to undo an action from {round(time_elapsed)} sec ago?"
                self.dialog_box.show()
                res = self.dialog_box.exec()

            if res:
                source = self.source_layer.value
                target = self.target_layer.value
                if source is None or target is None:
                    return

                target.data = self.previous_state
                self.has_done_update = False # so you can only undo once
                target.refresh()