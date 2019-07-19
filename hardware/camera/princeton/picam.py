"""
Qudi module blah-blah
Picam should be installed (grab it from ftp://ftp.piacton.com/Public/Software/Official/PICam/).
"""

import os
import ctypes
import numpy as np
from core.module import Base, ConfigOption
from interface.camera_interface import CameraInterface


# ##########################################################################################################
# Camera Class
class Picam(Base, CameraInterface):
    """
    Main class that handles all connectivity with library and cameras.
    """

    _modtype = 'PicamCamera'
    _modclass = 'hardware'

    _exposure = 0.1

    def get_size(self):
        sensor = str(self.get_current_camera_id().sensor_name, 'utf-8')
        resolution = [int(s) for s in sensor.split() if s.isdigit()]
        return resolution

    def support_live_acquisition(self):
        pass

    def start_live_acquisition(self):
        pass

    def start_single_acquisition(self):
        pass

    def stop_acquisition(self):
        pass

    def get_acquired_data(self):
        """Returns only a first ROI in first frame.
            Reshape of returned array needed (at least for PyLoN BR 100) in case of image
            due to unknown reasons. (Different firmwares?)"""
        data = self.read_frames(1, 100000)[0][0]  # First ROI of first frame
        if np.shape(data)[1] == 1 or np.shape(data)[0] == 1:  # Return as is if the data is one dimensional
            return data
        else:
            return np.reshape(data, self.get_size()[::-1])

    def set_exposure(self, exposure):
        self.set_parameter("ExposureTime", exposure)
        self.send_configuration()

    def get_exposure(self):
        self.get_parameter("ExposureTime")

    def set_gain(self, gain):
        pass

    def get_gain(self):
        pass

    def get_ready_state(self):
        pass

    def get_name(self):
        return str(self.get_current_camera_id().sensor_name,'utf-8')

    def on_activate(self):
        # empty handle
        self.cam = None
        self.camIDs = None
        self.roisPtr = []
        self.pulsePtr = []
        self.modPtr = []
        self.acqThread = None
        self.totalFrameSize = 0
        self.load_library()
        self.connect()

    def on_deactivate(self):
        self.disconnect()
        self.unload_library()

    def load_library(self, path_to_lib=""):
        """
        Loads the picam library ('Picam.dll') and initializes it.

        :param str path_to_lib: Path to the dynamic link library (optional). If empty, the library is loaded using
        the path given by the environment variable *PicamRoot*, which is normally created by the PICam SDK installer.
        :returns: Prints the library version to stdout.
        """
        if path_to_lib == "":
            path_to_lib = os.path.join(os.environ["PicamRoot"], "Runtime")
        path_to_lib = os.path.join(path_to_lib, "Picam.dll")
        self.lib = ctypes.cdll.LoadLibrary(path_to_lib)

        is_connected = pibln()
        self.status(self.lib.Picam_IsLibraryInitialized(ptr(is_connected)))
        if not is_connected.value:
            self.status(self.lib.Picam_InitializeLibrary())

        print(self.get_library_version())

    def unload_library(self):
        """Call this function to release any resources and free the library."""
        # clean up all reserved memory that may be around
        for i in range(len(self.roisPtr)):
            self.status(self.lib.Picam_DestroyRois(self.roisPtr[i]))
        for i in range(len(self.pulsePtr)):
            self.status(self.lib.Picam_DestroyPulses(self.pulsePtr[i]))
        for i in range(len(self.modPtr)):
            self.status(self.lib.Picam_DestroyModulations(self.modPtr[i]))

        # disconnect from camera
        self.disconnect()

        if isinstance(self.camIDs, list):
            for c in self.camIDs:
                self.status(self.lib.Picam_DisconnectDemoCamera(ptr(c)))

        # free camID resources
        if self.camIDs is not None and not isinstance(self.camIDs, list):
            self.status(self.lib.Picam_DestroyCameraIDs(self.camIDs))
            self.camIDs = None

        # unload the library
        self.status(self.lib.Picam_UninitializeLibrary())
        print("Unloaded PICamSDK")

    # +++++++++++ CLASS FUNCTIONS ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def get_library_version(self):
        """Returns the PICam library version string."""
        major = piint()
        minor = piint()
        distr = piint()
        released = piint()
        self.status(self.lib.Picam_GetVersion(ptr(major), ptr(minor), ptr(distr), ptr(released)))
        return "PICam Library Version %d.%d.%d.%d" % (major.value, minor.value, distr.value, released.value)

    def get_available_cameras(self):  # TODO: fix bytestring outputs for Sensor_name and Serial number
        """
        Queries a list of IDs of cameras that are connected to the computer and prints
        some sensor information for each camera to stdout.
        If no physical camera is found, a demo camera is initialized - *for debug only*.
        """
        if self.camIDs is not None and not isinstance(self.camIDs, list):
            self.status(self.lib.Picam_DestroyCameraIDs(self.camIDs))
            self.camIDs = None

        # get connected cameras
        self.camIDs = ptr(PicamCameraID())
        id_count = piint()
        self.status(self.lib.Picam_GetAvailableCameraIDs(ptr(self.camIDs), ptr(id_count)))

        # if none are found, create a demo camera
        print("Available Cameras:")
        if id_count.value < 1:
            self.status(self.lib.Picam_DestroyCameraIDs(self.camIDs))

            model_array = ptr(piint())
            model_count = piint()
            self.status(self.lib.Picam_GetAvailableDemoCameraModels(ptr(model_array), ptr(model_count)))

            model_ID = PicamCameraID()
            serial = ctypes.c_char_p("Demo Cam 1".encode("utf-8"))
            self.status(self.lib.Picam_ConnectDemoCamera(model_array[0], serial, ptr(model_ID)))
            self.camIDs = [model_ID]

            self.status(self.lib.Picam_DestroyModels(model_array))

            print('  Model is ', PicamModelLookup[model_ID.model])
            print('  Computer interface is ', PicamComputerInterfaceLookup[model_ID.computer_interface])
            print('  Sensor_name is ', str(model_ID.sensor_name, 'utf-8'))
            print('  Serial number is', str(model_ID.serial_number, 'utf-8'))
            print('\n')
        else:
            for i in range(id_count.value):
                print('  Model is ', PicamModelLookup[self.camIDs[i].model])
                print('  Computer interface is ', PicamComputerInterfaceLookup[self.camIDs[i].computer_interface])
                print('  Sensor_name is ', self.camIDs[i].sensor_name)
                print('  Serial number is', self.camIDs[i].serial_number)
                print('\n')

    def get_last_error(self):
        """Returns the identifier associated with the last error (*str*)."""
        return PicamErrorLookup[self.err]

    def status(self, err):
        """Checks the return value of a picam function for any error code.
         If an error occurred, it prints the error message to stdout.

        :param int err: Error code returned by any picam function call.
        :returns: Error code (int) and if an error occurred, prints error message.
        """
        errstr = PicamErrorLookup[err]
        if errstr != "None":
            print("ERROR: ", errstr)
        #    raise AssertionError(errstr)
        self.err = err
        return err

    def connect(self, cam_id=None):
        """ Connect to camera.

        :param int cam_id: Number / index of camera to connect to (optional).
        It is an integer index into a list of valid camera IDs that has been retrieved by
        :py:func:`getAvailableCameras`.
        If camID is None, this functions connects to the first available camera (default).
        """
        if self.cam is not None:
            self.disconnect()
        if cam_id is None:
            self.cam = pivoid()
            self.status(self.lib.Picam_OpenFirstCamera(ptr(self.cam)))
        else:
            self.cam = pivoid()
            self.status(self.lib.Picam_OpenCamera(ptr(self.camIDs[cam_id]), ctypes.addressof(self.cam)))
        # invoke commit parameters to validate all parameters for acquisition
        self.send_configuration()

    def disconnect(self):
        """Disconnect current camera."""
        if self.cam is not None:
            self.status(self.lib.Picam_CloseCamera(self.cam))
        self.cam = None

    def get_current_camera_id(self):
        """Returns the current camera ID (:py:class:`PicamCameraID`)."""
        id = PicamCameraID()
        self.status(self.lib.Picam_GetCameraID(self.cam, ptr(id)))
        return id

    def print_available_parameters(self):
        """Prints an overview over the parameters to stdout that are available
        for the current camera and their limits.
        """
        parameter_array = ptr(piint())
        parameter_count = piint()
        self.lib.Picam_GetParameters(self.cam, ptr(parameter_array), ptr(parameter_count))

        for i in range(parameter_count.value):

            # read / write access
            access = piint()
            self.lib.Picam_GetParameterValueAccess(self.cam, parameter_array[i], ptr(access))
            readable = PicamValueAccessLookup[access.value]

            # constraints
            contype = piint()
            self.lib.Picam_GetParameterConstraintType(self.cam, parameter_array[i], ptr(contype))

            if PicamConstraintTypeLookup[contype.value] == "None":
                constraint = "ALL"

            elif PicamConstraintTypeLookup[contype.value] == "Range":

                c = ptr(PicamRangeConstraint())
                self.lib.Picam_GetParameterRangeConstraint(self.cam, parameter_array[i],
                                                           PicamConstraintCategory['Capable'], ptr(c))

                constraint = "from %f to %f in steps of %f" % (c[0].minimum, c[0].maximum, c[0].increment)

                self.lib.Picam_DestroyRangeConstraints(c)

            elif PicamConstraintTypeLookup[contype.value] == "Collection":

                c = ptr(PicamCollectionConstraint())
                self.lib.Picam_GetParameterCollectionConstraint(self.cam, parameter_array[i],
                                                                PicamConstraintCategory['Capable'], ptr(c))

                constraint = ""
                for j in range(c[0].values_count):
                    if constraint != "":
                        constraint += ", "
                    constraint += str(c[0].values_array[j])

                self.lib.Picam_DestroyCollectionConstraints(c)

            elif PicamConstraintTypeLookup[contype.value] == "Rois":
                constraint = "N.A."
            elif PicamConstraintTypeLookup[contype.value] == "Pulse":
                constraint = "N.A."
            elif PicamConstraintTypeLookup[contype.value] == "Modulations":
                constraint = "N.A."

            # print info
            print(PicamParameterLookup[parameter_array[i]])
            print(" value access:", readable)
            print(" allowed values:", constraint)
            print("\n")

        self.lib.Picam_DestroyParameters(parameter_array)

    # get / set parameters
    # name is a string specifying the parameter
    def get_parameter(self, name):
        """Reads and returns the value of the parameter with given name.
        If there is no parameter of this name, the function returns None and prints a warning.

        :param str name: Name of the parameter exactly as stated in the PICam SDK manual.
        :returns: Value of this parameter with data type corresponding to the type of parameter.
        """
        prm = PicamParameter[name]

        exists = pibln()
        self.lib.Picam_DoesParameterExist(self.cam, prm, ptr(exists))
        if not exists.value:
            print("Ignoring parameter", name)
            print("  Parameter does not exist for current camera!")
            return

        # get type of parameter
        type = piint()
        self.lib.Picam_GetParameterValueType(self.cam, prm, ptr(type))

        if type.value not in PicamValueTypeLookup:
            print("Not a valid parameter type enumeration:", type.value)
            print("Ignoring parameter", name)
            return 0

        if PicamValueTypeLookup[type.value] in ["Integer", "Boolean", "Enumeration"]:
            val = piint()

            # test whether we can read the value directly from hardware
            cr = pibln()
            self.lib.Picam_CanReadParameter(self.cam, prm, ptr(cr))
            if cr.value:
                if self.lib.Picam_ReadParameterIntegerValue(self.cam, prm, ptr(val)) == 0:
                    return val.value
            else:
                if self.lib.Picam_GetParameterIntegerValue(self.cam, prm, ptr(val)) == 0:
                    return val.value

        if PicamValueTypeLookup[type.value] == "LargeInteger":
            val = pi64s()
            if self.lib.Picam_GetParameterLargeIntegerValue(self.cam, prm, ptr(val)) == 0:
                return val.value

        if PicamValueTypeLookup[type.value] == "FloatingPoint":
            val = piflt()

            # NEW
            # test whether we can read the value directly from hardware
            cr = pibln()
            self.lib.Picam_CanReadParameter(self.cam, prm, ptr(cr))
            if cr.value:
                if self.lib.Picam_ReadParameterFloatingPointValue(self.cam, prm, ptr(val)) == 0:
                    return val.value
            else:
                if self.lib.Picam_GetParameterFloatingPointValue(self.cam, prm, ptr(val)) == 0:
                    return val.value

        if PicamValueTypeLookup[type.value] == "Rois":
            val = ptr(PicamRois())
            if self.lib.Picam_GetParameterRoisValue(self.cam, prm, ptr(val)) == 0:
                self.roisPtr.append(val)
                return val.contents

        if PicamValueTypeLookup[type.value] == "Pulse":
            val = ptr(PicamPulse())
            if self.lib.Picam_GetParameterPulseValue(self.cam, prm, ptr(val)) == 0:
                self.pulsePtr.append(val)
                return val.contents

        if PicamValueTypeLookup[type.value] == "Modulations":
            val = ptr(PicamModulations())
            if self.lib.Picam_GetParameterModulationsValue(self.cam, prm, ptr(val)) == 0:
                self.modPtr.append(val)
                return val.contents

        return None

    def set_parameter(self, name, value):
        """Set parameter. The value is automatically typecast to the correct data type corresponding to the type of parameter.

        .. note:: Setting a parameter with this function does not automatically change the configuration in the camera. In order to apply all changes, :py:func:`sendConfiguration` has to be called.

        :param str name: Name of the parameter exactly as stated in the PICam SDK manual.
        :param mixed value: New parameter value. If the parameter value cannot be changed, a warning is printed to stdout.
        """
        prm = PicamParameter[name]

        exists = pibln()
        self.lib.Picam_DoesParameterExist(self.cam, prm, ptr(exists))
        if not exists:
            print("Ignoring parameter", name)
            print("  Parameter does not exist for current camera!")
            return

        access = piint()
        self.lib.Picam_GetParameterValueAccess(self.cam, prm, ptr(access))
        if PicamValueAccessLookup[access.value] not in ["ReadWrite", "ReadWriteTrivial"]:
            print("Ignoring parameter", name)
            print("  Not allowed to overwrite parameter!")
            return
        if PicamValueAccessLookup[access.value] == "ReadWriteTrivial":
            print("WARNING: Parameter", name, " allows only one value!")

        # get type of parameter
        type = piint()
        self.lib.Picam_GetParameterValueType(self.cam, prm, ptr(type))

        if type.value not in PicamValueTypeLookup:
            print("Ignoring parameter", name)
            print("  Not a valid parameter type:", type.value)
            return

        if PicamValueTypeLookup[type.value] in ["Integer", "Boolean", "Enumeration"]:
            val = piint(value)
            self.status(self.lib.Picam_SetParameterIntegerValue(self.cam, prm, val))

        if PicamValueTypeLookup[type.value] == "LargeInteger":
            val = pi64s(value)
            self.status(self.lib.Picam_SetParameterLargeIntegerValue(self.cam, prm, val))

        if PicamValueTypeLookup[type.value] == "FloatingPoint":
            val = piflt(value)
            self.status(self.lib.Picam_SetParameterFloatingPointValue(self.cam, prm, val))

        if PicamValueTypeLookup[type.value] == "Rois":
            self.status(self.lib.Picam_SetParameterRoisValue(self.cam, prm, ptr(value)))

        if PicamValueTypeLookup[type.value] == "Pulse":
            self.status(self.lib.Picam_SetParameterPulseValue(self.cam, prm, ptr(value)))

        if PicamValueTypeLookup[type.value] == "Modulations":
            self.status(self.lib.Picam_SetParameterModulationsValue(self.cam, prm, ptr(value)))

        if self.err != PicamError["None"]:
            print("Ignoring parameter", name)
            print("  Could not change parameter. Keeping previous value:", self.get_parameter(name))

    def send_configuration(self):
        """This function has to be called once all configurations are done to apply settings to the camera.
        """
        failed = ptr(piint())
        failedCount = piint()

        self.status(self.lib.Picam_CommitParameters(self.cam, ptr(failed), ptr(failedCount)))

        if failedCount.value > 0:
            for i in range(failedCount.value):
                print("Could not set parameter", PicamParameterLookup[failed[i]])
        self.status(self.lib.Picam_DestroyParameters(failed))

        self.update_rois()

    def update_rois(self):
        """Internally used utility function to extract a list of pixel sizes of ROIs.
        """
        self.ROIS = []
        rois = self.get_parameter("Rois")
        self.totalFrameSize = 0
        offs = 0
        for i in range(rois.roi_count):
            w = int(np.ceil(float(rois.roi_array[i].width) / float(rois.roi_array[i].x_binning)))
            h = int(np.ceil(float(rois.roi_array[i].height) / float(rois.roi_array[i].y_binning)))
            self.ROIS.append((w, h, offs))
            offs = offs + w * h
        self.totalFrameSize = offs

    def set_roi(self, x0, w, xbin, y0, h, ybin):
        """Create a single region of interest (ROI).

        :param int x0: X-coordinate of upper left corner of ROI.
        :param int w: Width of ROI.
        :param int xbin: X-Binning, i.e. number of columns that are combined into one larger column (1 to w).
        :param int y0: Y-coordinate of upper left corner of ROI.
        :param int h: Height of ROI.
        :param int ybin: Y-Binning, i.e. number of rows that are combined into one larger row (1 to h).
        """
        r = PicamRoi(x0, w, xbin, y0, h, ybin)
        R = PicamRois(ptr(r), 1)
        self.set_parameter("Rois", R)
        self.update_rois()
        self.send_configuration()

    def add_roi(self, x0, w, xbin, y0, h, ybin):
        """Add a region-of-interest to the existing list of ROIs.

        .. important:: The ROIs should not overlap! However, this function does not check for overlapping ROIs!

        :param int x0: X-coordinate of upper left corner of ROI.
        :param int w: Width of ROI.
        :param int xbin: X-Binning, i.e. number of columns that are combined into one larger column (1 to w).
        :param int y0: Y-coordinate of upper left corner of ROI.
        :param int h: Height of ROI.
        :param int ybin: Y-Binning, i.e. number of rows that are combined into one larger row (1 to h).
        """
        # read existing rois
        R = self.get_parameter("Rois")
        r0 = (PicamRoi * (R.roi_count + 1))()
        for i in range(R.roi_count):
            r0[i] = R.roi_array[i]
        # add new roi
        r0[-1] = PicamRoi(x0, w, xbin, y0, h, ybin)
        # write back to camera
        R1 = PicamRois(ptr(r0[0]), len(r0))
        self.set_parameter("Rois", R1)
        self.update_rois()

    def read_frames(self, n=1, timeout=100):
        """This function acquires N frames using Picam_Acquire. It waits till all frames have been collected before it returns.

        :param int n: Number of frames to collect (>= 1, default=1). This number is essentially limited by the available memory.
        :param float timeout: Maximum wait time between frames in milliseconds (default=100). This parameter is important when using external triggering.
        :returns: List of acquired frames.
        """
        available = PicamAvailableData()
        errors = piint()

        running = pibln()
        self.lib.Picam_IsAcquisitionRunning(self.cam, ptr(running))
        if running.value:
            print("ERROR: acquisition still running")
            return []

        # start acquisition
        self.status(self.lib.Picam_Acquire(self.cam, pi64s(n), piint(timeout), ptr(available), ptr(errors)))

        # return data as numpy array
        if available.readout_count >= n:
            if len(self.ROIS) == 1:
                return self.get_buffer(available.initial_readout, available.readout_count)[0:n]
            else:
                return self.get_buffer(available.initial_readout, available.readout_count)[:][0:n]
        return []

    def get_buffer(self, address, size):
        """This is an internally used function to convert the readout buffer into a sequence of numpy arrays.
        It reads all available data at once into a numpy buffer and reformats data to a usable format.

        :param long address: Memory address where the readout buffer is stored.
        :param int size: Number of readouts available in the readout buffer.
        :returns: List of ROIS; for each ROI, array of readouts; each readout is a NxM array.
        """
        # get number of pixels contained in a single readout and a single frame
        # parameters are bytes, a pixel in resulting array is 2 bytes
        readoutstride = self.get_parameter("ReadoutStride") // 2
        framestride = self.get_parameter("FrameStride") // 2
        frames = self.get_parameter("FramesPerReadout")

        # create a pointer to data
        dataArrayType = pi16u * readoutstride * size
        dataArrayPointerType = ctypes.POINTER(dataArrayType)
        dataPointer = ctypes.cast(address, dataArrayPointerType)

        # create a numpy array from the buffer
        data = np.frombuffer(dataPointer.contents, dtype='uint16')

        # cast it into a usable format - [frames][data]
        data = ((data.reshape(size, readoutstride)[:, :frames * framestride]).reshape(size, frames, framestride)[:, :, :self.totalFrameSize]).reshape(size * frames, self.totalFrameSize).astype(float)

        # if there is just a single ROI, we are done
        if len(self.ROIS) == 1:
            return [data.reshape(size * frames, self.ROIS[0][0], self.ROIS[0][1])]

        # otherwise, iterate through rois and add to output list (has to be list due to possibly different sizes)
        out = []
        for i, r in enumerate(self.ROIS):
            out.append(data[:, r[2]:r[0] * r[1] + r[2]])
        return out


