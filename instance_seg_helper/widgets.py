# widgets
import napari
from magicgui import magicgui
from magicgui.widgets import Container, create_widget, PushButton
import numpy as np

class AddWatershedRegion(Container):
    def __init__(self, viewer: "napari.viewer.Viewer"):
        super().__init__()
        self._viewer = viewer

        self.source_image_layer_chooser = create_widget(
            label="Source image", annotation="napari.layers.Labels"
        )

        self.source_image_label = create_widget(
            label="Source label",
            annotation=int
        )

        self.target_image_layer_chooser = create_widget(
            label="Target image", annotation="napari.layers.Labels"
        )

        self.target_image_label = create_widget(
            label="Target label",
            annotation=int
        )

        self.execute_button = create_widget(
            label="Run",
            widget_type="PushButton"
        )

        self.undo_button = create_widget(
            label="Undo",
            widget_type="PushButton"
        )
        self.has_done_update=False
        self.previous_state = None

        # append into/extend the container with your widgets
        self.extend([
            self.source_image_layer_chooser,
            self.source_image_label,
            self.target_image_layer_chooser,
            self.target_image_label,
            self.execute_button,
            self.undo_button
        ])

        self.execute_button.clicked.connect(self.update_image)
        self.undo_button.clicked.connect(self.undo)

    def update_image(self):
        source_layer = self.source_image_layer_chooser.value
        if source_layer is None:
            return
        
        target_layer = self.target_image_layer_chooser.value
        if target_layer is None:
            return

        source = source_layer.data
        target = target_layer.data

        source_label = self.source_image_label.value
        target_label = self.target_image_label.value

        if source_label != 0:
            self.previous_state = target.copy()

            target[source == source_label] = target_label

            target_layer.refresh()
            self.has_done_update = True

    def undo(self):
        source_layer = self.source_image_layer_chooser.value
        target_layer = self.target_image_layer_chooser.value
        if source_layer is None or target_layer is None:
            return
        
        target_layer.data = self.previous_state
        self.has_done_update = False # so you can only undo once

        target_layer.refresh()