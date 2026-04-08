from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

import ctypes
import sys
import math
from threading import Lock
import numpy as np
import array

import pyzed.sl as sl

M_PI = 3.1415926

VERTEX_SHADER = """
# version 330 core
layout(location = 0) in vec3 in_Vertex;
layout(location = 1) in vec4 in_Color;
uniform mat4 u_mvpMatrix;
out vec4 b_color;
void main() {
    b_color = in_Color;
    gl_Position = u_mvpMatrix * vec4(in_Vertex, 1);
}
"""

FRAGMENT_SHADER = """
# version 330 core
in vec4 b_color;
layout(location = 0) out vec4 out_Color;
void main() {
   out_Color = b_color;
}
"""





def safe_glutBitmapString(font, str_):
    for i in range(len(str_)):
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(str_[i]))

class Shader:
    def __init__(self, _vs, _fs):

        self.program_id = glCreateProgram()
        vertex_id = self.compile(GL_VERTEX_SHADER, _vs)
        fragment_id = self.compile(GL_FRAGMENT_SHADER, _fs)

        glAttachShader(self.program_id, vertex_id)
        glAttachShader(self.program_id, fragment_id)
        glBindAttribLocation( self.program_id, 0, "in_vertex")
        glBindAttribLocation( self.program_id, 1, "in_texCoord")
        glLinkProgram(self.program_id)

        if glGetProgramiv(self.program_id, GL_LINK_STATUS) != GL_TRUE:
            info = glGetProgramInfoLog(self.program_id)
            if (self.program_id is not None) and (self.program_id > 0) and glIsProgram(self.program_id):
                glDeleteProgram(self.program_id)
            if (vertex_id is not None) and (vertex_id > 0) and glIsShader(vertex_id):
                glDeleteShader(vertex_id)
            if (fragment_id is not None) and (fragment_id > 0) and glIsShader(fragment_id):
                glDeleteShader(fragment_id)
            raise RuntimeError('Error linking program: %s' % (info))
        if (vertex_id is not None) and (vertex_id > 0) and glIsShader(vertex_id):
            glDeleteShader(vertex_id)
        if (fragment_id is not None) and (fragment_id > 0) and glIsShader(fragment_id):
            glDeleteShader(fragment_id)

    def compile(self, _type, _src):
        try:
            shader_id = glCreateShader(_type)
            if shader_id == 0:
                print("ERROR: shader type {0} does not exist".format(_type))
                exit()

            glShaderSource(shader_id, _src)
            glCompileShader(shader_id)
            if glGetShaderiv(shader_id, GL_COMPILE_STATUS) != GL_TRUE:
                info = glGetShaderInfoLog(shader_id)
                if (shader_id is not None) and (shader_id > 0) and glIsShader(shader_id):
                    glDeleteShader(shader_id)
                raise RuntimeError('Shader compilation failed: %s' % (info))
            return shader_id
        except:
            if (shader_id is not None) and (shader_id > 0) and glIsShader(shader_id):
                glDeleteShader(shader_id)
            raise

    def get_program_id(self):
        return self.program_id


class Simple3DObject:
    def __init__(self, _is_static):
        self.vaoID = 0
        self.drawing_type = GL_TRIANGLES
        self.is_static = _is_static
        self.elementbufferSize = 0

        self.vertices = array.array('f')
        self.colors = array.array('f')
        self.indices = array.array('I')

    def add_pt(self, _pts):  # _pts [x,y,z]
        for pt in _pts:
            self.vertices.append(pt)

    def add_clr(self, _clrs):    # _clr [r,g,b]
        for clr in _clrs:
            self.colors.append(clr)

    def add_point_clr(self, _pt, _clr):
        self.add_pt(_pt)
        self.add_clr(_clr)
        self.indices.append(len(self.indices))

    def add_line(self, _p1, _p2, _clr):
        self.add_point_clr(_p1, _clr)
        self.add_point_clr(_p2, _clr)

    def push_to_GPU(self):
        self.vboID = glGenBuffers(4)

        if len(self.vertices):
            glBindBuffer(GL_ARRAY_BUFFER, self.vboID[0])
            glBufferData(GL_ARRAY_BUFFER, len(self.vertices) * self.vertices.itemsize, (GLfloat * len(self.vertices))(*self.vertices), GL_STATIC_DRAW)

        if len(self.colors):
            glBindBuffer(GL_ARRAY_BUFFER, self.vboID[1])
            glBufferData(GL_ARRAY_BUFFER, len(self.colors) * self.colors.itemsize, (GLfloat * len(self.colors))(*self.colors), GL_STATIC_DRAW)

        if len(self.indices):
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.vboID[2])
            glBufferData(GL_ELEMENT_ARRAY_BUFFER,len(self.indices) * self.indices.itemsize,(GLuint * len(self.indices))(*self.indices), GL_STATIC_DRAW)

        self.elementbufferSize = len(self.indices)

    def clear(self):
        self.vertices = array.array('f')
        self.colors = array.array('f')
        self.indices = array.array('I')
        self.elementbufferSize = 0

    def set_drawing_type(self, _type):
        self.drawing_type = _type

    def draw(self):
        if (self.elementbufferSize):
            glEnableVertexAttribArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, self.vboID[0])
            glVertexAttribPointer(0,3,GL_FLOAT,GL_FALSE,0,None)

            glEnableVertexAttribArray(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.vboID[1])
            glVertexAttribPointer(1,3,GL_FLOAT,GL_FALSE,0,None)

            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.vboID[2])
            glDrawElements(self.drawing_type, self.elementbufferSize, GL_UNSIGNED_INT, None)

            glDisableVertexAttribArray(0)
            glDisableVertexAttribArray(1)