# ##########################################################################################################
# helper functions

def ptr(x):
    """
    Shortcut to return a ctypes.pointer to object x.
    """
    return ctypes.pointer(x)

# Here goes content from pitypes.py
# +++++++ simple data types +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# data types - use these for communication with the picam library!
# to get the value, use XX.value
piint = ctypes.c_int
piflt = ctypes.c_double     # !!!! native floating point is actually double; ctypes.c_float
pibln = ctypes.c_bool
pichar = ctypes.c_char
pibyte = ctypes.c_byte
pibool = ctypes.c_bool
pi8s = ctypes.c_int8
pi8u = ctypes.c_uint8
pi16s = ctypes.c_int16
pi16u = ctypes.c_uint16
pi32s = ctypes.c_int32
pi32u = ctypes.c_uint32
pi64s = ctypes.c_int64
pi64u = ctypes.c_uint64
pivoid = ctypes.c_void_p

# +++++++ enumerations +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# each enumeration has a lookup table of the same name XXLookup which accepts the integer
# value as key and gives the string name as value
PicamError = {
    # Success
    "None": 0,
    # General Errors
    "UnexpectedError": 4,
    "UnexpectedNullPointer": 3,
    "InvalidPointer": 35,
    "InvalidCount": 39,
    "EnumerationValueNotDefined": 17,
    "InvalidOperation": 42,
    "OperationCanceled": 43,
    # Library Initialization Errors
    "LibraryNotInitialized": 1,
    "LibraryAlreadyInitialized": 5,
    # General String Handling Errors
    "InvalidEnumeratedType": 16,
    # Camera/Accessory Plug 'n Play Discovery Errors
    "NotDiscoveringCameras": 18,
    "AlreadyDiscoveringCameras": 19,
    "NotDiscoveringAccessories": 48,
    "AlreadyDiscoveringAccessories": 49,
    # Camera/Accessory Access Errors
    "NoCamerasAvailable": 34,
    "CameraAlreadyOpened": 7,
    "InvalidCameraID": 8,
    "NoAccessoriesAvailable": 45,
    "AccessoryAlreadyOpened": 46,
    "InvalidAccessoryID": 47,
    "InvalidHandle": 9,
    "DeviceCommunicationFailed": 15,
    "DeviceDisconnected": 23,
    "DeviceOpenElsewhere": 24,
    # Demo Camera Errors
    "InvalidDemoModel": 6,
    "InvalidDemoSerialNumber": 21,
    "DemoAlreadyConnected": 22,
    "DemoNotSupported": 40,
    # Camera/Accessory Parameter Access Errors
    "ParameterHasInvalidValueType": 11,
    "ParameterHasInvalidConstraintType": 13,
    "ParameterDoesNotExist": 12,
    "ParameterValueIsReadOnly": 10,
    "InvalidParameterValue": 2,
    "InvalidConstraintCategory": 38,
    "ParameterValueIsIrrelevant": 14,
    "ParameterIsNotOnlineable": 25,
    "ParameterIsNotReadable": 26,
    "ParameterIsNotWaitableStatus": 50,
    "InvalidWaitableStatusParameterTimeOut": 51,
    # Camera Data Acquisition Errors
    "InvalidParameterValues": 28,
    "ParametersNotCommitted": 29,
    "InvalidAcquisitionBuffer": 30,
    "InvalidReadoutCount": 36,
    "InvalidReadoutTimeOut": 37,
    "InsufficientMemory": 31,
    "AcquisitionInProgress": 20,
    "AcquisitionNotInProgress": 27,
    "TimeOutOccurred": 32,
    "AcquisitionUpdatedHandlerRegistered": 33,
    "NondestructiveReadoutEnabled": 41,
    "ShutterOverheated": 52,
    "CenterWavelengthFaulted": 54,
    "CameraFaulted": 53
}
PicamErrorLookup = dict(zip(PicamError.values(), PicamError.keys()))

