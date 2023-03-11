# import IDS libraries
from ids_peak import ids_peak as peak
from ids_peak_ipl import ids_peak_ipl
from ids_peak import ids_peak_ipl_extension

from imswitch.imcommon.model import initLogger

class IDSCamera:
    def __init__(self):
        super().__init__()
        self.__logger = initLogger(self, tryInheritParent=False)

        peak.Library.Initialize()
        self.model = "IDS Camera"
        
        # camera parameters
        self.blacklevel = 15
        self.exposure_time = 30
        self.analog_gain = 1
        self.pixel_format = "Mono8"
        self.target_fps = 30

        self.SensorWidth = 1920
        self.SensorHeight = 1200
        self.shape = (self.SensorWidth,self.SensorHeight)
        
        self.is_running = False

        self.m_device = None
        self.m_dataStream = None
        self.m_node_map_remote_device = None

        self.openCamera()


    def start_live(self):
        if self.m_device is None:
            self.__logger.debug("No device found!")
            return

        try:
            if not self.prepare_acquisition():
                self.__logger.warning("Warning! Couldn't prepare acquisition")
            
            if not self.setROI(0, 0, int(self.SensorWidth), int(self.SensorHeight)):
                self.__logger.warning("Warning! Couldn't set roi")
            
            if not self.alloc_and_announce_buffers():
                self.__logger.warning("Warning! Couldn't allocate buffer")

            if not self.set_framerate(self.target_fps):
                self.__logger.warning("Warning! Couldn't set framerate")

            self.m_dataStream.StartAcquisition(peak.AcquisitionStartMode_Default, peak.DataStream.INFINITE_NUMBER)
            self.m_node_map_remote_device.FindNode("TLParamsLocked").SetValue(1)
            self.m_node_map_remote_device.FindNode("AcquisitionStart").Execute()

            self.is_running = True
        except peak.Exception as e:
            self.__logger.debug("Start Live was a problem!")
            self.__logger.error(e)
        
         
    def stop_live(self):
        if self.m_device is None or self.is_running is False:
            return

        try:
            self.m_node_map_remote_device.FindNode("AcquisitionStop").Execute()

            self.m_dataStream.KillWait()
            self.m_dataStream.StopAcquisition(peak.AcquisitionStopMode_Default)
            self.m_dataStream.Flush(peak.DataStreamFlushMode_DiscardAll)

            self.m_node_map_remote_device.FindNode("TLParamsLocked").SetValue(0)
        except peak.Exception as e:
            self.__logger.error(e)

        self.camera_is_open = False

    def suspend_live(self):
        try:
            self.__logger.debug("Suspending live")
            self.m_node_map_remote_device.FindNode("AcquisitionStop").Execute()
            self.m_node_map_remote_device.FindNode("TLParamsLocked").SetValue(0)

            self.m_dataStream.StopAcquisition(peak.AcquisitionStopMode_Default)
            
            self.camera_is_open = False
        except peak.Exception as e:
            self.__logger.error(e)

    def prepare_live(self):
        pass

    def close(self):
        self.camera_is_open = False
        
    def set_value(self ,feature_key, feature_value):
        try:
            if feature_key == "PixelFormat":
                self.m_node_map_remote_device.FindNode("PixelFormat").SetCurrentEntry(feature_value)
            else:
                self.m_node_map_remote_device.FindNode(feature_key).SetValue(feature_value)
            
        except peak.Exception as e:
            self.__logger.error(e)
            self.__logger.error(feature_key)
            self.__logger.debug("Value not available?")
    

    def set_exposure_time(self,exposure_time):
        self.exposure_time = exposure_time
        self.set_value("ExposureTime", self.exposure_time*1000)

    def set_analog_gain(self,analog_gain):
        self.analog_gain = analog_gain
        self.set_value("Gain", self.analog_gain)
        
    def set_blacklevel(self,blacklevel):
        self.blacklevel = blacklevel
        self.set_value("BlackLevel", blacklevel)

    def set_pixel_format(self,format):
        self.pixelformat = format
        self.set_value("PixelFormat", self.pixelformat)

    def set_image_width(self, width):
        self.SensorWidth = width
        self.set_value("Width", int(self.SensorWidth))

    def set_image_height(self, height):
        self.SensorHeight = height
        self.set_value("Height", int(self.SensorHeight))
        
    def getLast(self):
        try:
            buffer = self.m_dataStream.WaitForFinishedBuffer(5000)

            # Create IDS peak IPL image for debayering and convert it to [desired] format
            image = ids_peak_ipl.Image_CreateFromSizeAndBuffer(
                buffer.PixelFormat(),
                buffer.BasePtr(),
                buffer.Size(),
                buffer.Width(),
                buffer.Height()
            )

            converted_ipl_image = image.ConvertTo(ids_peak_ipl.PixelFormatName_Mono8)
            
            # get numpy array from image
            image_np_array = converted_ipl_image.get_numpy_2D()

            self.m_dataStream.QueueBuffer(buffer)
            return image_np_array
        except peak.Exception as e:
            self.__logger.debug("Get Last was a problem!")
            self.__logger.error(e)

        
    def getLastChunk(self):
        try:
            # Get buffer from device's DataStream
            buffer = self.m_dataStream.WaitForFinishedBuffer(5000)
        
            if buffer.HasChunks():
                self.m_node_map_remote_device.UpdateChunkNodes(buffer)
                exposure_time = self.m_node_map_remote_device.FindNode("ChunkExposureTime").Value()
        
            # Create IDS peak IPL image for debayering and convert it to [desired] format
            image = ids_peak_ipl.Image_CreateFromSizeAndBuffer(
                buffer.PixelFormat(),
                buffer.BasePtr(),
                buffer.Size(),
                buffer.Width(),
                buffer.Height()
            )

            converted_ipl_image = image.ConvertTo(ids_peak_ipl.PixelFormatName_Mono8)
            
            # get numpy array from image
            image_np_array = converted_ipl_image.get_numpy_2D()
        
            self.m_dataStream.QueueBuffer(buffer)
            return image_np_array
        except peak.Exception as e:
            self.__logger.error(e)
       
    def setROI(self, x, y, width, height):
        # TODO find nearest number dividable by 8 for width and height
        while width % 8 != 0:
            width -= 1

        while height % 8 != 0:
            height -= 1

        try:

            # self.__logger.debug("Setting ROI with value")
            # self.__logger.debug("Height: " + str(height) + " Width: " + str(width))

            # Get the minimum ROI and set it. After that there are no size restrictions anymore
            x_min = self.m_node_map_remote_device.FindNode("OffsetX").Minimum()
            y_min = self.m_node_map_remote_device.FindNode("OffsetY").Minimum()
            w_min = self.m_node_map_remote_device.FindNode("Width").Minimum()
            h_min = self.m_node_map_remote_device.FindNode("Height").Minimum()
        
            self.m_node_map_remote_device.FindNode("OffsetX").SetValue(x_min)
            self.m_node_map_remote_device.FindNode("OffsetY").SetValue(y_min)
            self.m_node_map_remote_device.FindNode("Width").SetValue(w_min)
            self.m_node_map_remote_device.FindNode("Height").SetValue(h_min)
        
            # Get the maximum ROI values
            x_max = self.m_node_map_remote_device.FindNode("OffsetX").Maximum()
            y_max = self.m_node_map_remote_device.FindNode("OffsetY").Maximum()
            w_max = self.m_node_map_remote_device.FindNode("Width").Maximum()
            h_max = self.m_node_map_remote_device.FindNode("Height").Maximum()
        
            if (x < x_min) or (y < y_min) or (x > x_max) or (y > y_max):
                self.__logger.error("Offset value is wrong!")
                return False
            elif (width < w_min) or (height < h_min) or ((x + width) > w_max) or ((y + height) > h_max):
                self.__logger.warning("ROI size is wrong! Setting to maximum value!")
                self.m_node_map_remote_device.FindNode("Width").SetValue(w_max)
                self.m_node_map_remote_device.FindNode("Height").SetValue(h_max)

                return True
            else:
                # Now, set final ROI
                self.m_node_map_remote_device.FindNode("OffsetX").SetValue(x)
                self.m_node_map_remote_device.FindNode("OffsetY").SetValue(y)
                self.m_node_map_remote_device.FindNode("Width").SetValue(width)
                self.m_node_map_remote_device.FindNode("Height").SetValue(height)
        
                return True
        except peak.Exception as e:
            # ...
            self.__logger.error(e)
        
        return False

    def openPropertiesGUI(self):
        pass

    def setPropertyValue(self, property_name, property_value):
        # Check if the property exists.
        if property_name == "gain":
            self.set_analog_gain(property_value)
        elif property_name == "exposure":
            self.set_exposure_time(property_value)
        elif property_name == "blacklevel":
            self.set_blacklevel(property_value)
        elif property_name == "image_width":
            self.set_image_width(property_value)
        elif property_name == "image_height":
            self.set_image_height(property_value)
        elif property_name == "pixel_format":
            self.set_pixel_format(property_value)
        else:
            self.__logger.warning(f'Set Property {property_name} does not exist')
            return False
        return property_value

    def getPropertyValue(self, property_name):
        # Check if the property exists.
        if property_name == "gain":
            property_value = self.gain
        elif property_name == "exposure":
            property_value = self.exposure
        elif property_name == "blacklevel":
            property_value = self.blacklevel
        elif property_name == "image_width":
            property_value = self.SensorWidth
        elif property_name == "image_height":
            property_value = self.SensorHeight
        elif property_name == "pixel_format":
            property_value = self.PixelFormat
        else:
            self.__logger.warning(f'Get Property {property_name} does not exist')
            return False
        return property_value

    def openCamera(self):
        try:
            device_manager = peak.DeviceManager.Instance()
            device_manager.Update()

            if device_manager.Devices().empty():
                self.__logger.Debug("No IDS camera found!")

            device_count = device_manager.Devices().size()
            for i in range(device_count):
                if device_manager.Devices()[i].IsOpenable():
                    self.m_device = device_manager.Devices()[i].OpenDevice(peak.DeviceAccessType_Control)
        
                    # Get NodeMap of the RemoteDevice for all accesses to the GenICam NodeMap tree
                    self.m_node_map_remote_device = self.m_device.RemoteDevice().NodeMaps()[0]
    
            self.set_binning(1)
            self.camera = self.m_device
        except peak.Exception as e:
            self.__logger.error(e)
        
    
    def prepare_acquisition(self):
        try:
            if self.m_device:
                data_streams = self.m_device.DataStreams()
                # no data streams available
                if data_streams.empty():
                    return False
            
                if self.m_dataStream is None:
                    self.m_dataStream = data_streams[0].OpenDataStream()
            
                return True
        except peak.Exception as e:
            self.__logger.error(e)
        
        return False
    

    def alloc_and_announce_buffers(self):
        try:
            if self.m_dataStream:
                # Flush queue and prepare all buffers for revoking
                self.m_dataStream.Flush(peak.DataStreamFlushMode_DiscardAll)
        
                # Clear all old buffers
                for buffer in self.m_dataStream.AnnouncedBuffers():
                    self.m_dataStream.RevokeBuffer(buffer)
        
                payload_size = self.m_node_map_remote_device.FindNode("PayloadSize").Value()
        
                # Get number of minimum required buffers
                num_buffers_min_required = self.m_dataStream.NumBuffersAnnouncedMinRequired()
        
                # Alloc buffers
                for count in range(num_buffers_min_required):
                    buffer = self.m_dataStream.AllocAndAnnounceBuffer(payload_size)
                    self.m_dataStream.QueueBuffer(buffer)

                return True
        except peak.Exception as e:
            self.__logger.error(e)
        
        return False

    
    def set_framerate(self, target=None):
        try:
            min_frame_rate = 0
            max_frame_rate = 0
            inc_frame_rate = 0

            # Get frame rate range. All values in fps.
            min_frame_rate = self.m_node_map_remote_device.FindNode("AcquisitionFrameRate").Minimum()
            max_frame_rate = self.m_node_map_remote_device.FindNode("AcquisitionFrameRate").Maximum()
            
            if self.m_node_map_remote_device.FindNode("AcquisitionFrameRate").HasConstantIncrement():
                inc_frame_rate = self.m_node_map_remote_device.FindNode("AcquisitionFrameRate").Increment()
            else:
                # If there is no increment, it might be useful to choose a suitable increment for a GUI control element (e.g. a slider)
                inc_frame_rate = 0.1
            
            # Get the current frame rate
            frame_rate = self.m_node_map_remote_device.FindNode("AcquisitionFrameRate").Value()
            
            if target is None or target > max_frame_rate or target < min_frame_rate:
                # Set frame rate to maximum
                self.m_node_map_remote_device.FindNode("AcquisitionFrameRate").SetValue(max_frame_rate)
            else:
                self.m_node_map_remote_device.FindNode("AcquisitionFrameRate").SetValue(float(target))

            return True
        except peak.Exception as e:
            self.__logger.error(e)

        return False

    def set_binning(self, binning=1):
        try:
            # set BinningSelector to "Region0"
            self.m_node_map_remote_device.FindNode("BinningSelector").SetCurrentEntry("Region0")
            
            # determine the current BinningHorizontal 
            h_binning = self.m_node_map_remote_device.FindNode("BinningHorizontal").Value()
            self.__logger.debug("Current Binning: " + str(h_binning))
            self.__logger.debug("Target Binning: " + str(binning))
            
            # set binning value
            self.m_node_map_remote_device.FindNode("BinningHorizontal").SetValue(int(binning))
            self.m_node_map_remote_device.FindNode("BinningVertical").SetValue(int(binning))
        except peak.Exception as e:
            self.__logger.error(e)