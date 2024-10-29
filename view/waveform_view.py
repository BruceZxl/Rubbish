import math
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Timer
import numpy as np
from PySide6 import QtCore,QtGui
from PySide6.QtCore import QRectF, QObject
from PySide6.QtGui import QImage,QColor
from PySide6.QtQuick import QQuickPaintedItem
import cv2
from loguru import logger

from data_model.frame_size import FrameSize
from viewmodel.frame_sizes import FrameSizes
from viewmodel.waveform_area_viewmodel import WaveformAreaViewModel
from viewmodel.waveform_page_viewmodel import WaveformPageViewModel
def create_canvas_with_lines(width=1190, height=1280, lines=5, color=(0, 0, 0), line_color=(192,192,192), dash_length=10, gap_length=5):
    # 创建一个白色画布
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255

    # 计算每个竖线的位置
    spacing = width // lines
    mid = spacing//2
    # 绘制中间的虚线
    mid_x = width // 2
    for y in range(0, height, dash_length + gap_length):
        # 每次绘制一个 dash 的长度
        cv2.line(canvas, (mid, y), (mid, min(y + dash_length, height)), (192,192,192), 2)

    # 绘制竖线
    for i in range(1, lines):
        x = i * spacing
        cv2.line(canvas, (x, 0), (x, height), line_color, 2)
        for y in range(0, height, dash_length + gap_length):
        # 每次绘制一个 dash 的长度
            cv2.line(canvas, (mid+x, y), (mid+x, min(y + dash_length, height)), (192,192,192), 2)

    return canvas

xs = [1,2,4,5,10,30,60,120,300,1800]

imgs = [create_canvas_with_lines(lines=x) for x in xs]