PicamEnumeratedType = {
    # Function Return Error Codes
    "Error": 1,
    # General String Handling
    "EnumeratedType": 29,
    # Camera/Accessory Identification
    "Model": 2,
    "ComputerInterface": 3,
    # Camera/Accessory Plug 'n Play Discovery
    "DiscoveryAction": 26,
    # Camera/Accessory Access
    "HandleType": 27,
    # Camera/Accessory Parameters
    "ValueType": 4,
    "ConstraintType": 5,
    "Parameter": 6,
    # Camera/Accessory Parameter Values - Enumerated Types
    "ActiveShutter": 53,
    "AdcAnalogGain": 7,
    "AdcQuality": 8,
    "CcdCharacteristicsMask": 9,
    "CenterWavelengthStatus": 51,
    "CoolingFanStatus": 56,
    "EMIccdGainControlMode": 42,
    "GateTrackingMask": 36,
    "GatingMode": 34,
    "GatingSpeed": 38,
    "GratingCoating": 48,
    "GratingType": 49,
    "IntensifierOptionsMask": 35,
    "IntensifierStatus": 33,
    "LaserOutputMode": 45,
    "LaserStatus": 54,
    "LightSource": 46,
    "LightSourceStatus": 47,
    "ModulationTrackingMask": 41,
    "OrientationMask": 10,
    "OutputSignal": 11,
    "PhosphorType": 39,
    "PhotocathodeSensitivity": 40,
    "PhotonDetectionMode": 43,
    "PixelFormat": 12,
    "ReadoutControlMode": 13,
    "SensorTemperatureStatus": 14,
    "SensorType": 15,
    "ShutterStatus": 52,
    "ShutterTimingMode": 16,
    "ShutterType": 50,
    "TimeStampsMask": 17,
    "TriggerCoupling": 30,
    "TriggerDetermination": 18,
    "TriggerResponse": 19,
    "TriggerSource": 31,
    "TriggerStatus": 55,
    "TriggerTermination": 32,
    "VacuumStatus": 57,
    # Camera/Accessory Parameter Information - Value Access
    "ValueAccess": 20,
    # Camera/Accessory Parameter Information - Dynamics
    "DynamicsMask": 28,
    # Camera/Accessory Parameter Constraints - Enumerated Types
    "ConstraintScope": 21,
    "ConstraintSeverity": 22,
    "ConstraintCategory": 23,
    # Camera Parameter Constraints - Regions of Interest
    "RoisConstraintRulesMask": 24,
    # Camera Acquisition Control
    "AcquisitionErrorsMask": 25,
    # Camera Acquisition Notification
    "AcquisitionState": 37,
    "AcquisitionStateErrorsMask": 44
}
PicamEnumeratedTypeLookup = dict(zip(PicamEnumeratedType.values(), PicamEnumeratedType.keys()))