def addVert(obj, i_f, limit, clr) :
    obj.add_line([i_f, 0, -limit], [i_f, 0, limit], clr)
    obj.add_line([-limit, 0, i_f],[limit, 0, i_f], clr)

class GLViewer:
    def __init__(self):
        self.available = False
        self.mutex = Lock()
        self.camera = CameraGL()
        self.wheelPosition = 0.
        self.mouse_button = [False, False]
        self.mouseCurrentPosition = [0., 0.]
        self.previousMouseMotion = [0., 0.]
        self.mouseMotion = [0., 0.]
        self.pose = sl.Transform()
        self.trackState = None
        self.txtT = ""
        self.txtR = ""

        self.plane_arrow = None
        self.depth_disp_val = 0.0  # 右上角显示的（滤波后）深度（米）

        # --- 初始化杆末端的坐标 (Y, Z)，单位: 米 ---
        self.y_tip = -0.9
        self.z_tip = 0.0



    def init(self, camera_model): # _params = sl.CameraParameters
        glutInit()
        wnd_w = int(glutGet(GLUT_SCREEN_WIDTH)*0.9)
        wnd_h = int(glutGet(GLUT_SCREEN_HEIGHT) *0.9)
        glutInitWindowSize(wnd_w, wnd_h)
        glutInitWindowPosition(int(wnd_w*0.05), int(wnd_h*0.05))

        glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)
        glutCreateWindow(b"ZED Positional Tracking")
        glViewport(0, 0, wnd_w, wnd_h)

        glutSetOption(GLUT_ACTION_ON_WINDOW_CLOSE,
                      GLUT_ACTION_CONTINUE_EXECUTION)

        glEnable(GL_DEPTH_TEST)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        # Compile and create the shader for 3D objects
        self.shader_image = Shader(VERTEX_SHADER, FRAGMENT_SHADER)
        self.shader_MVP = glGetUniformLocation(self.shader_image.get_program_id(), "u_mvpMatrix")

        self.bckgrnd_clr = np.array([223/255., 230/255., 233/255.])

        # Create the bounding box object
        self.floor_grid = Simple3DObject(False)
        self.floor_grid.set_drawing_type(GL_LINES)

        limit = 20
        clr1 = np.array([218/255., 223/255., 225/255.])
        clr2 = np.array([108/255., 122/255., 137/255.])

        for i in range (limit * -5, limit * 5):
            i_f = i / 5.
            if((i % 5) == 0):
                addVert(self.floor_grid, i_f, limit, clr2)
            else:
                addVert(self.floor_grid, i_f, limit, clr1)
        self.floor_grid.push_to_GPU()

        self.zedPath = Simple3DObject(False)
        self.zedPath.set_drawing_type(GL_LINE_STRIP)

        self.zedModel = Simple3DObject(False)

        # Create the camera model
        Z_ = -0.3 #size
        Y_ = Z_ * math.tan(95. * M_PI / 180. / 2.)
        X_ = Y_ * 16./9.

        A = np.array([0, 0, 0])
        B = np.array([X_, Y_, Z_])
        C = np.array([-X_, Y_, Z_])
        D = np.array([-X_, -Y_, Z_])
        E = np.array([X_, -Y_, Z_])

        lime_clr = np.array([217 / 255, 255/255, 66/255])

        self.zedModel.add_line(A, B, lime_clr)
        self.zedModel.add_line(A, C, lime_clr)
        self.zedModel.add_line(A, D, lime_clr)
        self.zedModel.add_line(A, E, lime_clr)

        self.zedModel.add_line(B, C, lime_clr)
        self.zedModel.add_line(C, D, lime_clr)
        self.zedModel.add_line(D, E, lime_clr)
        self.zedModel.add_line(E, B, lime_clr)

        self.zedModel.set_drawing_type(GL_LINES)
        self.zedModel.push_to_GPU()

        # --- Create a fixed pole relative to the camera ---
        self.poleModel = Simple3DObject(False)
        self.poleModel.set_drawing_type(GL_LINES)
        # 这里调用我们新增的方法进行初始化
        INIT_LEN = -0.76
        INIT_ANG_DEG = 48.0
        self.set_pole_by_length_angle(INIT_LEN, INIT_ANG_DEG)

        # Register GLUT callback functions
        glutDisplayFunc(self.draw_callback)
        glutIdleFunc(self.idle)
        glutKeyboardFunc(self.keyPressedCallback)
        glutCloseFunc(self.close_func)
        glutMouseFunc(self.on_mouse)
        glutMotionFunc(self.on_mousemove)
        glutReshapeFunc(self.on_resize)

        self.available = True

    def is_available(self):
        if self.available:
            glutMainLoopEvent()
        return self.available

    def updateData(self, zed_rt, str_t, str_r, state):
        self.mutex.acquire()
        self.pose = zed_rt
        self.zedPath.add_point_clr(zed_rt.get_translation().get(), [0.1,0.36,0.84])
        self.trackState = state
        self.txtT = str_t
        self.txtR = str_r
        self.mutex.release()

    def idle(self):
        if self.available:
            glutPostRedisplay()

    def exit(self):
        if self.available:
            self.available = False

    def close_func(self):
        if self.available:
            self.available = False

    def keyPressedCallback(self, key, x, y):
        step = 0.02  # y/z 微调步长 (m)
        ang_step = 1.0  # 角度微调步长 (deg)
        len_step = 0.002  # 长度微调步长 (m)
        updated = False

        # ---- 现有的 y/z 微调（保留）----
        if key == b'w':  # z 减小（向前）
            self.z_tip -= step;
            updated = True
        elif key == b's':  # z 增大（向后）
            self.z_tip += step;
            updated = True
        elif key == b'a':  # y 增大（向上）
            self.y_tip += step;
            updated = True
        elif key == b'd':  # y 减小（向下）
            self.y_tip -= step;
            updated = True
        elif key == b'r':  # 重置为一组默认 yz
            self.set_pole_by_length_angle(-1.02, 45.0)  # 或者还原到你的默认
            return
        elif ord(key) == 27:  # ESC
            self.close_func();
            return

        # ---- 可选：角度/长度微调（J/L: 角度, I/K: 长度）----
        elif key == b'j':  # 角度 -
            self.pole_angle_deg -= ang_step
            self.set_pole_by_length_angle(self.pole_length, self.pole_angle_deg)
            return
        elif key == b'l':  # 角度 +
            self.pole_angle_deg += ang_step
            self.set_pole_by_length_angle(self.pole_length, self.pole_angle_deg)
            return
        elif key == b'i':  # 长度 +
            self.pole_length = max(0.0, self.pole_length + len_step)
            self.set_pole_by_length_angle(self.pole_length, self.pole_angle_deg)
            return
        elif key == b'k':  # 长度 -
            self.pole_length = max(0.0, self.pole_length - len_step)
            self.set_pole_by_length_angle(self.pole_length, self.pole_angle_deg)
            return

        if updated:
            self.update_pole_geometry()

    def on_mouse(self,*args,**kwargs):
        (key,Up,x,y) = args
        if key==0:
            self.mouse_button[0] = (Up == 0)
        elif key==2 :
            self.mouse_button[1] = (Up == 0)
        elif(key == 3):
            self.wheelPosition = self.wheelPosition + 1
        elif(key == 4):
            self.wheelPosition = self.wheelPosition - 1

        self.mouseCurrentPosition = [x, y]
        self.previousMouseMotion = [x, y]

    def on_mousemove(self,*args,**kwargs):
        (x,y) = args
        self.mouseMotion[0] = x - self.previousMouseMotion[0]
        self.mouseMotion[1] = y - self.previousMouseMotion[1]
        self.previousMouseMotion = [x, y]
        glutPostRedisplay()

    def on_resize(self,Width,Height):
        glViewport(0, 0, Width, Height)
        self.camera.setProjection(Height / Width)

    def draw_callback(self):
        if self.available:
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glClearColor(self.bckgrnd_clr[0], self.bckgrnd_clr[1], self.bckgrnd_clr[2], 1.)

            self.mutex.acquire()
            self.update()
            self.draw()
            self.print_text()
            self.mutex.release()

            glutSwapBuffers()
            glutPostRedisplay()

    def update(self):
        self.zedPath.push_to_GPU()

        if(self.mouse_button[0]):
            r = sl.Rotation()
            vert=self.camera.vertical_
            tmp = vert.get()
            vert.init_vector(tmp[0] * -1.,tmp[1] * -1., tmp[2] * -1.)
            r.init_angle_translation(self.mouseMotion[0] * 0.002, vert)
            self.camera.rotate(r)

            r.init_angle_translation(self.mouseMotion[1] * 0.002, self.camera.right_)
            self.camera.rotate(r)

        if(self.mouse_button[1]):
            t = sl.Translation()
            tmp = self.camera.right_.get()
            scale = self.mouseMotion[0] * -0.01
            t.init_vector(tmp[0] * scale, tmp[1] * scale, tmp[2] * scale)
            self.camera.translate(t)

            tmp = self.camera.up_.get()
            scale = self.mouseMotion[1] * 0.01
            t.init_vector(tmp[0] * scale, tmp[1] * scale, tmp[2] * scale)
            self.camera.translate(t)

        if (self.wheelPosition != 0):
            t = sl.Translation()
            tmp = self.camera.forward_.get()
            scale = self.wheelPosition * -0.065
            t.init_vector(tmp[0] * scale, tmp[1] * scale, tmp[2] * scale)
            self.camera.translate(t)


        self.camera.update()

        self.mouseMotion = [0., 0.]
        self.wheelPosition = 0

    def set_pole_by_length_angle(self, length, angle_deg):
        """按杆长和角度设置末端点；角度相对 +Z 轴，朝 +Y 为正（与 atan2(y, z) 保持一致）"""
        angle_rad = math.radians(angle_deg)
        self.y_tip = length * math.sin(angle_rad)
        self.z_tip = length * math.cos(angle_rad)
        self.update_pole_geometry()


    def update_pole_geometry(self):
        """根据当前 y_tip, z_tip 更新杆的长度、角度、三刀盘位置"""
        self.poleModel.clear()

        y_tip = self.y_tip
        z_tip = self.z_tip

        # === 计算长度与角度 ===
        pole_length = math.sqrt(y_tip**2 + z_tip**2)
        angle_rad = math.atan2(y_tip, z_tip)
        angle_deg = math.degrees(angle_rad)

        self.pole_length = pole_length
        self.pole_angle_deg = angle_deg

        # === 重新定义杆在相机坐标系中的位置 ===
        start_local = np.array([0.0, 0.0, 0.0])
        end_local = np.array([0.0, y_tip, z_tip])

        pole_clr = np.array([1.0, 0.5, 0.0])  # 橙色杆
        self.poleModel.add_line(start_local, end_local, pole_clr)
        self.pole_end = end_local

        self.poleModel.push_to_GPU()
        print(f"[Update] Pole tip=({y_tip:.3f},{z_tip:.3f}), L={pole_length:.3f}m, θ={angle_deg:.2f}°")




    def draw(self):
        glPointSize(1.)
        glUseProgram(self.shader_image.get_program_id())

        vpMatrix = self.camera.getViewProjectionMatrix()
        glUniformMatrix4fv(self.shader_MVP, 1, GL_TRUE,  (GLfloat * len(vpMatrix))(*vpMatrix))

        glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        glLineWidth(2)
        self.zedPath.draw()
        self.floor_grid.draw()

        vpMatrix = self.camera.getViewProjectionMatrixRT(self.pose)
        glUniformMatrix4fv(self.shader_MVP, 1, GL_FALSE,  (GLfloat * len(vpMatrix))(*vpMatrix))

        glLineWidth(6)  # 把相机视觉框线加粗，比如 6 像素

        self.zedModel.draw()
        self.poleModel.draw()

        # --- 绘制沿法向量方向阵列的三刀盘结构 ---
        glDisableVertexAttribArray(1)
        glVertexAttrib4f(1, 0.6, 0.6, 0.6, 1.0)  # 灰色圆盘

        if hasattr(self, "pole_end"):
            center = np.array(self.pole_end, dtype=float)
            radius = 0.085  # 单个刀盘半径
            spacing = 0.25  # 三刀盘前后间距
            segments = 60

            # ✅ 刀盘法向量方向 = X 轴（或根据需求改为 Y/Z）
            normal = np.array([1.0, 0.0, 0.0], dtype=float)

            # 平面内两个正交方向（确定圆形轮廓）
            up = np.array([0.0, 1.0, 0.0], dtype=float)
            right = np.cross(normal, up)
            right /= np.linalg.norm(right)
            up /= np.linalg.norm(up)

            # ✅ 计算三个刀盘的中心点（沿 normal 前后排列）
            centers = [
                center - normal * spacing,  # 后刀盘
                center,  # 中间刀盘
                center + normal * spacing  # 前刀盘
            ]

            # --- 绘制三个圆盘 ---
            for c in centers:
                glBegin(GL_TRIANGLE_FAN)
                glVertex3f(*c)
                for i in range(segments + 1):
                    theta = 2.0 * math.pi * i / segments
                    point = c + radius * (math.cos(theta) * up + math.sin(theta) * right)
                    glVertex3f(*point)
                glEnd()

            # --- 绘制连接轴（沿法向量方向）---
            glVertexAttrib4f(1, 0.3, 0.3, 0.3, 1.0)  # 深灰色轴
            glLineWidth(8)
            glBegin(GL_LINES)
            glVertex3f(*(centers[0]))
            glVertex3f(*(centers[2]))
            glEnd()

            # --- 绘制外轮廓线（增强立体感）---
            glVertexAttrib4f(1, 0.0, 0.0, 0.0, 1.0)
            glLineWidth(2)
            for c in centers:
                glBegin(GL_LINE_LOOP)
                for i in range(segments):
                    theta = 2.0 * math.pi * i / segments
                    point = c + radius * (math.cos(theta) * up + math.sin(theta) * right)
                    glVertex3f(*point)
                glEnd()


        # --- 绘制平面法向量箭头 ---
        if self.plane_arrow is not None:
            start, end = self.plane_arrow

            # 让 attribute(1)=in_Color 使用常量颜色（橙红）
            glDisableVertexAttribArray(1)  # 关键：禁用数组，让常量生效
            glVertexAttrib4f(1, 1.0, 0.3, 0.0, 1.0)  # 关键：设置 in_Color 常量

            # --- 主箭头线 ---
            glLineWidth(10)
            glBegin(GL_LINES)
            glVertex3f(*start)
            glVertex3f(*end)
            glEnd()

            # --- 箭头尖端 ---
            direction = np.array(end) - np.array(start)
            direction /= np.linalg.norm(direction)
            tip_length = 0.2
            base = np.array(end) - direction * tip_length
            up = np.array([0, 1, 0])
            if abs(np.dot(up, direction)) > 0.9:
                up = np.array([1, 0, 0])
            right = np.cross(direction, up);
            right /= np.linalg.norm(right)
            up = np.cross(right, direction)

            tip_size = 0.2
            p1 = base + right * tip_size
            p2 = base - right * tip_size
            p3 = base + up * tip_size

            glBegin(GL_TRIANGLES)
            glVertex3f(*p1);
            glVertex3f(*p2);
            glVertex3f(*end)
            glVertex3f(*p1);
            glVertex3f(*p3);
            glVertex3f(*end)
            glEnd()

            # --- 绘制法向量所在平面 ---
            # 改成给 attribute(1) 设“半透明天蓝”常量
            glVertexAttrib4f(1, 0.3, 0.7, 1.0, 0.3)  # 关键：设置平面的 in_Color 常量（含透明度）

            glBegin(GL_QUADS)
            normal = direction
            ref_up = np.array([0, 1, 0]) if abs(np.dot(normal, [0, 1, 0])) < 0.9 else np.array([1, 0, 0])
            right = np.cross(normal, ref_up);
            right /= np.linalg.norm(right)
            up = np.cross(right, normal);
            up /= np.linalg.norm(up)

            plane_size = tip_length * 6

            c = np.array(start)
            q1 = c + right * plane_size + up * plane_size
            q2 = c - right * plane_size + up * plane_size
            q3 = c - right * plane_size - up * plane_size
            q4 = c + right * plane_size - up * plane_size

            glVertex3f(*q1);
            glVertex3f(*q2);
            glVertex3f(*q3);
            glVertex3f(*q4)
            glEnd()

        # ==============================================================
        # === 绘制左下角相机坐标系（实时更新） =========================
        # ==============================================================
        try:
            # 🔸关闭当前着色器，启用固定管线模式
            glUseProgram(0)

            # 进入2D正交投影
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            w_wnd = glutGet(GLUT_WINDOW_WIDTH)
            h_wnd = glutGet(GLUT_WINDOW_HEIGHT)
            glOrtho(0, w_wnd, 0, h_wnd, -1., 1.)

            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()

            glDisable(GL_DEPTH_TEST)
            glLineWidth(4.0)

            # 屏幕原点与长度（像素）
            origin_x = 100
            origin_y = 100
            axis_len = 60

            # === 从当前相机姿态提取旋转矩阵 ===
            if hasattr(self, "pose") and self.pose is not None:
                try:
                    rot = np.array(self.pose.get_rotation_matrix().r)
                    if rot.shape == (3, 3):
                        x_dir = rot[:, 0]
                        y_dir = rot[:, 1]
                        z_dir = rot[:, 2]
                    else:
                        x_dir, y_dir, z_dir = np.eye(3)
                except Exception as e:
                    print(f"[Warn] rotation matrix read failed: {e}")
                    x_dir, y_dir, z_dir = np.eye(3)
            else:
                x_dir, y_dir, z_dir = np.eye(3)

            # === 绘制三轴 ===
            glBegin(GL_LINES)
            # X轴
            glColor3f(1.0, 0.0, 0.0)
            glVertex2f(origin_x, origin_y)
            glVertex2f(origin_x + x_dir[0] * axis_len,
                       origin_y + x_dir[1] * axis_len)

            # Y轴
            glColor3f(0.0, 1.0, 0.0)
            glVertex2f(origin_x, origin_y)
            glVertex2f(origin_x + y_dir[0] * axis_len,
                       origin_y + y_dir[1] * axis_len)

            # Z轴
            glColor3f(0.0, 0.0, 1.0)
            glVertex2f(origin_x, origin_y)
            glVertex2f(origin_x + z_dir[0] * axis_len,
                       origin_y + z_dir[1] * axis_len)
            glEnd()

            # === 添加坐标轴文字标注 ===
            def draw_label(x, y, text, color):
                glColor3f(*color)
                glRasterPos2f(x, y)
                for ch in text:
                    glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))

            draw_label(origin_x + x_dir[0] * axis_len + 5,
                       origin_y + x_dir[1] * axis_len + 5, "X", (1.0, 0.0, 0.0))
            draw_label(origin_x + y_dir[0] * axis_len + 5,
                       origin_y + y_dir[1] * axis_len + 5, "Y", (0.0, 1.0, 0.0))
            draw_label(origin_x + z_dir[0] * axis_len + 5,
                       origin_y + z_dir[1] * axis_len + 5, "Z", (0.0, 0.0, 1.0))

            # 恢复状态
            glEnable(GL_DEPTH_TEST)
            glMatrixMode(GL_MODELVIEW)
            glPopMatrix()
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)

        except Exception as e:
            print(f"[Error] Drawing mini coordinate failed: {e}")

        glUseProgram(0)

    def print_text(self):
        if self.trackState is not None:
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            w_wnd = glutGet(GLUT_WINDOW_WIDTH)
            h_wnd = glutGet(GLUT_WINDOW_HEIGHT)
            glOrtho(0, w_wnd, 0, h_wnd, -1., 1.)

            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()

            start_w = 20
            start_h = h_wnd - 40

            glColor3f(0.2, 0.65, 0.2)
            glRasterPos2i(start_w, start_h)
            safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18,  "POSITIONAL TRACKING STATUS: " + str(self.trackState.tracking_fusion_status))

            dark_clr = 0.12
            glColor3f(dark_clr, dark_clr, dark_clr)
            glRasterPos2i(start_w, start_h - 40)
            safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, "Translation (m) :")

            glColor3f(0.4980, 0.5490, 0.5529)
            glRasterPos2i(155, start_h - 40)

            safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, self.txtT)

            glColor3f(dark_clr, dark_clr, dark_clr)
            glRasterPos2i(start_w, start_h - 60)
            safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, "Rotation   (rad) :")

            glColor3f(0.4980, 0.5490, 0.5529)
            glRasterPos2i(155, start_h - 60)
            safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, self.txtR)

            # --- 显示杆子初始化信息（角度和长度） ---
            glColor3f(0.12, 0.12, 0.12)
            glRasterPos2i(start_w, start_h - 150)
            safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, "Pole Initialization:")

            glColor3f(0.0, 0.2, 0.8)
            glRasterPos2i(200, start_h - 170)
            safe_glutBitmapString(
                GLUT_BITMAP_HELVETICA_18,
                f"Angle = {self.pole_angle_deg:.2f}°, Length = {self.pole_length:.2f} m"
            )

            # --- 在左侧相机信息下方显示平面法向量 ---
            if self.plane_arrow is not None:
                start, end = self.plane_arrow
                normal = np.array(end) - np.array(start)
                normal /= np.linalg.norm(normal)

                glColor3f(0.12, 0.12, 0.12)
                glRasterPos2i(start_w, start_h - 90)
                safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, "Plane Normal (x, y, z):")

                glColor3f(0.0, 0.2, 0.8)
                glRasterPos2i(200, start_h - 90)
                safe_glutBitmapString(
                    GLUT_BITMAP_HELVETICA_18,
                    f"({normal[0]:.3f}, {normal[1]:.3f}, {normal[2]:.3f})"
                )

                glColor3f(0.12, 0.12, 0.12)
                glRasterPos2i(start_w, start_h - 110)
                safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, "Plane Center:")

                glColor3f(0.0, 0.5, 0.0)
                glRasterPos2i(200, start_h - 110)
                safe_glutBitmapString(
                    GLUT_BITMAP_HELVETICA_18,
                    f"({start[0]:.2f}, {start[1]:.2f}, {start[2]:.2f})"
                )

                # --- 计算杆底端到平面距离（减去圆盘半径）---
                if self.plane_arrow is not None and hasattr(self, "pole_end"):
                    start, end = self.plane_arrow
                    plane_center = np.array(start, dtype=float)
                    plane_normal = np.array(end, dtype=float) - plane_center
                    plane_normal /= np.linalg.norm(plane_normal)

                    pole_end = np.array(self.pole_end, dtype=float)
                    radius = 0.12  # 与圆盘半径一致

                    # 平面到点的距离
                    dist = np.dot(plane_normal, (pole_end - plane_center))  # ✅ 保留符号
                    dist_adjusted = dist - radius

                    glColor3f(0.2, 0.1, 0.1)
                    glRasterPos2i(start_w, start_h - 130)
                    safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, "Distance to Plane (m):")

                    glColor3f(0.7, 0.0, 0.0)
                    glRasterPos2i(250, start_h - 130)
                    safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, f"{dist_adjusted:.3f}")


                    # --- 绘制右上角二维视图：刀盘与平面距离示意 ---
                    # --- 计算杆底端到平面距离（减去圆盘半径）---  (替换版：统一用“有符号距离”，并驱动右上角简化指示器)
                    if self.plane_arrow is not None and hasattr(self, "pole_end"):
                        start, end = self.plane_arrow
                        plane_center = np.array(start, dtype=float)
                        plane_normal = np.array(end, dtype=float) - plane_center
                        nrm = np.linalg.norm(plane_normal)
                        if nrm < 1e-9:
                            plane_normal = np.array([0., 1., 0.], dtype=float)
                        else:
                            plane_normal /= nrm

                        pole_end = np.array(self.pole_end, dtype=float)
                        radius_phys = 0.12  # 与3D刀盘半径一致（仅用于深度定义）

                        # 1) 有符号距离：相机杆端到平面的符号距离 (米)
                        dist_signed = float(np.dot(plane_normal, (pole_end - plane_center)))

                        # 2) 定义“耕作深度”：与之前一致 = 点到平面距离 - 圆盘半径
                        depth_val = dist_signed - radius_phys

                        # 3) 死区 + 低通（降低敏感度）
                        deadband = 0.005  # 5mm 死区
                        if abs(depth_val) < deadband:
                            depth_val = 0.0
                        alpha = 0.88  # 低通系数(0.85~0.92可调)
                        self.depth_disp_val = alpha * self.depth_disp_val + (1.0 - alpha) * depth_val

                        # 4) 左上角数值显示（使用“未滤波”的 depth_val，实时）
                        glColor3f(0.2, 0.1, 0.1)
                        glRasterPos2i(start_w, start_h - 130)
                        safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, "Distance to Plane (m):")

                        glColor3f(0.7, 0.0, 0.0)
                        glRasterPos2i(250, start_h - 130)
                        safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, f"{depth_val:+.3f}")  # 与右上角用同一物理定义

                        # ---------------- 右上角二维“指示器”视图（不再保真实尺寸，仅指示方向与大小）----------------
                        # 0) 先在2D正交下绘制（避免被3D深度遮挡）
                        glDisable(GL_DEPTH_TEST)
                        glEnable(GL_BLEND)
                        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

                        # --- 设置2D正交投影 ---
                        glMatrixMode(GL_PROJECTION)
                        glPushMatrix()
                        glLoadIdentity()
                        w_wnd = glutGet(GLUT_WINDOW_WIDTH)
                        h_wnd = glutGet(GLUT_WINDOW_HEIGHT)
                        glOrtho(0, w_wnd, 0, h_wnd, -1., 1.)

                        glMatrixMode(GL_MODELVIEW)
                        glPushMatrix()
                        glLoadIdentity()

                        # 1) 视窗与布局
                        view_w = int(w_wnd * 0.28)  # 视窗稍大，扩大可视行程
                        view_h = int(h_wnd * 0.30)
                        margin = 20
                        origin_x = w_wnd - view_w - margin
                        origin_y = h_wnd - view_h - margin

                        # 蓝色“地平”线位置（固定）
                        plane_y = origin_y + int(view_h * 0.28)

                        # 2) 固定像素圆盘半径（与真实物理半径脱钩，只保颜色/外观）
                        CIRCLE_R_PX = 24

                        # 3) 行程/比例尺：让 ±Dmax 的深度覆盖约 70% 的视窗高度
                        Dmax = 0.30  # 米，可根据你期望的显示“程”度调整
                        SCALE_PX_PER_M = 0.70 * view_h / (2.0 * Dmax)

                        # 4) “0相切”的圆心位置映射：深度=0时圆盘底部刚好与蓝线相切
                        #    圆心y = 线y + 圆半径 + 映射位移
                        depth_px = self.depth_disp_val * SCALE_PX_PER_M
                        circle_y = plane_y + CIRCLE_R_PX + depth_px

                        # 5) 末端裁剪（避免出框，但不要过早夹死）
                        min_y = origin_y + CIRCLE_R_PX + 4
                        max_y = origin_y + view_h - CIRCLE_R_PX - 4
                        circle_y = max(min_y, min(max_y, circle_y))

                        # ===== 绘制开始 =====
                        # 背景白框（半透明）
                        glColor4f(1.0, 1.0, 1.0, 0.80)
                        glBegin(GL_QUADS)
                        glVertex2f(origin_x, origin_y)
                        glVertex2f(origin_x + view_w, origin_y)
                        glVertex2f(origin_x + view_w, origin_y + view_h)
                        glVertex2f(origin_x, origin_y + view_h)
                        glEnd()

                        # 边框
                        glColor3f(0.7, 0.7, 0.7)
                        glLineWidth(2)
                        glBegin(GL_LINE_LOOP)
                        glVertex2f(origin_x, origin_y)
                        glVertex2f(origin_x + view_w, origin_y)
                        glVertex2f(origin_x + view_w, origin_y + view_h)
                        glVertex2f(origin_x, origin_y + view_h)
                        glEnd()

                        # 蓝线（平面）
                        glColor3f(0.2, 0.6, 1.0)
                        glLineWidth(3)
                        glBegin(GL_LINES)
                        glVertex2f(origin_x + 20, plane_y)
                        glVertex2f(origin_x + view_w - 20, plane_y)
                        glEnd()

                        # 灰色圆盘（固定像素半径）
                        glColor3f(0.6, 0.6, 0.6)
                        circle_radius = float(CIRCLE_R_PX)
                        glBegin(GL_TRIANGLE_FAN)
                        glVertex2f(origin_x + view_w / 2, circle_y)
                        for i in range(0, 361, 10):
                            theta = math.radians(i)
                            x = origin_x + view_w / 2 + circle_radius * math.cos(theta)
                            y = circle_y + circle_radius * math.sin(theta)
                            glVertex2f(x, y)
                        glEnd()

                        # 黑色轮廓
                        glColor3f(0.0, 0.0, 0.0)
                        glLineWidth(1.8)
                        glBegin(GL_LINE_LOOP)
                        for i in range(0, 361, 10):
                            theta = math.radians(i)
                            x = origin_x + view_w / 2 + circle_radius * math.cos(theta)
                            y = circle_y + circle_radius * math.sin(theta)
                            glVertex2f(x, y)
                        glEnd()

                        # 标题与数值（数值建议显示未滤波的 depth_val，保证与左上角一致）
                        glColor3f(0.1, 0.1, 0.1)
                        glRasterPos2i(origin_x + 10, origin_y + view_h - 25)
                        safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, "Tillage Depth:")

                        glColor3f(0.85, 0.85, 0.85)
                        glLineWidth(1)
                        glBegin(GL_LINES)
                        glVertex2f(origin_x + 10, origin_y + view_h - 30)
                        glVertex2f(origin_x + view_w - 10, origin_y + view_h - 30)
                        glEnd()

                        # 颜色：正(上)为绿，负(下)为红
                        if depth_val < 0:
                            glColor3f(1.0, 0.0, 0.0)
                        else:
                            glColor3f(0.0, 0.6, 0.0)

                        glRasterPos2i(origin_x + 120, origin_y + view_h - 25)
                        safe_glutBitmapString(GLUT_BITMAP_HELVETICA_18, f"{depth_val:+.3f} m")

                        # --- 恢复矩阵与状态 ---
                        glMatrixMode(GL_MODELVIEW)
                        glPopMatrix()
                        glMatrixMode(GL_PROJECTION)
                        glPopMatrix()
                        glMatrixMode(GL_MODELVIEW)
                        glEnable(GL_DEPTH_TEST)

            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
            glPopMatrix()

    def update_plane_vector(self, center, normal):
        """更新当前法向量箭头"""
        if center is None or normal is None:
            self.plane_arrow = None
            return
        start = np.array(center)
        end = start + np.array(normal) * 0.5  # 放大系数可调
        self.plane_arrow = (start, end)


