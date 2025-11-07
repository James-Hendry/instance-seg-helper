# widgets
import napari
from magicgui.widgets import Container, create_widget, Dialog, Label
import numpy as np
import time
import numba

@numba.njit
def get_bbox(arr, idx):
    min_z, max_z = arr.shape[0], 0
    min_y, max_y = arr.shape[1], 0
    min_x, max_x = arr.shape[2], 0
    for z in range(arr.shape[0]):
        for y in range(arr.shape[1]):
            for x in range(arr.shape[2]):
                val = arr[z, y, x]
                if val == idx:
                    if z < min_z: min_z = z
                    if z > max_z: max_z = z
                    if y < min_y: min_y = y
                    if y > max_y: max_y = y
                    if x < min_x: min_x = x
                    if x > max_x: max_x = x
    
    return min_z, max_z,min_y, max_y,min_x, max_x


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


class PlateletVis3D(Container):
    def __init__(self, viewer: "napari.viewer.Viewer"):
        super().__init__()
        self._viewer = viewer

        self.source_layer = create_widget(label="Source image", annotation="napari.layers.Labels")
        self.source_label = create_widget(label="Source label", annotation=int)
        self.run_button = create_widget(label="Visualise", widget_type="PushButton")
        self.cancel_button = create_widget(label="Cancel Visualisation", widget_type="PushButton")

        self.extend([
            self.source_layer,
            self.source_label,
            self.run_button,
            self.cancel_button
        ])

        self.vis_active = False # this keeps track of whether we are currently visualising a platelet or not

        self.run_button.clicked.connect(self.vis_image_3D)
        self.cancel_button.clicked.connect(self.cancel_vis)

    def vis_image_3D(self):
        source = self.source_layer.value
        if source is None:
            return

        self.label = self.source_label.value

        # this is setting every layer to be non-visible and keeping track of the visibility state
        self.layer_vis_dict = {}
        for layer in self._viewer.layers:
            self.layer_vis_dict[layer.name] = layer.visible
            layer.visible = False

        # we make a smaller array of just the platelet labelled "label"
        idxs = np.where(source.data == self.label)
        min_z, max_z = idxs[0].min(), idxs[0].max()
        min_y, max_y = idxs[1].min(), idxs[1].max()
        min_x, max_x = idxs[2].min(), idxs[2].max()

        self.platelet_vis = source.data[min_z:max_z,min_y:max_y,min_x:max_x].copy()
        self.platelet_vis[self.platelet_vis != self.label] = 0  # get rid of anything else in the bounding box

        # add the platelet as a new layer and set the viewer to 3D
        self._viewer.add_labels(self.platelet_vis, name=f"object {self.label}", colormap=source.colormap)
        self._viewer.dims.ndisplay = 3
        # set the point the camera rotates around to the centre of the platelet instead of the centre of the whole instance segmentation
        self._viewer.camera.center = ((max_z - min_z)//2, (max_y - min_y)//2, (max_x - min_x)//2)
        self.vis_active = True

    def cancel_vis(self):
        if self.vis_active:
            self._viewer.dims.ndisplay = 2  # set the viewer back to 2D
            # remove the visualisation layer if it still exists
            if f"object {self.label}" in self._viewer.layers:
                self._viewer.layers.remove(f"object {self.label}")
            # set all the visibilities to what they used to be
            for layer_name in self.layer_vis_dict.keys():
                self._viewer.layers[layer_name].visible = self.layer_vis_dict[layer_name]
            # stop it trying to undo the visualisation again
            self.vis_active = False