PicamModel = {
    # PI-MTESeries(1419)
    "PIMteSeries": 1400,
    # PI-MTE1024Series
    "PIMte1024Series": 1401,
    "PIMte1024F": 1402,
    "PIMte1024B": 1403,
    "PIMte1024BR": 1405,
    "PIMte1024BUV": 1404,
    # PI-MTE1024FTSeries
    "PIMte1024FTSeries": 1406,
    "PIMte1024FT": 1407,
    "PIMte1024BFT": 1408,
    # PI-MTE1300Series
    "PIMte1300Series": 1412,
    "PIMte1300B": 1413,
    "PIMte1300R": 1414,
    "PIMte1300BR": 1415,
    # PI-MTE2048Series
    "PIMte2048Series": 1416,
    "PIMte2048B": 1417,
    "PIMte2048BR": 1418,
    # PI-MTE2KSeries
    "PIMte2KSeries": 1409,
    "PIMte2KB": 1410,
    "PIMte2KBUV": 1411,
    # PI-MTE3Series(2005)
    "PIMte3Series": 2000,
    # PI-MTE32048Series
    "PIMte32048Series": 2001,
    "PIMte32048B": 2002,
    # PIXISSeries(76)
    "PixisSeries": 0,
    # PIXIS100Series
    "Pixis100Series": 1,
    "Pixis100F": 2,
    "Pixis100B": 6,
    "Pixis100R": 3,
    "Pixis100C": 4,
    "Pixis100BR": 5,
    "Pixis100BExcelon": 54,
    "Pixis100BRExcelon": 55,
    "PixisXO100B": 7,
    "PixisXO100BR": 8,
    "PixisXB100B": 68,
    "PixisXB100BR": 69,
    # PIXIS256Series
    "Pixis256Series": 26,
    "Pixis256F": 27,
    "Pixis256B": 29,
    "Pixis256E": 28,
    "Pixis256BR": 30,
    "PixisXB256BR": 31,
    # PIXIS400Series
    "Pixis400Series": 37,
    "Pixis400F": 38,
    "Pixis400B": 40,
    "Pixis400R": 39,
    "Pixis400BR": 41,
    "Pixis400BExcelon": 56,
    "Pixis400BRExcelon": 57,
    "PixisXO400B": 42,
    "PixisXB400BR": 70,
    # PIXIS512Series
    "Pixis512Series": 43,
    "Pixis512F": 44,
    "Pixis512B": 45,
    "Pixis512BUV": 46,
    "Pixis512BExcelon": 58,
    "PixisXO512F": 49,
    "PixisXO512B": 50,
    "PixisXF512F": 48,
    "PixisXF512B": 47,
    # PIXIS1024Series
    "Pixis1024Series": 9,
    "Pixis1024F": 10,
    "Pixis1024B": 11,
    "Pixis1024BR": 13,
    "Pixis1024BUV": 12,
    "Pixis1024BExcelon": 59,
    "Pixis1024BRExcelon": 60,
    "PixisXO1024F": 16,
    "PixisXO1024B": 14,
    "PixisXO1024BR": 15,
    "PixisXF1024F": 17,
    "PixisXF1024B": 18,
    "PixisXB1024BR": 71,
    # PIXIS1300Series
    "Pixis1300Series": 51,
    "Pixis1300F": 52,
    "Pixis1300F_2": 75,
    "Pixis1300B": 53,
    "Pixis1300BR": 73,
    "Pixis1300BExcelon": 61,
    "Pixis1300BRExcelon": 62,
    "PixisXO1300B": 65,
    "PixisXF1300B": 66,
    "PixisXB1300R": 72,
    # PIXIS2048Series
    "Pixis2048Series": 20,
    "Pixis2048F": 21,
    "Pixis2048B": 22,
    "Pixis2048BR": 67,
    "Pixis2048BExcelon": 63,
    "Pixis2048BRExcelon": 74,
    "PixisXO2048B": 23,
    "PixisXF2048F": 25,
    "PixisXF2048B": 24,
    # PIXIS2KSeries
    "Pixis2KSeries": 32,
    "Pixis2KF": 33,
    "Pixis2KB": 34,
    "Pixis2KBUV": 36,
    "Pixis2KBExcelon": 64,
    "PixisXO2KB": 35,
    # Quad-ROSeries(104)
    "QuadroSeries": 100,
    "Quadro4096": 101,
    "Quadro4096_2": 103,
    "Quadro4320": 102,
    # ProEMSeries(214)
    "ProEMSeries": 200,
    # ProEM512Series
    "ProEM512Series": 203,
    "ProEM512B": 201,
    "ProEM512BK": 205,
    "ProEM512BExcelon": 204,
    "ProEM512BKExcelon": 206,
    # ProEM1024Series
    "ProEM1024Series": 207,
    "ProEM1024B": 202,
    "ProEM1024BExcelon": 208,
    # ProEM1600Series
    "ProEM1600Series": 209,
    "ProEM1600xx2B": 212,
    "ProEM1600xx2BExcelon": 210,
    "ProEM1600xx4B": 213,
    "ProEM1600xx4BExcelon": 211,
    # ProEM+Series(614)
    "ProEMPlusSeries": 600,
    # ProEM+512Series
    "ProEMPlus512Series": 603,
    "ProEMPlus512B": 601,
    "ProEMPlus512BK": 605,
    "ProEMPlus512BExcelon": 604,
    "ProEMPlus512BKExcelon": 606,
    # ProEM+1024Series
    "ProEMPlus1024Series": 607,
    "ProEMPlus1024B": 602,
    "ProEMPlus1024BExcelon": 608,
    # ProEM+1600Series
    "ProEMPlus1600Series": 609,
    "ProEMPlus1600xx2B": 612,
    "ProEMPlus1600xx2BExcelon": 610,
    "ProEMPlus1600xx4B": 613,
    "ProEMPlus1600xx4BExcelon": 611,
    # ProEM-HSSeries(1218)
    "ProEMHSSeries": 1200,
    # ProEM-HS512Series
    "ProEMHS512Series": 1201,
    "ProEMHS512B": 1202,
    "ProEMHS512BK": 1207,
    "ProEMHS512BExcelon": 1203,
    "ProEMHS512BKExcelon": 1208,
    "ProEMHS512B_2": 1216,
    "ProEMHS512BExcelon_2": 1217,
    # ProEM-HS1024Series
    "ProEMHS1024Series": 1204,
    "ProEMHS1024B": 1205,
    "ProEMHS1024BExcelon": 1206,
    "ProEMHS1024B_2": 1212,
    "ProEMHS1024BExcelon_2": 1213,
    "ProEMHS1024B_3": 1214,
    "ProEMHS1024BExcelon_3": 1215,
    # ProEM-HS1K-10Series
    "ProEMHS1K10Series": 1209,
    "ProEMHS1KB10": 1210,
    "ProEMHS1KB10Excelon": 1211,
    # PI-MAX3Series(303)
    "PIMax3Series": 300,
    "PIMax31024I": 301,
    "PIMax31024x256": 302,
    # PI-MAX4Series(721)
    "PIMax4Series": 700,
    # PI-MAX41024iSeries
    "PIMax41024ISeries": 703,
    "PIMax41024I": 701,
    "PIMax41024IRF": 704,
    # PI-MAX41024fSeries
    "PIMax41024FSeries": 710,
    "PIMax41024F": 711,
    "PIMax41024FRF": 712,
    # PI-MAX41024x256Series
    "PIMax41024x256Series": 705,
    "PIMax41024x256": 702,
    "PIMax41024x256RF": 706,
    # PI-MAX42048Series
    "PIMax42048Series": 716,
    "PIMax42048F": 717,
    "PIMax42048B": 718,
    "PIMax42048FRF": 719,
    "PIMax42048BRF": 720,
    # PI-MAX4512EMSeries
    "PIMax4512EMSeries": 708,
    "PIMax4512EM": 707,
    "PIMax4512BEM": 709,
    # PI-MAX41024EMSeries
    "PIMax41024EMSeries": 713,
    "PIMax41024EM": 715,
    "PIMax41024BEM": 714,
    # PyLoNSeries(439)
    "PylonSeries": 400,
    # PyLoN100Series
    "Pylon100Series": 418,
    "Pylon100F": 404,
    "Pylon100B": 401,
    "Pylon100BR": 407,
    "Pylon100BExcelon": 425,
    "Pylon100BRExcelon": 426,
    # PyLoN256Series
    "Pylon256Series": 419,
    "Pylon256F": 409,
    "Pylon256B": 410,
    "Pylon256E": 411,
    "Pylon256BR": 412,
    # PyLoN400Series
    "Pylon400Series": 420,
    "Pylon400F": 405,
    "Pylon400B": 402,
    "Pylon400BR": 408,
    "Pylon400BExcelon": 427,
    "Pylon400BRExcelon": 428,
    # PyLoN1024Series
    "Pylon1024Series": 421,
    "Pylon1024B": 417,
    "Pylon1024BExcelon": 429,
    # PyLoN1300Series
    "Pylon1300Series": 422,
    "Pylon1300F": 406,
    "Pylon1300B": 403,
    "Pylon1300R": 438,
    "Pylon1300BR": 432,
    "Pylon1300BExcelon": 430,
    "Pylon1300BRExcelon": 433,
    # PyLoN2048Series
    "Pylon2048Series": 423,
    "Pylon2048F": 415,
    "Pylon2048B": 434,
    "Pylon2048BR": 416,
    "Pylon2048BExcelon": 435,
    "Pylon2048BRExcelon": 436,
    # PyLoN2KSeries
    "Pylon2KSeries": 424,
    "Pylon2KF": 413,
    "Pylon2KB": 414,
    "Pylon2KBUV": 437,
    "Pylon2KBExcelon": 431,
    # PyLoN-IRSeries(904)
    "PylonirSeries": 900,
    # PyLoN-IR1024Series
    "Pylonir1024Series": 901,
    "Pylonir102422": 902,
    "Pylonir102417": 903,
    # PIoNIRSeries(502)
    "PionirSeries": 500,
    "Pionir640": 501,
    # NIRvanaSeries(802)
    "NirvanaSeries": 800,
    "Nirvana640": 801,
    # NIRvanaSTSeries(1302)
    "NirvanaSTSeries": 1300,
    "NirvanaST640": 1301,
    # NIRvana-LNSeries(1102)
    "NirvanaLNSeries": 1100,
    "NirvanaLN640": 1101,
    # SOPHIASeries(1840)
    "SophiaSeries": 1800,
    # SOPHIA2048Series
    "Sophia2048Series": 1801,
    "Sophia2048B": 1802,
    "Sophia2048BExcelon": 1803,
    "SophiaXO2048B": 1804,
    "SophiaXF2048B": 1805,
    "SophiaXB2048B": 1806,
    # SOPHIA2048-13.5Series
    "Sophia2048135Series": 1807,
    "Sophia2048135": 1808,
    "Sophia2048B135": 1809,
    "Sophia2048BR135": 1810,
    "Sophia2048B135Excelon": 1811,
    "Sophia2048BR135Excelon": 1812,
    "SophiaXO2048B135": 1813,
    "SophiaXO2048BR135": 1814,
    # SOPHIA4096Series
    "Sophia4096Series": 1826,
    "Sophia4096B": 1827,
    "SophiaXO4096B": 1829,
    "SophiaXF4096B": 1830,
    "SophiaXB4096B": 1831,
    # SOPHIA4096-HDRSeries
    "Sophia4096HdrSeries": 1832,
    "Sophia4096BHdr": 1833,
    "Sophia4096BRHdr": 1834,
    "SophiaXO4096BHdr": 1837,
    "SophiaXO4096BRHdr": 1838,
    "SophiaXF4096BHdr": 1839,
    "SophiaXF4096BRHdr": 1828,
    "SophiaXB4096BHdr": 1835,
    "SophiaXB4096BRHdr": 1836,
    # BLAZESeries(1519)
    "BlazeSeries": 1500,
    # BLAZE100Series
    "Blaze100Series": 1507,
    "Blaze100B": 1501,
    "Blaze100BR": 1505,
    "Blaze100HR": 1503,
    "Blaze100BRLD": 1509,
    "Blaze100BExcelon": 1511,
    "Blaze100BRExcelon": 1513,
    "Blaze100HRExcelon": 1515,
    "Blaze100BRLDExcelon": 1517,
    # BLAZE400Series
    "Blaze400Series": 1508,
    "Blaze400B": 1502,
    "Blaze400BR": 1506,
    "Blaze400HR": 1504,
    "Blaze400BRLD": 1510,
    "Blaze400BExcelon": 1512,
    "Blaze400BRExcelon": 1514,
    "Blaze400HRExcelon": 1516,
    "Blaze400BRLDExcelon": 1518,
    # FERGIESeries(1612)
    "FergieSeries": 1600,
    # FERGIE256Series
    "Fergie256Series": 1601,
    "Fergie256B": 1602,
    "Fergie256BR": 1607,
    "Fergie256BExcelon": 1603,
    "Fergie256BRExcelon": 1608,
    # FERGIE256FTSeries
    "Fergie256FTSeries": 1604,
    "Fergie256FFT": 1609,
    "Fergie256BFT": 1605,
    "Fergie256BRFT": 1610,
    "Fergie256BFTExcelon": 1606,
    "Fergie256BRFTExcelon": 1611,
    # FERGIE-ISO-81Series(2104)
    "FergieIso81Series": 2100,
    # FERGIE-ISO-81256FTSeries
    "FergieIso81256FTSeries": 2101,
    "FergieIso81256BFTExcelon": 2102,
    "FergieIso81256BRFTExcelon": 2103,
    # FERGIEAccessorySeries(1707)
    "FergieAccessorySeries": 1700,
    # FERGIELampSeries
    "FergieLampSeries": 1701,
    "FergieAEL": 1702,
    "FergieQTH": 1703,
    # FERGIELaserSeries
    "FergieLaserSeries": 1704,
    "FergieLaser785": 1705,
    "FergieLaser532": 1706,
    # KUROSeries(1904)
    "KuroSeries": 1900,
    "Kuro1200B": 1901,
    "Kuro1608B": 1902,
    "Kuro2048B": 1903
}
PicamModelLookup = dict(zip(PicamModel.values(), PicamModel.keys()))

