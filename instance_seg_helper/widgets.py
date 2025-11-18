# widgets
import napari
from magicgui.widgets import Container, create_widget, Dialog, Label
import numpy as np
import time
import numba
from skimage.draw import polygon

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

        self.has_done_update = False
        self.previous_state = None
        self._coords_exist = False # safety so we don't try to access box coords before the box has been drawn
        self.box_mode = False

        # This is so the button text remains consistent everywhere (it is updated in multiple places)
        self.__selection_text = "shape selection mode"

        # this is just to get a default value for the slice slider if the layers have already been loaded
        if self._viewer.layers:
            maxval = self._viewer.layers[0].data.shape[0]

        self.source_layer = create_widget(label="Source image", annotation="napari.layers.Labels")
        self.source_label = create_widget(label="Source label", annotation=int)
        self.target_layer = create_widget(label="Target image", annotation="napari.layers.Labels")
        self.target_label = create_widget(label="Target label", annotation=int)
        self.slice_range = create_widget(label="Copy in range", widget_type="RangeSlider",
                                        options={"min": 0, "max": maxval, "value": (0, maxval)})
        self.run_button = create_widget(label="Run", widget_type="PushButton")
        self.undo_button = create_widget(label="Undo", widget_type="PushButton")
        self.box_mode_button = create_widget(label="Enable " + self.__selection_text, widget_type="PushButton")

        self.extend([
            self.source_layer,
            self.source_label,
            self.target_layer,
            self.target_label,
            self.slice_range,
            self.run_button,
            self.undo_button,
            self.box_mode_button
        ])

        self.pop_up_text = Label(value="")
        self.dialog_box = Dialog(widgets=[self.pop_up_text], layout="vertical")

        self.run_button.clicked.connect(self.update_image)
        self.undo_button.clicked.connect(self.undo)
        self.box_mode_button.clicked.connect(self._box_mode_toggle)
        # this updates the layer names in the dropdown menu when you change the active layer
        self._viewer.layers.selection.events.changed.connect(self.reset_choices)
        # this updates the maximum allowable value in the range slider to the number of slices in the active layer
        self._viewer.layers.selection.events.changed.connect(self._update_slider)


    def update_image(self):
        source = self.source_layer.value
        target = self.target_layer.value
        if source is None or target is None:
            return

        source_label = self.source_label.value
        target_label = self.target_label.value

        if source_label != 0:
            self.previous_state = target.data.copy()  # copy current state for undo function
            z0, z1 = self.slice_range.value

            # using shape mode (only copying regions based on a shape selection)
            if self.box_mode and self._coords_exist: # if box mode is active only copy the labels within the box
                self.prev_coords =  z0, z1, self.y0, self.y1, self.x0, self.x1 # save the current shape
                # copy label from source layer to target layer within a slice range within a polygon mask
                target.data[z0:z1, self.y0:self.y1, self.x0:self.x1][(source.data[z0:z1, self.y0:self.y1, self.x0:self.x1] == source_label) & self.mask] = target_label

            else: # if box_mode isn't active, copy the label globally
                self.prev_coords =  z0, z1, 0, source.data.shape[-2], 0, source.data.shape[-1] # save the current shape
                # copy label from source layer to target layer within a slice range
                target.data[z0:z1][source.data[z0:z1] == source_label] = target_label

            target.refresh()
            self.has_done_update = True
            self.update_timestamp = time.time()  # this is for the undo safety popup


    def undo(self):
        if self.has_done_update:  # only undo if there is something to undo
            # this part is for the pop-up box message
            time_elapsed = time.time() - self.update_timestamp
            if time_elapsed < 10: # no pop-up if it's been less than 10 sec
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


    def _box_mode_toggle(self):
        self.box_mode  = not self.box_mode  # swap the toggle
        if self.box_mode:
            self.box_mode_button.text = "Disable " + self.__selection_text

            # add a layer for the box
            if "Select region" not in self._viewer.layers:
                self.shapes_layer = self._viewer.add_shapes(
                    name="Select region",
                    face_color="#FFFFFFCC",
                    edge_color="cyan",
                    edge_width=4,
                    ndim=2,
                )
            else: # there might be some edge case where the layer already exists
                self.shapes_layer = self._viewer.layers["Select region"]

            self.shapes_layer.events.data.connect(self._on_shape_added)
        else:
            self.box_mode_button.text = "Enable " + self.__selection_text
            self.shapes_layer.events.data.disconnect(self._on_shape_added)
            if "Select region" in self._viewer.layers:
                self._viewer.layers.remove("Select region")


    def _update_slider(self):
        layer = self._viewer.layers.selection.active
        # if there is a layer and it's either an Image or a Labels layer
        if layer is not None and (isinstance(layer, napari.layers.Image) or isinstance(layer, napari.layers.Labels)):
            self.slice_range.max = layer.data.shape[0]


    def _on_shape_added(self, event):

        if event.action == "added": # this occurs when you finish drawing a shape 
            # delete any previous shape
            if len(self.shapes_layer.data) > 1:
                self.shapes_layer.selected_data = {0}
                try:
                    self.shapes_layer.remove_selected()
                    #self.shapes_layer.remove([0])  # this is what the line would be in napari >=0.6.5. The "selected_data" line above would also be removed
                except:
                    pass
                self.shapes_layer.refresh()  # needs to be refreshed to display correctly

            vertices = self.shapes_layer.data[0].astype(int)

            # position of the bounding box in original coordinates. +1 because index 10 requires an array of length >= 11
            self.y0 = vertices[:,0].min()
            self.y1 = vertices[:,0].max() + 1
            self.x0 = vertices[:,1].min()
            self.x1 = vertices[:,1].max() + 1

            # reposition so the coordinates are relative to the bounding box of the shape
            vertices[:,0] -= self.y0
            vertices[:,1] -= self.x0

            sub_shape = (self.y1-self.y0, self.x1-self.x0)
            # mask is a boolean array for indexing
            mask = np.zeros(sub_shape, dtype=bool)
            rr, cc = polygon(vertices[:,0], vertices[:,1], sub_shape)
            mask[rr,cc] = True

            self.mask = mask
            self._coords_exist = True


