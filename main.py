import RPi.GPIO as GPIO
import threading as th
import time
import math
import numpy as np
from inverse_kinimatics import calc_servo_positions, normal_vector_from_projections, angle_disc_and_rotated_axis
from servo import Servo
from camera import Camera

# GPIO setup
GPIO.setmode(GPIO.BCM)

# Initialize servos
servo1 = Servo(17, 77.3, 180, 2.5, 12.5)
servo2 = Servo(27, 69.5, 180, 2.5, 12.5)
servo3 = Servo(22, 90, 180, 2.5, 12.5)
camera = Camera()

# PID parameters
p = 0.11
i = 0.04
d = 0.07
max_integral = 120  # Limit for integral term

# State variables
pos_history = []
history_len = 2
integral = np.array([0.0,0.0])
last_time = time.time()

# Flags
running = True
ball_on_plate = False

# Key capture thread to stop the program
def key_capture_thread():
    global running
    input()
    running = False

# saves the balls position
def record_hisory(pos, pos_history):
    pos_history.insert(0, [pos, time.time()])
    while len(pos_history) > history_len:
        pos_history.pop(history_len)

# Get ball velocity
def get_ball_vel(pos_history):
    if len(pos_history) == history_len:
        diff = pos_history[0][0] - pos_history[history_len-1][0]
        dt = time.time() - pos_history[history_len-1][1]
        vel = diff/dt
    else:
        vel = np.array([0.0,0.0])
    return vel

def update_integral(integral, error, dt):
    integral += error * dt
    integral = np.clip(integral, -max_integral, max_integral)
    
    return integral

def cap_normal_vector(normal_vector, max_angle):
    # Calculate the max length of the projection onto the XY plane
    max_xy_projection = math.acos(max_angle)
    
    # Calculate the current length of the projection onto the XY plane
    xy_projection_length = np.linalg.norm(normal_vector[:2])  # norm of (nx, ny)

    if xy_projection_length > max_xy_projection:
        # Calculate the scaling factor needed to cap the XY projection
        scale_factor = max_xy_projection / xy_projection_length
        
        # Scale the x and y components accordingly
        normal_vector[:2] *= scale_factor

        # Recalculate the z-component to maintain the original vector direction
        normal_vector[2] = np.sqrt(1 - np.sum(normal_vector[:2]**2))
    
    return normal_vector

# calculates the height of the center of the plate to keep the ball at a constant one (looks cool)
def calc_plate_height(pos, disc_normal, base_height=120):
    if pos[0] == 0:
        if pos[1] > 0:
            angle_ball_center = 90
        elif pos[1] < 0:
            angle_ball_center = 270
        else:
            angle_ball_center = 0
    elif pos[0] > 0:
        angle_ball_center = math.atan(pos[1]/pos[0])
    else:
        angle_ball_center = math.atan(pos[1]/pos[0]) + math.radians(180)
    
    ball_disc_angle = angle_disc_and_rotated_axis(disc_normal, angle_ball_center)
    
    return base_height-math.tan(ball_disc_angle)*min(math.sqrt(pos[0]**2+pos[1]**2),90)

th.Thread(target=key_capture_thread, args=(), name='key_capture_thread', daemon=True).start()

while running:
    
    pos = camera.get_ball_pos()
    
    if not np.isnan(pos).all(): # if camera sees the ball
        if not ball_on_plate:
            ball_on_plate = True
            print("back on :D")
        
        current_time = time.time()
        dt = current_time - last_time
        last_time = current_time
        
        record_hisory(pos, pos_history)

        target = np.array([0.0,0.0])
        
        error = pos+target

        integral = update_integral(integral, error, dt)

        vel = get_ball_vel(pos_history)
        
        slope = p*error + i*integral + d*vel
        
        disc_normal = normal_vector_from_projections(math.radians(slope[0]), math.radians(slope[1]))
        
        disc_normal = cap_normal_vector(disc_normal, math.radians(10))
        
        height = calc_plate_height(pos,disc_normal)
        
        angle1, angle2, angle3 = calc_servo_positions(disc_normal, height)
        servo1.angle = angle1
        servo2.angle = angle2
        servo3.angle = angle3
    else:
        if ball_on_plate:
            ball_on_plate = False
            print("ball fell off :(")
            
        angle1, angle2, angle3 = calc_servo_positions([0,0,1], 120)
        servo1.angle = angle1
        servo2.angle = angle2
        servo3.angle = angle3

# Cleanup
angle1, angle2, angle3 = calc_servo_positions([0,0,1], 120)
servo1.angle = angle1
servo2.angle = angle2
servo3.angle = angle3

time.sleep(0.3)

del camera
del servo1
del servo2
del servo3
GPIO.cleanup()