PicamComputerInterface = {
    "Usb2": 1,
    "1394A": 2,
    "GigabitEthernet": 3,
    "Usb3": 4
}
PicamComputerInterfaceLookup = dict(zip(PicamComputerInterface.values(), PicamComputerInterface.keys()))

PicamStringSize = {
    "SensorName": 64,
    "SerialNumber": 64,
    "FirmwareName": 64,
    "FirmwareDetail": 256
}
PicamStringSizeLookup = dict(zip(PicamStringSize.values(), PicamStringSize.keys()))

PicamValueType = {
    "Integer": 1,
    "Boolean": 3,
    "Enumeration": 4,
    "LargeInteger": 6,
    "FloatingPoint": 2,
    "Rois": 5,
    "Pulse": 7,
    "Modulations": 8
}
PicamValueTypeLookup = dict(zip(PicamValueType.values(), PicamValueType.keys()))

PicamConstraintType = {
    "None": 1,
    "Range": 2,
    "Collection": 3,
    "Rois": 4,
    "Pulse": 5,
    "Modulations": 6
}
PicamConstraintTypeLookup = dict(zip(PicamConstraintType.values(), PicamConstraintType.keys()))

PI_V = lambda v, c, n: (PicamConstraintType[c] << 24) + (PicamValueType[v] << 16) + n