class PlateletVis3D(Container):
    def __init__(self, viewer: "napari.viewer.Viewer"):
        super().__init__()
        self._viewer = viewer

        self.source_layer = create_widget(label="Image", annotation="napari.layers.Labels")
        self.source_label = create_widget(label="Label", annotation=int)
        self.run_button = create_widget(label="Visualise in 3D", widget_type="PushButton")
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
        # this updates the layer names in the dropdown menu when you change the active layer
        self._viewer.layers.selection.events.changed.connect(self.reset_choices)

    def vis_image_3D(self):
        source = self.source_layer.value
        if source is None:
            return

        self.label = self.source_label.value
        # if a visualisation is already active, delete it. Otherwise turn off the other layers.
        if self.vis_active:
            if f"object {self.last_label}" in self._viewer.layers:
                self._viewer.layers.remove(f"object {self.last_label}")
        else:  # this is setting every layer to be non-visible and keeping track of the visibility state and the active layer
            self.active_layer = self._viewer.layers.selection.active
            self.layer_vis_dict = {}
            for layer in self._viewer.layers:
                self.layer_vis_dict[layer.name] = layer.visible
                layer.visible = False

        # we make a smaller array of just the platelet labelled "label"
        min_z, max_z,min_y, max_y,min_x, max_x = get_bbox(source.data, self.label)
        self.platelet_vis = source.data[min_z:max_z,min_y:max_y,min_x:max_x].copy()
        self.platelet_vis[self.platelet_vis != self.label] = 0  # get rid of anything else in the bounding box

        # add the platelet as a new layer and set the viewer to 3D
        self._viewer.add_labels(self.platelet_vis, name=f"object {self.label}", colormap=source.colormap)
        self._viewer.dims.ndisplay = 3
        # set the point the camera rotates around to the centre of the platelet instead of the centre of the whole instance segmentation
        self._viewer.camera.center = ((max_z - min_z)//2, (max_y - min_y)//2, (max_x - min_x)//2)
        self.vis_active = True
        self.last_label = self.label


    def cancel_vis(self):
        if self.vis_active:
            self._viewer.dims.ndisplay = 2  # set the viewer back to 2D
            # remove the visualisation layer if it still exists
            if f"object {self.label}" in self._viewer.layers:
                self._viewer.layers.remove(f"object {self.label}")
            # set all the visibilities to what they used to be
            for layer_name in self.layer_vis_dict.keys():
                self._viewer.layers[layer_name].visible = self.layer_vis_dict[layer_name]
            # set active layer to what it was before
            self._viewer.layers.selection.active = self.active_layer
            # stop it trying to undo the visualisation again
            self.vis_active = False