class CameraGL:
    def __init__(self):
        self.ORIGINAL_FORWARD = sl.Translation()
        self.ORIGINAL_FORWARD.init_vector(0,0,1)
        self.ORIGINAL_UP = sl.Translation()
        self.ORIGINAL_UP.init_vector(0,1,0)
        self.ORIGINAL_RIGHT = sl.Translation()
        self.ORIGINAL_RIGHT.init_vector(1,0,0)
        self.znear = 0.5
        self.zfar = 100.
        self.horizontalFOV = 70.
        self.orientation_ = sl.Orientation()
        self.position_ = sl.Translation()
        self.forward_ = sl.Translation()
        self.up_ = sl.Translation()
        self.right_ = sl.Translation()
        self.vertical_ = sl.Translation()
        self.vpMatrix_ = sl.Matrix4f()
        self.projection_ = sl.Matrix4f()
        self.projection_.set_identity()
        self.setProjection(1.78)

        self.position_.init_vector(0., 2., -1.)
        tmp = sl.Translation()
        tmp.init_vector(0, 0, 4)
        tmp2 = sl.Translation()
        tmp2.init_vector(0, 1, 0)
        self.setDirection(tmp, tmp2)
        cam_rot = sl.Rotation()
        cam_rot.set_euler_angles(-50., 0., 0., False)
        self.setRotation(cam_rot)

    def update(self):
        dot_ = sl.Translation.dot_translation(self.vertical_, self.up_)
        if(dot_ < 0.):
            tmp = self.vertical_.get()
            self.vertical_.init_vector(tmp[0] * -1.,tmp[1] * -1., tmp[2] * -1.)
        transformation = sl.Transform()
        transformation.init_orientation_translation(self.orientation_, self.position_)
        transformation.inverse()
        self.vpMatrix_ = self.projection_ * transformation

    def setProjection(self, im_ratio):
        fov_x = self.horizontalFOV * 3.1416 / 180.
        fov_y = self.horizontalFOV * im_ratio * 3.1416 / 180.

        self.projection_[(0,0)] = 1. / math.tan(fov_x * .5)
        self.projection_[(1,1)] = 1. / math.tan(fov_y * .5)
        self.projection_[(2,2)] = -(self.zfar + self.znear) / (self.zfar - self.znear)
        self.projection_[(3,2)] = -1.
        self.projection_[(2,3)] = -(2. * self.zfar * self.znear) / (self.zfar - self.znear)
        self.projection_[(3,3)] = 0.

    def getViewProjectionMatrix(self):
        tmp = self.vpMatrix_.m
        vpMat = array.array('f')
        for row in tmp:
            for v in row:
                vpMat.append(v)
        return vpMat

    def getViewProjectionMatrixRT(self, tr):
        tmp = self.vpMatrix_
        tmp.transpose()
        tr.transpose()
        tmp =  (tr * tmp).m
        vpMat = array.array('f')
        for row in tmp:
            for v in row:
                vpMat.append(v)
        return vpMat

    def setDirection(self, dir, vert):
        dir.normalize()
        tmp = dir.get()
        dir.init_vector(tmp[0] * -1.,tmp[1] * -1., tmp[2] * -1.)
        self.orientation_.init_translation(self.ORIGINAL_FORWARD, dir)
        self.updateVectors()
        self.vertical_ = vert
        if(sl.Translation.dot_translation(self.vertical_, self.up_) < 0.):
            tmp = sl.Rotation()
            tmp.init_angle_translation(3.14, self.ORIGINAL_FORWARD)
            self.rotate(tmp)

    def translate(self, t):
        ref = self.position_.get()
        tmp = t.get()
        self.position_.init_vector(ref[0] + tmp[0], ref[1] + tmp[1], ref[2] + tmp[2])

    def setPosition(self, p):
        self.position_ = p

    def rotate(self, r):
        tmp = sl.Orientation()
        tmp.init_rotation(r)
        self.orientation_ = tmp * self.orientation_
        self.updateVectors()

    def setRotation(self, r):
        self.orientation_.init_rotation(r)
        self.updateVectors()

    def updateVectors(self):
        self.forward_ = self.ORIGINAL_FORWARD * self.orientation_
        self.up_ = self.ORIGINAL_UP * self.orientation_
        right = self.ORIGINAL_RIGHT
        tmp = right.get()
        right.init_vector(tmp[0] * -1.,tmp[1] * -1., tmp[2] * -1.)
        self.right_ = right * self.orientation_