PicamParameter = {
    # Shutter Timing
    "ExposureTime": PI_V("FloatingPoint", "Range", 23),
    "ShutterTimingMode": PI_V("Enumeration", "Collection", 24),
    "ShutterOpeningDelay": PI_V("FloatingPoint", "Range", 46),
    "ShutterClosingDelay": PI_V("FloatingPoint", "Range", 25),
    "ShutterDelayResolution": PI_V("FloatingPoint", "Collection", 47),
    # Gating
    "GatingMode": PI_V("Enumeration", "Collection", 93),
    "RepetitiveGate": PI_V("Pulse", "Pulse", 94),
    "SequentialStartingGate": PI_V("Pulse", "Pulse", 95),
    "SequentialEndingGate": PI_V("Pulse", "Pulse", 96),
    "SequentialGateStepCount": PI_V("LargeInteger", "Range", 97),
    "SequentialGateStepIterations": PI_V("LargeInteger", "Range", 98),
    "DifStartingGate": PI_V("Pulse", "Pulse", 102),
    "DifEndingGate": PI_V("Pulse", "Pulse", 103),
    # Intensifier
    "EnableIntensifier": PI_V("Boolean", "Collection", 86),
    "IntensifierStatus": PI_V("Enumeration", "None", 87),
    "IntensifierGain": PI_V("Integer", "Range", 88),
    "EMIccdGainControlMode": PI_V("Enumeration", "Collection", 123),
    "EMIccdGain": PI_V("Integer", "Range", 124),
    "PhosphorDecayDelay": PI_V("FloatingPoint", "Range", 89),
    "PhosphorDecayDelayResolution": PI_V("FloatingPoint", "Collection", 90),
    "BracketGating": PI_V("Boolean", "Collection", 100),
    "IntensifierOptions": PI_V("Enumeration", "None", 101),
    "EnableModulation": PI_V("Boolean", "Collection", 111),
    "ModulationDuration": PI_V("FloatingPoint", "Range", 118),
    "ModulationFrequency": PI_V("FloatingPoint", "Range", 112),
    "RepetitiveModulationPhase": PI_V("FloatingPoint", "Range", 113),
    "SequentialStartingModulationPhase": PI_V("FloatingPoint", "Range", 114),
    "SequentialEndingModulationPhase": PI_V("FloatingPoint", "Range", 115),
    "CustomModulationSequence": PI_V("Modulations", "Modulations", 119),
    "PhotocathodeSensitivity": PI_V("Enumeration", "None", 107),
    "GatingSpeed": PI_V("Enumeration", "None", 108),
    "PhosphorType": PI_V("Enumeration", "None", 109),
    "IntensifierDiameter": PI_V("FloatingPoint", "None", 110),
    # Analog to Digital Conversion
    "AdcSpeed": PI_V("FloatingPoint", "Collection", 33),
    "AdcBitDepth": PI_V("Integer", "Collection", 34),
    "AdcAnalogGain": PI_V("Enumeration", "Collection", 35),
    "AdcQuality": PI_V("Enumeration", "Collection", 36),
    "AdcEMGain": PI_V("Integer", "Range", 53),
    "CorrectPixelBias": PI_V("Boolean", "Collection", 106),
    # Hardware I/O
    "TriggerSource": PI_V("Enumeration", "Collection", 79),
    "TriggerResponse": PI_V("Enumeration", "Collection", 30),
    "TriggerDetermination": PI_V("Enumeration", "Collection", 31),
    "TriggerFrequency": PI_V("FloatingPoint", "Range", 80),
    "TriggerTermination": PI_V("Enumeration", "Collection", 81),
    "TriggerCoupling": PI_V("Enumeration", "Collection", 82),
    "TriggerThreshold": PI_V("FloatingPoint", "Range", 83),
    "TriggerDelay": PI_V("FloatingPoint", "Range", 164),
    "OutputSignal": PI_V("Enumeration", "Collection", 32),
    "InvertOutputSignal": PI_V("Boolean", "Collection", 52),
    "OutputSignal2": PI_V("Enumeration", "Collection", 150),
    "InvertOutputSignal2": PI_V("Boolean", "Collection", 151),
    "EnableAuxOutput": PI_V("Boolean", "Collection", 161),
    "AuxOutput": PI_V("Pulse", "Pulse", 91),
    "EnableSyncMaster": PI_V("Boolean", "Collection", 84),
    "SyncMaster2Delay": PI_V("FloatingPoint", "Range", 85),
    "EnableModulationOutputSignal": PI_V("Boolean", "Collection", 116),
    "ModulationOutputSignalFrequency": PI_V("FloatingPoint", "Range", 117),
    "ModulationOutputSignalAmplitude": PI_V("FloatingPoint", "Range", 120),
    "AnticipateTrigger": PI_V("Boolean", "Collection", 131),
    "DelayFromPreTrigger": PI_V("FloatingPoint", "Range", 132),
    # Readout Control
    "ReadoutControlMode": PI_V("Enumeration", "Collection", 26),
    "ReadoutTimeCalculation": PI_V("FloatingPoint", "None", 27),
    "ReadoutPortCount": PI_V("Integer", "Collection", 28),
    "ReadoutOrientation": PI_V("Enumeration", "None", 54),
    "KineticsWindowHeight": PI_V("Integer", "Range", 56),
    "SeNsRWindowHeight": PI_V("Integer", "Range", 163),
    "VerticalShiftRate": PI_V("FloatingPoint", "Collection", 13),
    "Accumulations": PI_V("LargeInteger", "Range", 92),
    "EnableNondestructiveReadout": PI_V("Boolean", "Collection", 128),
    "NondestructiveReadoutPeriod": PI_V("FloatingPoint", "Range", 129),
    # Data Acquisition
    "Rois": PI_V("Rois", "Rois", 37),
    "NormalizeOrientation": PI_V("Boolean", "Collection", 39),
    "DisableDataFormatting": PI_V("Boolean", "Collection", 55),
    "ReadoutCount": PI_V("LargeInteger", "Range", 40),
    "ExactReadoutCountMaximum": PI_V("LargeInteger", "None", 77),
    "PhotonDetectionMode": PI_V("Enumeration", "Collection", 125),
    "PhotonDetectionThreshold": PI_V("FloatingPoint", "Range", 126),
    "PixelFormat": PI_V("Enumeration", "Collection", 41),
    "FrameSize": PI_V("Integer", "None", 42),
    "FrameStride": PI_V("Integer", "None", 43),
    "FramesPerReadout": PI_V("Integer", "None", 44),
    "ReadoutStride": PI_V("Integer", "None", 45),
    "PixelBitDepth": PI_V("Integer", "None", 48),
    "ReadoutRateCalculation": PI_V("FloatingPoint", "None", 50),
    "OnlineReadoutRateCalculation": PI_V("FloatingPoint", "None", 99),
    "FrameRateCalculation": PI_V("FloatingPoint", "None", 51),
    "Orientation": PI_V("Enumeration", "None", 38),
    "TimeStamps": PI_V("Enumeration", "Collection", 68),
    "TimeStampResolution": PI_V("LargeInteger", "Collection", 69),
    "TimeStampBitDepth": PI_V("Integer", "Collection", 70),
    "TrackFrames": PI_V("Boolean", "Collection", 71),
    "FrameTrackingBitDepth": PI_V("Integer", "Collection", 72),
    "GateTracking": PI_V("Enumeration", "Collection", 104),
    "GateTrackingBitDepth": PI_V("Integer", "Collection", 105),
    "ModulationTracking": PI_V("Enumeration", "Collection", 121),
    "ModulationTrackingBitDepth": PI_V("Integer", "Collection", 122),
    # Sensor Information
    "SensorType": PI_V("Enumeration", "None", 57),
    "CcdCharacteristics": PI_V("Enumeration", "None", 58),
    "SensorActiveWidth": PI_V("Integer", "None", 59),
    "SensorActiveHeight": PI_V("Integer", "None", 60),
    "SensorActiveExtendedHeight": PI_V("Integer", "None", 159),
    "SensorActiveLeftMargin": PI_V("Integer", "None", 61),
    "SensorActiveTopMargin": PI_V("Integer", "None", 62),
    "SensorActiveRightMargin": PI_V("Integer", "None", 63),
    "SensorActiveBottomMargin": PI_V("Integer", "None", 64),
    "SensorMaskedHeight": PI_V("Integer", "None", 65),
    "SensorMaskedTopMargin": PI_V("Integer", "None", 66),
    "SensorMaskedBottomMargin": PI_V("Integer", "None", 67),
    "SensorSecondaryMaskedHeight": PI_V("Integer", "None", 49),
    "SensorSecondaryActiveHeight": PI_V("Integer", "None", 74),
    "PixelWidth": PI_V("FloatingPoint", "None", 9),
    "PixelHeight": PI_V("FloatingPoint", "None", 10),
    "PixelGapWidth": PI_V("FloatingPoint", "None", 11),
    "PixelGapHeight": PI_V("FloatingPoint", "None", 12),
    # Sensor Layout
    "ActiveWidth": PI_V("Integer", "Range", 1),
    "ActiveHeight": PI_V("Integer", "Range", 2),
    "ActiveExtendedHeight": PI_V("Integer", "Range", 160),
    "ActiveLeftMargin": PI_V("Integer", "Range", 3),
    "ActiveTopMargin": PI_V("Integer", "Range", 4),
    "ActiveRightMargin": PI_V("Integer", "Range", 5),
    "ActiveBottomMargin": PI_V("Integer", "Range", 6),
    "MaskedHeight": PI_V("Integer", "Range", 7),
    "MaskedTopMargin": PI_V("Integer", "Range", 8),
    "MaskedBottomMargin": PI_V("Integer", "Range", 73),
    "SecondaryMaskedHeight": PI_V("Integer", "Range", 75),
    "SecondaryActiveHeight": PI_V("Integer", "Range", 76),
    # Sensor Cleaning
    "CleanSectionFinalHeight": PI_V("Integer", "Range", 17),
    "CleanSectionFinalHeightCount": PI_V("Integer", "Range", 18),
    "CleanSerialRegister": PI_V("Boolean", "Collection", 19),
    "CleanCycleCount": PI_V("Integer", "Range", 20),
    "CleanCycleHeight": PI_V("Integer", "Range", 21),
    "CleanBeforeExposure": PI_V("Boolean", "Collection", 78),
    "CleanUntilTrigger": PI_V("Boolean", "Collection", 22),
    "StopCleaningOnPreTrigger": PI_V("Boolean", "Collection", 130),
    # Sensor Temperature
    "SensorTemperatureSetPoint": PI_V("FloatingPoint", "Range", 14),
    "SensorTemperatureReading": PI_V("FloatingPoint", "None", 15),
    "SensorTemperatureStatus": PI_V("Enumeration", "None", 16),
    "DisableCoolingFan": PI_V("Boolean", "Collection", 29),
    "CoolingFanStatus": PI_V("Enumeration", "None", 162),
    "EnableSensorWindowHeater": PI_V("Boolean", "Collection", 127),
    "VacuumStatus": PI_V("Enumeration", "None", 165),
    # Spectrograph
    "CenterWavelengthSetPoint": PI_V("FloatingPoint", "Range", 140),
    "CenterWavelengthReading": PI_V("FloatingPoint", "None", 141),
    "CenterWavelengthStatus": PI_V("Enumeration", "None", 149),
    "GratingType": PI_V("Enumeration", "None", 142),
    "GratingCoating": PI_V("Enumeration", "None", 143),
    "GratingGrooveDensity": PI_V("FloatingPoint", "None", 144),
    "GratingBlazingWavelength": PI_V("FloatingPoint", "None", 145),
    "FocalLength": PI_V("FloatingPoint", "None", 146),
    "InclusionAngle": PI_V("FloatingPoint", "None", 147),
    "SensorAngle": PI_V("FloatingPoint", "None", 148),
    # Accessory - Lamp
    "LightSource": PI_V("Enumeration", "Collection", 133),
    "LightSourceStatus": PI_V("Enumeration", "None", 134),
    "Age": PI_V("FloatingPoint", "None", 135),
    "LifeExpectancy": PI_V("FloatingPoint", "None", 136),
    # Accessory - Laser
    "LaserOutputMode": PI_V("Enumeration", "Collection", 137),
    "LaserPower": PI_V("FloatingPoint", "Range", 138),
    "LaserStatus": PI_V("Enumeration", "None", 157),
    "InputTriggerStatus": PI_V("Enumeration", "None", 158)
}
PicamParameterLookup = dict(zip(PicamParameter.values(), PicamParameter.keys()))