class WaveformView(QQuickPaintedItem):  # 波形视图
    frameSizeChanged = QtCore.Signal()  # 创建信号  窗口大小改变
    mark_breathe_event_record_changed = QtCore.Signal()
    colorChanged = QtCore.Signal()

    heightChanged = QtCore.Signal(int) # 创建信号，窗口高度改变

    def __init__(self):  # 初始化 定义
        super().__init__()
        self._frame_size = FrameSizes().lookup(FrameSize.TenSec)  # 初始化 波形大小 时间是 10s
        self._canvas = None
        self._render_num_threads = 6
        self._render_executor = ThreadPoolExecutor(self._render_num_threads)
        self._previous_width = None
        self.mark_breathe_event = {"-1": "white", "0": "red", "1": "green", "2": "blue"}  # 设置字典
        self.mark_spindle_color = {"1" :"yellow"}
        self._mark_breathe_event_record = []
        self._seconds = 0
        self._wave_record=[]
        self._window_height = 600

    # noinspection PyTypeChecker
    @QtCore.Slot(int, result=float)
    def tess(self, times):
        import timeit
        return timeit.timeit(self._render, number=times)

    @property
    def _page_viewmodel(self) -> WaveformPageViewModel:
        # noinspection PyTypeChecker
        return self.property("page_viewmodel")
    def load_image(self, image_path):
        img = cv2.imread('', cv2.IMREAD_UNCHANGED)

        return img

    @property  # 使定义的函数变为属性
    def _viewmodel(self) -> WaveformAreaViewModel:  # 指定返回值为这个类型
        # noinspection PyTypeChecker
        return self.property("viewmodel")

    @QtCore.Slot()
    def auto_scroll(self):
        if self._seconds == self._page_viewmodel.seconds:
            return
        if self._page_viewmodel._project is not None and self._page_viewmodel.seconds > self.frame_size:
            self._viewmodel.scroll(self._viewmodel.scale)
            self._seconds = self._page_viewmodel.seconds

    @QtCore.Property(bool, notify=mark_breathe_event_record_changed)
    def store_mark_breathe_event(self):
        return self._mark_breathe_event_record

    @store_mark_breathe_event.setter
    def store_mark_breathe_event(self):
        if self._page_viewmodel.set_save_flag == 1:
            if self._viewmodel.get_selection() not in self._mark_breathe_event_record:
                # print(self._viewmodel.get_selection())
                self._mark_breathe_event_record.append(self._viewmodel.get_selection())
                self.mark_breathe_event_record_changed.emit()

    def paint(self, painter):
        pvm = self._page_viewmodel
        if pvm is None or not pvm.loaded:
            return
        width = self.width()
        if self._previous_width != width:
            self.update_scale()
        start_time = time.monotonic()
        img = self._render()
        height = img.height() / self.window().devicePixelRatio()
        print(img.height(),img.width())
        if abs(self.height() - height) > 2:
            self.setHeight(height)
        painter.drawImage(QRectF(0, 0, self.width(), height), img)
        # noinspection PyPropertyAccess
        if pvm.maggot_mode:  # 如果  放大镜模式打开  为true
            painter.setPen("green")  # 设置画笔 绿色
            painter.drawRect(self._viewmodel.get_selection())  # 画矩形框    里面是获取坐标
        if pvm.wave_mode:  # 如果 双模式
            painter.setPen("blue")  # 设置画笔 绿色
            painter.drawRect(self._viewmodel.get_selection())  # 画矩形框    里面是获取坐标

        painter.setPen("blue")

        for position, value in pvm.mark_breathe_event_record1.items():
            positions = position.split(",")
            x1, x2, y1, y2 = float(positions[0]), float(positions[1]), float(positions[2]), float(positions[3])
            x1, x2 = map(lambda x: x * self._viewmodel.scale, [x1 - pvm.position, x2 - pvm.position])
            painter.setOpacity(0.6)
            painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))  # 画矩形框    里面是获取坐标
            painter.fillRect(QRectF(x1, y1, x2 - x1, y2 - y1),
                             self.mark_breathe_event[value])  #

        #手工标注纺锤波
        for position, value in pvm.mark_spindle_notation_record.items():
            positions = position.split(",")
            x1, x2, y1, y2 = float(positions[0]), float(positions[1]), float(positions[2]), float(positions[3])
            x1, x2 = map(lambda x: x * self._viewmodel.scale, [x1 - pvm.position, x2 - pvm.position])
            painter.setOpacity(0.6)
            painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))  # 画矩形框    里面是获取坐标
            painter.fillRect(QRectF(x1, y1, x2 - x1, y2 - y1),
                             self.mark_spindle_color[value])


        for tuple in pvm.list1:
            # print(tuple)
            x1, y1, x2, y2 = tuple[0], tuple[1], tuple[2], tuple[3]
            x1, x2 = map(lambda x: x * self._viewmodel.scale, [x1 - pvm.position, x2 - pvm.position])
            painter.drawRect(QRectF(x1, y1, x2-x1, y2-y1 ))

        painter.setPen("black")
        for key in pvm._mark_sequence:
            painter.drawText((int(key) * 30 - pvm.position) * self._viewmodel._scale, 20, pvm._mark_sequence[key])
            painter.drawText((int(key)*30-pvm.position)*self._viewmodel._scale,20,pvm._mark_sequence[key])

        # TODO: reimplement ultra-slow operations below.
        # painter.setPen("grey")
        # if self.frame_size>5:
        #     for num in range(0,int(pvm.seconds)+1,30):
        #         snum=num-pvm.position
        #         linepos=snum*self._viewmodel._scale
        #         painter.drawLine(linepos, 0, linepos, height)
        # else:
        #     # 0.5s line
        #     for num in range(0, 2*int(pvm.seconds) + 1):
        #         snum = 0.5 + num * 0.5 - pvm.position
        #         linepos = snum * self._viewmodel._scale
        #         for i in range(0, int(height), 5):
        #             painter.drawLine(linepos, i, linepos, i + 2)

        #     # 2.5s line
        #     for num in range(0, int(pvm.seconds) + 1):
        #         snum = 2.5 + num * 2.5 - pvm.position
        #         linepos = snum * self._viewmodel._scale
        #         painter.drawLine(linepos, 0, linepos, height)

        elapsed = time.monotonic() - start_time
        self._viewmodel.record_render_time(elapsed)

    @QtCore.Slot(int)
    def scroll(self, scroll):
        if (viewmodel := self._viewmodel) is not None:
            viewmodel.scroll(scroll)

    @QtCore.Slot(int)
    def seek(self, value):
        if (pvm := self._page_viewmodel) is not None:
            pvm.seek(value)

    @QtCore.Slot(float, int)
    def zoom(self, y, amount):
        if (pvm := self._page_viewmodel) is not None and (vm := self._viewmodel) is not None:
            vm.zoom(int(y // pvm.channel_height), amount / -360)

        # 定义属性

    @QtCore.Slot(int)  # 确保添加这个装饰器
    def setWindowHeight(self, height):  # 改用驼峰命名以符合Qt惯例
        if self._window_height != height:
            self._window_height = height
            self.heightChanged.emit(height)
            print("100")
            print(f"Height updated in Python: {height}px")

    def _render(self, downsample=True, test_portion=0):
        pvm = self._page_viewmodel
        dpi = self.window().devicePixelRatio()
        logical_width = self.width()
        width = math.ceil(logical_width * dpi)
        # get data to render & downsample to screen width
        frac,_ = self._viewmodel.get_standard_fraction(
            int(logical_width) if downsample else None)
        num_channels = frac.shape[1]
        height = math.ceil(num_channels * pvm.channel_height * dpi)
        if test_portion == 4:
            return
        frac += ((np.arange(num_channels, dtype=np.float32) + .5) * self._window_height / 9 * dpi).astype(np.int32)

        # allocate canvas if needed
        # TODO: change canvas re-allocation algo to growable array's
        # i.e. grow by double, shrink by four times
        if self._canvas is None or self._canvas.shape[:2] != (height, width):
            self._canvas = img = np.zeros([height, width, 3], dtype=np.uint8)
        else:
            img = self._canvas

        # img[:] = (204,255,204)
        img = imgs[self._frame_size]
        # x = np.arange(len(frac), dtype=np.float32) * display_fs \
        #     * self._viewmodel.scale / self._viewmodel.breathe_event_detection.sampling_rate
        # x = x.astype(np.int32)
        x = np.linspace(0, len(frac) * dpi, len(frac)).astype(np.int32)
        # logger.debug(x)
        if test_portion == 3:
            return

        futures = []
        portion_size = frac.shape[0] // self._render_num_threads
        portion_offset = 0
        for _ in range(self._render_num_threads):
            new_offset = portion_offset + portion_size
            if frac.shape[0] - new_offset < portion_size:
                new_offset = frac.shape[0]
            futures.append(self._render_executor.submit(
                self._render_portion, self._page_viewmodel.colour_list,frac[portion_offset:new_offset + 1], x[portion_offset:new_offset + 1], img,
                round(dpi)))
            self._wave_record.append([frac[portion_offset:new_offset + 1], x[portion_offset:new_offset + 1], img,
                round(dpi)])
            # print("_render_portion","portion",frac[portion_offset:new_offset + 1],"xpos",x[portion_offset:new_offset + 1],"img",img,"thickness",
            #     round(dpi))
            portion_offset = new_offset
        [future.result() for future in futures]
        w, h, c = img.shape
        if test_portion == 2:
            return
        return QImage(img.data, h, w, h * c, QImage.Format_RGB888)


    # @QtCore.Slot(int, str)
    # def changeColor(self, index, colorStr):
    #     # 将颜色字符串转换为BGR格式
    #     color = QtGui.QColor(colorStr).rgb()
    #     # 将QColor的RGB值转换为OpenCV的BGR元组
    #     changeColor = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
    #     print("Changing color to:", changeColor)
    #
    #     # 确保索引有效
    #     if 0 <= index < len(self._wave_record):
    #         drawInfor = self._wave_record[index]
    #         # 使用新颜色绘制波形
    #         cv2.polylines(drawInfor[2],
    #                       [np.reshape(np.stack((drawInfor[1], drawInfor[0].T[index, :]), axis=-1), (-1, 1, 2))],
    #                       isClosed=False, color=changeColor, thickness=drawInfor[3])
    #         # 触发颜色改变信号
    #         self.colorChanged.emit()
    #         self.update()
    #     else:
    #         print("Invalid index:", index)

    @staticmethod
    def _render_portion(colors,portion, xpos, img, thickness):

        for i in range(portion.T.shape[0]):
            channel = portion.T[i, :]

            cv2.polylines(img, [np.reshape(np.stack((xpos, channel), axis=-1), (-1, 1, 2))],
                              isClosed=False, color=colors[i], thickness=thickness)


        # portion_1 = portion.T[:2,:]
        # portion_2 = portion.T[2:,:]
        # cv2.polylines(img, [np.reshape(np.stack((xpos, channel), axis=-1), (-1, 1, 2)) for channel in portion_1],
        #               isClosed=False, color=(0, 0, 0), thickness=thickness)
        # cv2.polylines(img, [np.reshape(np.stack((xpos, channel), axis=-1), (-1, 1, 2)) for channel in portion_2],
        #               isClosed=False, color=(255, 0, 0), thickness=thickness)
        # cv2.polylines(img, [np.reshape(np.stack((xpos, channel), axis=-1), (-1, 1, 2)) for channel in portion.T],
        #               isClosed=False, color=(255, 0, 0), thickness=thickness)

    # noinspection PyTypeChecker,PyCallingNonCallable
    @QtCore.Property(int, notify=frameSizeChanged)
    def frame_size(self):
        return self._frame_size

    # noinspection PyPropertyDefinition
    @frame_size.setter
    def frame_size(self, value):
        if self._frame_size != value:
            self._frame_size = value

            self.frameSizeChanged.emit()
            self.update_scale()
            self.update()

    def update_scale(self):
        # noinspection PyTypeChecker
        self._viewmodel.scale = self.width() / (FrameSizes().all[self._frame_size].value / 1000)

    # TODO: rename this to a noun.
    @QtCore.Property(list)
    def get_index(self):
        pvm = self._page_viewmodel
        logical_width = self.width()
        dpi = self.window().devicePixelRatio()

        # Ensure x1 and x2 are initialized with default values
        x1 = 0
        x2 = 0

        channel_info, x1, x2, time = self._viewmodel.get_channel()
        print('x1',x1)
        # Continue with the rest of your method implementation
        frac, frac_num = self._viewmodel.get_standard_fraction(int(logical_width))
        frac *= 3
        frac += 200
        start = 0
        if(int(x1)/self._viewmodel.scale>2):
            start = int(x1)-int(self._viewmodel.scale*2)

        end = int(x2)+int(self._viewmodel.scale*2)
        real_start = int(x1)-start
        real_end = int(x2)-start
        frac = frac[start:end].T[channel_info]
        frac_num = frac_num[start:end].T[channel_info]
        maxnum = max(frac_num)
        minnum = min(frac_num)
        maggot_data = [frac, maxnum,minnum,time,real_start,real_end,frac_num]
        return maggot_data