PicamActiveShutter = {
    "None": 1,
    "Internal": 2,
    "External": 3
}
PicamActiveShutterLookup = dict(zip(PicamActiveShutter.values(), PicamActiveShutter.keys()))

PicamAdcAnalogGain = {
    "Low": 1,
    "Medium": 2,
    "High": 3
}
PicamAdcAnalogGainLookup = dict(zip(PicamAdcAnalogGain.values(), PicamAdcAnalogGain.keys()))

PicamAdcQuality = {
    "LowNoise": 1,
    "HighCapacity": 2,
    "HighSpeed": 4,
    "ElectronMultiplied": 3
}
PicamAdcQualityLookup = dict(zip(PicamAdcQuality.values(), PicamAdcQuality.keys()))

PicamCcdCharacteristicsMask = {
    "None": 0x000,
    "BackIlluminated": 0x001,
    "DeepDepleted": 0x002,
    "OpenElectrode": 0x004,
    "UVEnhanced": 0x008,
    "ExcelonEnabled": 0x010,
    "SecondaryMask": 0x020,
    "Multiport": 0x040,
    "AdvancedInvertedMode": 0x080,
    "HighResistivity": 0x100
}  # Not used? As in picam.h

PicamCcdCharacteristicsMaskLookup = dict(zip(PicamCcdCharacteristicsMask.values(), PicamCcdCharacteristicsMask.keys()))

PicamCenterWavelengthStatus = {
    "Movind": 1,
    "Stationary": 2,
    "Faulted": 3
}

PicamCenterWavelengthStatusLookup = dict(zip(PicamCenterWavelengthStatus.values(), PicamCenterWavelengthStatus.keys()))

PicamCoolingFanStatus = {
    "Off": 1,
    "On": 2,
    "ForcedOn": 3
}

PicamCoolingFanStatusLookup = dict(zip(PicamCoolingFanStatus.values(), PicamCoolingFanStatus.keys()))

PicamEMIccdGainControlMode = {
    "Optimal": 1,
    "Manual": 2
}
PicamEMIccdGainControlModeLookup = dict(zip(PicamEMIccdGainControlMode.values(), PicamEMIccdGainControlMode.keys()))

PicamGateTrackingMask = {
    "None": 0x0,
    "Delay": 0x1,
    "Width": 0x2
}
PicamGateTrackingMaskLookup = dict(zip(PicamGateTrackingMask.values(), PicamGateTrackingMask.keys()))

PicamGatingMode = {
    "Disabled": 4,
    "Repetitive": 1,
    "Sequential": 2,
    "Custom": 3
}
PicamGatingModeLookup = dict(zip(PicamGatingMode.values(), PicamGatingMode.keys()))

PicamGatingSpeed = {
    "Fast": 1,
    "Slow": 2
}
PicamGatingSpeedLookup = dict(zip(PicamGatingSpeed.values(), PicamGatingSpeed.keys()))

PicamGratingCoating = {
    "Al": 1,
    "AlMgF2": 4,
    "Ag": 2,
    "Au": 3
}
PicamGratingCoatingLookup = dict(zip(PicamGratingCoating.values(), PicamGratingCoating.keys()))

PicamGratingType = {
    "Ruled": 1,
    "HolographicVisible": 2,
    "HolographicNir": 3,
    "HolographicUv": 4,
    "Mirror": 5
}
PicamGratingTypeLookup = dict(zip(PicamGratingType.values(), PicamGratingType.keys()))

PicamIntensifierOptionsMask = {
    "None": 0x0,
    "McpGating": 0x1,
    "SubNanosecondGating": 0x2,
    "Modulation": 0x4
}
PicamIntensifierOptionsMaskLookup = dict(zip(PicamIntensifierOptionsMask.values(), PicamIntensifierOptionsMask.keys()))

PicamIntensifierStatus = {
    "PoweredOff": 1,
    "PoweredOn": 2
}
PicamIntensifierStatusLookup = dict(zip(PicamIntensifierStatus.values(), PicamIntensifierStatus.keys()))

PicamLaserOutputMode = {
    "Disabled": 1,
    "ContinuousWave": 2,
    "Pulsed": 3,
}
PicamLaserOutputModeLookup = dict(zip(PicamLaserOutputMode.values(), PicamLaserOutputMode.keys()))

PicamLaserStatus = {
    "Disabled": 1,
    "Unarmed": 2,
    "Arming": 3,
    "Armed": 4
}
PicamLaserStatusLookup = dict(zip(PicamLaserStatus.values(), PicamLaserStatus.keys()))

PicamLightSource = {
    "Disabled": 1,
    "Hg": 2,
    "NeAr": 3,
    "Qth": 4
}
PicamLightSourceLookup = dict(zip(PicamLightSource.values(), PicamLightSource.keys()))

PicamLightSourceStatus = {
    "Unstable": 1,
    "Stable": 2,
}
PicamLightSourceStatusLookup = dict(zip(PicamLightSourceStatus.values(), PicamLightSourceStatus.keys()))

PicamModulationTrackingMask = {
    "None": 0x0,
    "Duration": 0x1,
    "Frequency": 0x2,
    "Phase": 0x4,
    "OutputSignalFrequency": 0x8
}
PicamModulationTrackingMaskLookup = dict(zip(PicamModulationTrackingMask.values(), PicamModulationTrackingMask.keys()))

PicamOrientationMask = {
    "Normal": 0x0,
    "FlippedHorizontally": 0x1,
    "FlippedVertically": 0x2
}
PicamOrientationMaskLookup = dict(zip(PicamOrientationMask.values(), PicamOrientationMask.keys()))

PicamOutputSignal = {
    "Acquiring": 6,
    "AlwaysHigh": 5,
    "AlwaysLow": 4,
    "AuxOutput": 14,
    "Busy": 3,
    "EffectivelyExposing": 9,
    "EffectivelyExposingAlternation": 15,
    "Exposing": 8,
    "Gate": 13,
    "InternalTriggerT0": 12,
    "NotReadingOut": 1,
    "ReadingOut": 10,
    "ShiftingUnderMask": 7,
    "ShutterOpen": 2,
    "WaitingForTrigger": 11
}
PicamOutputSignalLookup = dict(zip(PicamOutputSignal.values(), PicamOutputSignal.keys()))

PicamPhosphorType = {
    "P43": 1,
    "P46": 2
}
PicamPhosphorTypeLookup = dict(zip(PicamPhosphorType.values(), PicamPhosphorType.keys()))

PicamPhotocathodeSensitivity = {
    "RedBlue": 1,
    "SuperRed": 7,
    "SuperBlue": 2,
    "UV": 3,
    "SolarBlind": 10,
    "Unigen2Filmless": 4,
    "InGaAsFilmless": 9,
    "HighQEFilmless": 5,
    "HighRedFilmless": 8,
    "HighBlueFilmless": 6
}
PicamPhotocathodeSensitivityLookup = dict(zip(PicamPhotocathodeSensitivity.values(),
                                              PicamPhotocathodeSensitivity.keys()))

PicamPhotonDetectionMode = {
    "Disabled": 1,
    "Thresholding": 2,
    "Clipping": 3
}
PicamPhotonDetectionModeLookup = dict(zip(PicamPhotonDetectionMode.values(),
                                          PicamPhotonDetectionMode.keys()))

PicamPixelFormat = {
    "Monochrome16Bit": 1,
    "Monochrome32Bit": 2
}
PicamPixelFormatLookup = dict(zip(PicamPixelFormat.values(), PicamPixelFormat.keys()))

PicamReadoutControlMode = {
    "FullFrame": 1,
    "FrameTransfer": 2,
    "Interline": 5,
    "RollingShutter": 8,
    "Kinetics": 3,
    "SpectraKinetics": 4,
    "Dif": 6,
    "SeNsR": 7
}
PicamReadoutControlModeLookup = dict(zip(PicamReadoutControlMode.values(),
                                         PicamReadoutControlMode.keys()))

PicamSensorTemperatureStatus = {
    "Unlocked": 1,
    "Locked": 2,
    "Faulted": 3
}
PicamSensorTemperatureStatusLookup = dict(zip(PicamSensorTemperatureStatus.values(),
                                              PicamSensorTemperatureStatus.keys()))

PicamSensorType = {
    "Ccd": 1,
    "InGaAs": 2,
    "Cmos": 3
}
PicamSensorTypeLookup = dict(zip(PicamSensorType.values(), PicamSensorType.keys()))

PicamShutterStatus = {
    "NotConnected": 1,
    "Connected": 2,
    "Overheated": 3
}
PicamShutterStatusLookup = dict(zip(PicamShutterStatus.values(), PicamShutterStatus.keys()))

PicamShutterTimingMode = {
    "Normal": 1,
    "AlwaysClosed": 2,
    "AlwaysOpen": 3,
    "OpenBeforeTrigger": 4
}
PicamShutterTimingModeLookup = dict(zip(PicamShutterTimingMode.values(), PicamShutterTimingMode.keys()))

PicamShutterType = {
    "None": 1,
    "VincentCS2": 2,
    "VincentCS45": 3,
    "VincentCS90": 9,
    "VincentDSS10": 8,
    "VincentVS25": 4,
    "VincentVS35": 5,
    "ProntorMagnetic0": 6,
    "ProntorMagneticE40": 7,
}
PicamShutterTypeLookup = dict(zip(PicamShutterType.values(), PicamShutterType.keys()))

PicamTimeStampsMask = {
    "None": 0x0,
    "ExposureStarted": 0x1,
    "ExposureEnded": 0x2
}
PicamTimeStampsMaskLookup = dict(zip(PicamTimeStampsMask.values(), PicamTimeStampsMask.keys()))

PicamTriggerCoupling = {
    "AC": 1,
    "DC": 2
}
PicamTriggerCouplingLookup = dict(zip(PicamTriggerCoupling.values(), PicamTriggerCoupling.keys()))

PicamTriggerDetermination = {
    "PositivePolarity": 1,
    "NegativePolarity": 2,
    "RisingEdge": 3,
    "FallingEdge": 4,
    "AlternatingEdgeRising": 5,
    "AlternatingEdgeFalling": 6
}
PicamTriggerDeterminationLookup = dict(zip(PicamTriggerDetermination.values(), PicamTriggerDetermination.keys()))

PicamTriggerResponse = {
    "NoResponse": 1,
    "StartOnSingleTrigger": 5,
    "ReadoutPerTrigger": 2,
    "ShiftPerTrigger": 3,
    "GatePerTrigger": 6,
    "ExposeDuringTriggerPulse": 4,
}
PicamTriggerResponseLookup = dict(zip(PicamTriggerResponse.values(), PicamTriggerResponse.keys()))

PicamTriggerSource = {
    "None": 3,
    "External": 1,
    "Internal": 2
}
PicamTriggerSourceLookup = dict(zip(PicamTriggerSource.values(), PicamTriggerSource.keys()))

PicamTriggerStatus = {
    "NotConnected": 1,
    "Connected": 2
}
PicamTriggerStatusLookup = dict(zip(PicamTriggerStatus.values(), PicamTriggerStatus.keys()))

PicamTriggerTermination = {
    "FiftyOhms": 1,
    "HighImpedance": 2
}
PicamTriggerTerminationLookup = dict(zip(PicamTriggerTermination.values(), PicamTriggerTermination.keys()))

PicamVacuumStatus = {
    "Sufficient": 1,
    "Low": 2
}
PicamVacuumStatusLookup = dict(zip(PicamVacuumStatus.values(), PicamVacuumStatus.keys()))

PicamValueAccess = {
    "ReadOnly": 1,
    "ReadWriteTrivial": 3,
    "ReadWrite": 2
}
PicamValueAccessLookup = dict(zip(PicamValueAccess.values(), PicamValueAccess.keys()))

PicamConstraintScope = {
    "Independent": 1,
    "Dependent": 2
}
PicamConstraintScopeLookup = dict(zip(PicamConstraintScope.values(), PicamConstraintScope.keys()))

PicamConstraintSeverity = {
    "Error": 1,
    "Warning": 2
}
PicamConstraintSeverityLookup = dict(zip(PicamConstraintSeverity.values(), PicamConstraintSeverity.keys()))

PicamConstraintCategory = {
    "Capable": 1,
    "Required": 2,
    "Recommended": 3
}
PicamConstraintCategoryLookup = dict(zip(PicamConstraintCategory.values(), PicamConstraintCategory.keys()))

PicamRoisConstraintRulesMask = {
    "None": 0x00,
    "XBinningAlignment": 0x01,
    "YBinningAlignment": 0x02,
    "HorizontalSymmetry": 0x04,
    "VerticalSymmetry": 0x08,
    "SymmetryBoundsBinning": 0x10
}
PicamRoisConstraintRulesMaskLookup = dict(zip(PicamRoisConstraintRulesMask.values(),
                                              PicamRoisConstraintRulesMask.keys()))

PicamAcquisitionErrorsMask = {
    "None": 0x00,
    "CameraFaulted": 0x10,
    "ConnectionLost": 0x02,
    "ShutterOverheated": 0x08,
    "DataLost": 0x01,
    "DataNotArriving": 0x04
}
PicamAcquisitionErrorsMaskLookup = dict(zip(PicamAcquisitionErrorsMask.values(), PicamAcquisitionErrorsMask.keys()))


# +++++++ structures +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class PicamCameraID(ctypes.Structure):
        _fields_ = [("model", piint),
                    ("computer_interface", piint),
                    ("sensor_name", pichar * PicamStringSize["SensorName"]),
                    ("serial_number", pichar * PicamStringSize["SerialNumber"])]


class PicamFirmwareDetail(ctypes.Structure):
    _fields_ = [("name", pichar * PicamStringSize["FirmwareName"]),
                ("detail", pichar * PicamStringSize["FirmwareDetail"])]


class PicamRoi(ctypes.Structure):
    _fields_ = [("x", piint),
                ("width", piint),
                ("x_binning", piint),
                ("y", piint),
                ("height", piint),
                ("y_binning", piint)]


class PicamRois(ctypes.Structure):
    _fields_ = [("roi_array", ctypes.POINTER(PicamRoi)),
                ("roi_count", piint)]


class PicamPulse(ctypes.Structure):
    _fields_ = [("delay", piflt),
                ("width", piflt)]


class PicamModulation(ctypes.Structure):
    _fields_ = [("duration", piflt),
                ("frequency", piflt),
                ("phase", piflt),
                ("output_signal_frequency", piflt)]


class PicamModulations(ctypes.Structure):
    _fields_ = [("modulation_array", ctypes.POINTER(PicamModulation)),
                ("modulation_count", piint)]


class PicamCollectionConstraint(ctypes.Structure):
    _fields_ = [("scope", piint),
                ("severity", piint),
                ("values_array", ctypes.POINTER(piflt)),
                ("values_count", piint)]


class PicamRangeConstraint(ctypes.Structure):
    _fields_ = [("scope", piint),
                ("severity", piint),
                ("empty_set", pibln),
                ("minimum", piflt),
                ("maximum", piflt),
                ("increment", piflt),
                ("excluded_values_array", ctypes.POINTER(piflt)),
                ("excluded_values_count", piint),
                ("outlying_values_array", ctypes.POINTER(piflt)),
                ("outlying_values_count", piint)]


class PicamRoisConstraint(ctypes.Structure):
    _fields_ = [("scope", piint),
                ("severity", piint),
                ("empty_set", pibln),
                ("rules", piint),
                ("maximum_roi_count", piint),
                ("x_constraint", PicamRangeConstraint),
                ("width_constraint", PicamRangeConstraint),
                ("x_binning_limits_array", ctypes.POINTER(piint)),
                ("x_binning_limits_count", piint),
                ("y_constraint", PicamRangeConstraint),
                ("height_constraint", PicamRangeConstraint),
                ("y_binning_limits_array", ctypes.POINTER(piint)),
                ("y_binning_limits_count", piint)]


class PicamPulseConstraint(ctypes.Structure):
    _fields_ = [("scope", piint),
                ("severity", piint),
                ("empty_set", pibln),
                ("delay_constraint", PicamRangeConstraint),
                ("width_constraint", PicamRangeConstraint),
                ("minimum_duration", piflt),
                ("maximum_duration", piflt)]


class PicamModulationsConstraint(ctypes.Structure):
    _fields_ = [("scope", piint),
                ("severity", piint),
                ("empty_set", pibln),
                ("maximum_modulation_count", piint),
                ("duration_constraint", PicamRangeConstraint),
                ("frequency_constraint", PicamRangeConstraint),
                ("phase_constraint", PicamRangeConstraint),
                ("output_signal_frequency_constraint", PicamRangeConstraint)]


class PicamAvailableData(ctypes.Structure):
    _fields_ = [("initial_readout", pivoid),
                ("readout_count", pi64s)]


class PicamAcquisitionStatus(ctypes.Structure):
    _fields_ = [("running", pibln),
                ("errors", piint),
                ("readout_rate", piflt)]

